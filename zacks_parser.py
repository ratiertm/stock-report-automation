#!/usr/bin/env python3
"""Zacks Stock Report PDF Parser — Production-ready module
Maps extracted data to DB schema: stock_profiles, stock_reports, stock_financials, stock_key_stats, stock_peers
"""

import pdfplumber
import re
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any
from decimal import Decimal, InvalidOperation


def safe_decimal(val: str) -> Optional[str]:
    """Convert string to decimal-safe string, return None if invalid."""
    if not val or val.strip() in ("N/A", "NR", "NM", "-", ""):
        return None
    cleaned = val.replace(",", "").replace("$", "").strip()
    try:
        Decimal(cleaned)
        return cleaned
    except (InvalidOperation, ValueError):
        return None


def safe_int(val: str) -> Optional[int]:
    if not val:
        return None
    cleaned = val.replace(",", "").strip()
    try:
        return int(float(cleaned))
    except (ValueError, TypeError):
        return None


@dataclass
class ZacksProfile:
    """Maps to stock_profiles table."""
    ticker: Optional[str] = None
    company_name: Optional[str] = None
    industry: Optional[str] = None


@dataclass
class ZacksReport:
    """Maps to stock_reports table."""
    source: str = "Zacks"
    report_date: Optional[str] = None
    recommendation: Optional[str] = None
    prior_recommendation: Optional[str] = None
    zacks_rank: Optional[int] = None
    zacks_rank_label: Optional[str] = None
    style_scores: Optional[Dict[str, str]] = None
    target_price: Optional[str] = None
    current_price: Optional[str] = None
    price_date: Optional[str] = None
    industry_rank: Optional[str] = None
    reasons_to_buy: Optional[str] = None
    reasons_to_sell: Optional[str] = None
    last_earnings_summary: Optional[str] = None
    outlook: Optional[str] = None
    business_summary: Optional[str] = None
    recent_news: Optional[List[Dict]] = None


@dataclass
class ZacksKeyStats:
    """Maps to stock_key_stats table subset (Zacks-specific metrics)."""
    pe_forward_12m: Optional[str] = None
    ps_forward_12m: Optional[str] = None
    ev_ebitda: Optional[str] = None
    peg_ratio: Optional[str] = None
    price_to_book: Optional[str] = None
    price_to_cashflow: Optional[str] = None
    debt_equity: Optional[str] = None
    cash_per_share: Optional[str] = None
    earnings_yield_pct: Optional[str] = None
    dividend_yield_pct: Optional[str] = None
    dividend_rate: Optional[str] = None
    beta: Optional[str] = None
    market_cap_b: Optional[str] = None
    week_52_high: Optional[str] = None
    week_52_low: Optional[str] = None
    valuation_multiples: Optional[Dict] = None


@dataclass
class ZacksFinancial:
    """Maps to stock_financials table."""
    fiscal_year: int = 0
    fiscal_quarter: Optional[int] = None
    period_type: str = "annual"
    is_estimate: bool = False
    revenue: Optional[str] = None
    eps: Optional[str] = None
    gross_margin_pct: Optional[str] = None
    operating_margin_pct: Optional[str] = None
    eps_surprise_pct: Optional[str] = None
    sales_surprise_pct: Optional[str] = None


@dataclass
class ZacksPeer:
    """Maps to stock_peers table."""
    peer_ticker: Optional[str] = None
    peer_name: Optional[str] = None
    recommendation: Optional[str] = None
    rank: Optional[int] = None
    detailed_comparison: Optional[Dict] = None


@dataclass
class ZacksParseResult:
    """Complete parse result for one Zacks PDF."""
    profile: ZacksProfile = field(default_factory=ZacksProfile)
    report: ZacksReport = field(default_factory=ZacksReport)
    key_stats: ZacksKeyStats = field(default_factory=ZacksKeyStats)
    financials: List[ZacksFinancial] = field(default_factory=list)
    peers: List[ZacksPeer] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class ZacksParser:
    """Parse Zacks stock report PDFs."""

    def parse(self, filepath: str) -> ZacksParseResult:
        """Main entry point: parse a Zacks PDF and return structured data."""
        result = ZacksParseResult()

        try:
            with pdfplumber.open(filepath) as pdf:
                pages_text = [p.extract_text() or "" for p in pdf.pages]
                full_text = "\n".join(pages_text)
                page1 = pages_text[0] if pages_text else ""

                self._parse_header(page1, result)
                self._parse_rank_and_scores(page1, result)
                self._parse_text_sections(full_text, result)
                self._parse_valuation_data(full_text, result)
                self._parse_industry_comparison(pages_text, pdf, result)

        except Exception as e:
            result.errors.append(f"Fatal: {str(e)}")

        return result

    def _parse_header(self, text: str, result: ZacksParseResult):
        """Parse header: date, company, ticker, recommendation, price, target."""
        lines = text.split("\n")

        # Line 0: "Zacks Report Date: February 20, 2026"
        m = re.search(r'Report Date:\s*(\w+ \d+, \d{4})', text)
        if m:
            result.report.report_date = m.group(1)

        # Line 1: "Danaher Corporation (DHR) Long Term: 6-12 Months Zacks Recommendation: Neutral"
        for line in lines[:3]:
            # Company and ticker
            m = re.search(r'^(.+?)\s*\((\w+)\)', line)
            if m:
                result.profile.company_name = m.group(1).strip()
                result.profile.ticker = m.group(2)

            # Recommendation
            m = re.search(r'Zacks Recommendation:\s*(\w+)', line)
            if m:
                result.report.recommendation = m.group(1).strip()

        # Price: "$211.25 (Stock Price as of 02/19/2026)"
        m = re.search(r'\$([\d.,]+)\s*\(Stock Price as of (\d{2}/\d{2}/\d{4})\)', text)
        if m:
            result.report.current_price = safe_decimal(m.group(1))
            result.report.price_date = m.group(2)

        # Prior Recommendation
        m = re.search(r'Prior Recommendation:\s*(\w+)', text)
        if m:
            result.report.prior_recommendation = m.group(1).strip()

        # Price Target
        m = re.search(r'Price Target.*?:\s*\$([\d.,]+)', text)
        if m:
            result.report.target_price = safe_decimal(m.group(1))

    def _parse_rank_and_scores(self, text: str, result: ZacksParseResult):
        """Parse Zacks Rank and Style Scores — FIXED regex for rank bug."""
        # FIXED: "Zacks Rank: (1-5) 3-Hold" → rank=3, label=Hold
        # Old buggy pattern matched (1) and (5) separately
        m = re.search(r'Zacks Rank:\s*\(1-5\)\s*(\d)-(\w+)', text)
        if m:
            result.report.zacks_rank = int(m.group(1))
            result.report.zacks_rank_label = m.group(2)

        # Style Scores: "VGM:C"
        scores = {}
        m = re.search(r'VGM:(\w)', text)
        if m:
            scores["vgm"] = m.group(1)

        for score_name in ["Value", "Growth", "Momentum"]:
            m = re.search(rf'{score_name}:\s*(\w)', text)
            if m:
                scores[score_name.lower()] = m.group(1)

        if scores:
            result.report.style_scores = scores

        # Industry Rank: "Zacks Industry Rank Bottom 40% (145 out of 243)"
        m = re.search(r'Zacks Industry Rank\s+(.+?)(?:\n|$)', text)
        if m:
            result.report.industry_rank = m.group(1).strip()

    def _parse_text_sections(self, text: str, result: ZacksParseResult):
        """Extract major text sections from Zacks report.

        Zacks layout:
        - Page 1: Summary + Price/Consensus chart
        - Page 2: Recent News + Last Earnings Report
        - Page 3: Reasons To Buy (multi-column, with sidebar highlights)
        - Page 4: Reasons To Sell (multi-column, with sidebar highlights)
        - Page 5: Outlook
        - Page 6: Growth Rates + Financial Strength + Valuation
        - Page 7-8: Industry Analysis + Comparison table

        Key: Section headers are followed by ":" and newline.
        """
        # --- Reasons To Buy (page 3 area) ---
        m = re.search(r'Reasons To Buy:\s*\n(.*?)(?=Reasons To Sell:|\Z)',
                       text, re.DOTALL)
        if m:
            result.report.reasons_to_buy = self._clean_section(m.group(1))

        # --- Reasons To Sell (page 4 area) ---
        m = re.search(r'Reasons To Sell:\s*\n(.*?)(?=Last Earnings|Recent News|Outlook|\w+\'s Outlook|\Z)',
                       text, re.DOTALL)
        if m:
            result.report.reasons_to_sell = self._clean_section(m.group(1))

        # --- Last Earnings Report ---
        m = re.search(r'Last Earnings Report\s*\n(.*?)(?=Recent News|Reasons To Buy|Outlook|\w+\'s Outlook|\Z)',
                       text, re.DOTALL)
        if m:
            result.report.last_earnings_summary = self._clean_section(m.group(1))

        # --- Outlook --- (can be "<Company>'s Outlook" or just "Outlook")
        m = re.search(r"(?:\w+'s\s+)?Outlook\s*\n(.*?)(?=Industry (?:Comparison|Analysis)|Valuation|Growth Rates|Financial Strength|\Z)",
                       text, re.DOTALL)
        if m:
            content = self._clean_section(m.group(1))
            if len(content) > 20:
                result.report.outlook = content

        # --- Summary (page 1 text between style scores and chart area) ---
        lines = text.split("\n")
        summary_lines = []
        in_summary = False
        for line in lines:
            if "Summary" in line and "Price, Consensus" in line:
                in_summary = True
                continue
            if in_summary:
                if any(kw in line for kw in ["Reasons To Buy", "Recent News", "Last Earnings",
                                              "Industry Comparison", "Valuation", "Growth Rates"]):
                    break
                if line.strip():
                    summary_lines.append(line.strip())

        if summary_lines:
            result.report.business_summary = "\n".join(summary_lines)

    def _parse_valuation_data(self, text: str, result: ZacksParseResult):
        """Parse Zacks valuation metrics."""
        ks = result.key_stats

        # Forward P/E
        m = re.search(r'P/E\s*\(F1\).*?([\d.,]+)', text)
        if m:
            ks.pe_forward_12m = safe_decimal(m.group(1))

        # PEG
        m = re.search(r'PEG.*?([\d.,]+)', text)
        if m:
            ks.peg_ratio = safe_decimal(m.group(1))

        # P/B
        m = re.search(r'P/B.*?([\d.,]+)', text)
        if m:
            ks.price_to_book = safe_decimal(m.group(1))

        # P/CF
        m = re.search(r'P/CF.*?([\d.,]+)', text)
        if m:
            ks.price_to_cashflow = safe_decimal(m.group(1))

        # P/S
        m = re.search(r'P/S.*?([\d.,]+)', text)
        if m:
            ks.ps_forward_12m = safe_decimal(m.group(1))

        # EV/EBITDA
        m = re.search(r'EV/EBITDA.*?([\d.,]+)', text)
        if m:
            ks.ev_ebitda = safe_decimal(m.group(1))

        # D/E
        m = re.search(r'D/E.*?([\d.,]+)', text)
        if m:
            ks.debt_equity = safe_decimal(m.group(1))

        # Earnings Yield
        m = re.search(r'Earnings Yield.*?([\d.,]+)%', text)
        if m:
            ks.earnings_yield_pct = safe_decimal(m.group(1))

        # Dividend Yield
        m = re.search(r'Dividend Yield.*?([\d.,]+)%', text)
        if m:
            ks.dividend_yield_pct = safe_decimal(m.group(1))

        # Beta
        m = re.search(r'Beta.*?([\d.,]+)', text)
        if m:
            ks.beta = safe_decimal(m.group(1))

        # Market Cap
        m = re.search(r'Market Cap.*?\$([\d.,]+)\s*(B|M)', text)
        if m:
            val = safe_decimal(m.group(1))
            unit = m.group(2)
            if val and unit == "M":
                val = str(Decimal(val) / 1000)  # Convert M to B
            ks.market_cap_b = val

    def _parse_industry_comparison(self, pages_text: List[str], pdf, result: ZacksParseResult):
        """Parse Industry Comparison from text (table extraction unreliable for Zacks).

        Zacks Industry Comparison format (text-based):
        Line: "DHR X Industry S&P 500 CSL HON MMM"  ← column headers (ticker + peers)
        Line: "Zacks Recommendation (Long Term) Neutral - - Underperform Neutral Neutral"
        Line: "Zacks Rank (Short Term) - -"
        ...many metric rows...

        Also parse Top Peers from Industry Analysis section.
        """
        full_text = "\n".join(pages_text)

        # --- Top Peers from Industry Analysis section ---
        # Pattern: "CompanyName (TICKER) Recommendation"
        # e.g., "Honeywell International Inc. (HON) Neutral"
        # These appear before the Industry Comparison table
        peer_pattern = r'([A-Z][A-Za-z\s&.,]+?)\s+\((\w+)\)\s+(Neutral|Outperform|Underperform|Strong Buy|Strong Sell|Buy|Sell|Hold)'
        for m in re.finditer(peer_pattern, full_text):
            name = m.group(1).strip()
            ticker = m.group(2)
            rec = m.group(3)

            # Skip the main company itself
            if ticker == result.profile.ticker:
                continue

            # Avoid duplicates
            if any(p.peer_ticker == ticker for p in result.peers):
                continue

            peer = ZacksPeer(
                peer_ticker=ticker,
                peer_name=name,
                recommendation=rec,
            )
            result.peers.append(peer)

        # --- Industry Comparison table (text parsing) ---
        for page_text in pages_text:
            if "Industry Comparison" not in page_text:
                continue

            lines = page_text.split("\n")
            header_line = None
            peer_tickers = []

            for i, line in enumerate(lines):
                # Find the header line with tickers
                if result.profile.ticker and result.profile.ticker in line and \
                   ("Industry" in line or "S&P" in line):
                    header_line = line
                    # Parse tickers from header: "DHR X Industry S&P 500 CSL HON MMM"
                    # X = the main company marker
                    parts = line.split()
                    # Find tickers (uppercase 1-5 letter words that aren't "X", "S&P", "Industry")
                    skip = {"X", "Industry", "S&P", "500", result.profile.ticker}
                    for p in parts:
                        if p.upper() == p and 1 <= len(p) <= 5 and p not in skip and p.isalpha():
                            peer_tickers.append(p)

                    # Now parse Zacks Rank line if present
                    for j in range(i+1, min(i+5, len(lines))):
                        if "Zacks Rank" in lines[j]:
                            # Extract rank numbers for each peer
                            ranks = re.findall(r'\b([1-5])\b', lines[j])
                            for k, ticker in enumerate(peer_tickers):
                                if k < len(ranks):
                                    # Find or create peer
                                    existing = [p for p in result.peers if p.peer_ticker == ticker]
                                    if existing:
                                        existing[0].rank = int(ranks[k])
                                    else:
                                        result.peers.append(ZacksPeer(
                                            peer_ticker=ticker,
                                            rank=int(ranks[k])
                                        ))
                            break
                    break

        # Extract industry name
        m = re.search(r'Industry:\s*(.+?)\s+Industry Peers', full_text)
        if m:
            result.profile.industry = m.group(1).strip()

    def _clean_section(self, text: str) -> str:
        """Clean extracted section text."""
        lines = text.strip().split("\n")
        # Remove boilerplate
        cleaned = [l for l in lines
                   if not l.startswith("©") and
                      not l.startswith("Zacks Investment Research") and
                      not "Page " in l and
                      l.strip()]
        return "\n".join(cleaned).strip()


def parse_zacks(filepath: str) -> dict:
    """Convenience function: parse Zacks PDF and return as dict."""
    parser = ZacksParser()
    result = parser.parse(filepath)
    return {
        "profile": asdict(result.profile),
        "report": asdict(result.report),
        "key_stats": asdict(result.key_stats),
        "financials": [asdict(f) for f in result.financials],
        "peers": [asdict(p) for p in result.peers],
        "errors": result.errors,
        "warnings": result.warnings,
    }


if __name__ == "__main__":
    PDF_DIR = "mnt/Projects/active/Stock_report_automation"
    files = ["DHR.pdf", "AAPL-Zacks.pdf", "MSFT-Zacks.pdf", "JPM-Zacks.pdf"]

    for fname in files:
        result = parse_zacks(f"{PDF_DIR}/{fname}")
        print(f"\n{'='*60}")
        print(f"  {fname}")
        print(f"{'='*60}")
        p = result["profile"]
        r = result["report"]
        k = result["key_stats"]
        print(f"  Ticker: {p['ticker']} | Company: {p['company_name']}")
        print(f"  Date: {r['report_date']}")
        print(f"  Rec: {r['recommendation']} (prior: {r['prior_recommendation']})")
        print(f"  Zacks Rank: {r['zacks_rank']}-{r['zacks_rank_label']}")
        print(f"  Scores: {r['style_scores']}")
        print(f"  Price: ${r['current_price']} | Target: ${r['target_price']}")
        print(f"  Industry Rank: {r['industry_rank']}")
        print(f"  --- Text Sections ---")
        for sec in ["reasons_to_buy", "reasons_to_sell", "last_earnings_summary", "outlook"]:
            val = r.get(sec)
            if val:
                print(f"    [{sec}]: {val[:80]}...")
            else:
                print(f"    [{sec}]: NOT FOUND")
        print(f"  --- Peers: {len(result['peers'])} ---")
        for peer in result["peers"][:5]:
            print(f"    {peer['peer_ticker']}: {peer['peer_name']} ({peer['recommendation']}, rank={peer['rank']})")
        if result["errors"]:
            print(f"  ⚠️ Errors: {result['errors']}")
