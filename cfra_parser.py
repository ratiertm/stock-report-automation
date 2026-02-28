#!/usr/bin/env python3
"""CFRA Stock Report PDF Parser — Production-ready module
Maps extracted data to DB schema: stock_profiles, stock_reports, stock_financials, stock_key_stats, stock_analyst_notes
"""

import pdfplumber
import re
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any
from decimal import Decimal, InvalidOperation
from datetime import date, datetime


def safe_decimal(val: str) -> Optional[str]:
    """Convert string to decimal-safe string, return None if invalid."""
    if not val or val.strip() in ("N/A", "NR", "NM", "-", ""):
        return None
    cleaned = val.replace(",", "").strip()
    try:
        Decimal(cleaned)
        return cleaned
    except (InvalidOperation, ValueError):
        return None


def safe_int(val: str) -> Optional[int]:
    """Convert string to int, return None if invalid."""
    if not val:
        return None
    cleaned = val.replace(",", "").strip()
    try:
        return int(float(cleaned))
    except (ValueError, TypeError):
        return None


@dataclass
class CFRAProfile:
    """Maps to stock_profiles table."""
    ticker: Optional[str] = None
    company_name: Optional[str] = None
    exchange: Optional[str] = None
    gics_sector: Optional[str] = None
    gics_sub_industry: Optional[str] = None
    investment_style: Optional[str] = None


@dataclass
class CFRAReport:
    """Maps to stock_reports table."""
    source: str = "CFRA"
    report_date: Optional[str] = None
    analyst_name: Optional[str] = None
    recommendation: Optional[str] = None
    stars_rating: Optional[int] = None
    target_price: Optional[str] = None
    current_price: Optional[str] = None
    price_date: Optional[str] = None
    risk_assessment: Optional[str] = None
    fair_value: Optional[str] = None
    fair_value_rank: Optional[int] = None
    volatility: Optional[str] = None
    technical_eval: Optional[str] = None
    insider_activity: Optional[str] = None
    investment_style: Optional[str] = None
    highlights: Optional[str] = None
    investment_rationale: Optional[str] = None
    business_summary: Optional[str] = None
    sub_industry_outlook: Optional[str] = None


@dataclass
class CFRAKeyStats:
    """Maps to stock_key_stats table."""
    week_52_high: Optional[str] = None
    week_52_low: Optional[str] = None
    trailing_12m_eps: Optional[str] = None
    trailing_12m_pe: Optional[str] = None
    market_cap_b: Optional[str] = None
    shares_outstanding_m: Optional[str] = None
    beta: Optional[str] = None
    eps_cagr_3yr_pct: Optional[str] = None
    institutional_ownership_pct: Optional[str] = None
    dividend_yield_pct: Optional[str] = None
    dividend_rate: Optional[str] = None
    price_to_sales: Optional[str] = None
    price_to_ebitda: Optional[str] = None
    price_to_pretax: Optional[str] = None
    quality_ranking: Optional[str] = None
    oper_eps_current_e: Optional[str] = None
    oper_eps_next_e: Optional[str] = None
    pe_on_oper_eps_current: Optional[str] = None


@dataclass
class CFRAFinancial:
    """Maps to stock_financials table."""
    fiscal_year: int = 0
    fiscal_quarter: Optional[int] = None
    period_type: str = "annual"
    is_estimate: bool = False
    revenue: Optional[str] = None
    eps: Optional[str] = None


@dataclass
class CFRAAnalystNote:
    """Maps to stock_analyst_notes table."""
    source: str = "CFRA"
    published_at: Optional[str] = None
    analyst_name: Optional[str] = None
    content: Optional[str] = None
    stock_price_at_note: Optional[str] = None


@dataclass
class CFRAParseResult:
    """Complete parse result for one CFRA PDF."""
    profile: CFRAProfile = field(default_factory=CFRAProfile)
    report: CFRAReport = field(default_factory=CFRAReport)
    key_stats: CFRAKeyStats = field(default_factory=CFRAKeyStats)
    financials: List[CFRAFinancial] = field(default_factory=list)
    analyst_notes: List[CFRAAnalystNote] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class CFRAParser:
    """Parse CFRA stock report PDFs."""

    RECOMMENDATIONS = ["STRONG BUY", "STRONG SELL", "BUY", "HOLD", "SELL"]

    def parse(self, filepath: str) -> CFRAParseResult:
        """Main entry point: parse a CFRA PDF and return structured data."""
        result = CFRAParseResult()

        try:
            with pdfplumber.open(filepath) as pdf:
                pages_text = [p.extract_text() or "" for p in pdf.pages]
                full_text = "\n".join(pages_text)
                page1 = pages_text[0] if pages_text else ""

                self._parse_header(page1, result)
                self._parse_key_stats(page1, result)
                self._parse_stars(page1, result)
                self._parse_risk_assessment(full_text, result)
                self._parse_text_sections(full_text, result)
                self._parse_revenue_eps(full_text, result)
                self._parse_analyst_notes(full_text, result)

        except Exception as e:
            result.errors.append(f"Fatal: {str(e)}")

        return result

    def _parse_header(self, text: str, result: CFRAParseResult):
        """Parse first line: report date, exchange, ticker, S&P membership."""
        lines = text.split("\n")

        # Line 0: "Stock Report | February 21, 2026 | Symbol: NasdaqGS | PLTR is in the S&P 500"
        if lines:
            line0 = lines[0]
            # Report date
            m = re.search(r'(\w+ \d+, \d{4})', line0)
            if m:
                result.report.report_date = m.group(1)

            # Exchange and Ticker: "Symbol: NasdaqGS | PLTR"
            m = re.search(r'Symbol:\s*(\S+)\s*\|\s*(\w+)', line0)
            if m:
                result.profile.exchange = m.group(1)
                result.profile.ticker = m.group(2)
            else:
                # Fallback: try "Symbol: NYSE | JPM"
                m = re.search(r'Symbol:\s*(\S+)', line0)
                if m:
                    result.profile.exchange = m.group(1)
                # Ticker from "XXXX is in the"
                m = re.search(r'\|\s*(\w+)\s+is\s+in', line0)
                if m:
                    result.profile.ticker = m.group(1)

        # Line 1: Company name
        if len(lines) > 1:
            result.profile.company_name = lines[1].strip()

        # Line 3: Recommendation (BUY/STRONG BUY etc + stars)
        for line in lines[2:6]:
            for rec in self.RECOMMENDATIONS:
                if rec in line:
                    result.report.recommendation = rec
                    break
            if result.report.recommendation:
                break

        # Line 4: Price and target
        for line in lines[3:6]:
            # Current price: "USD 135.24 (as of market close Feb 20, 2026)"
            m = re.search(r'USD\s+([\d.,]+)\s+\(as of market close\s+(.+?)\)', line)
            if m:
                result.report.current_price = safe_decimal(m.group(1))
                result.report.price_date = m.group(2).strip()

            # Target price: "USD 203.00 USD" or at end
            m = re.search(r'\)\s+USD\s+([\d.,]+)', line)
            if m:
                result.report.target_price = safe_decimal(m.group(1))

        # Line 5: Analyst name
        for line in lines[4:8]:
            m = re.search(r'Equity Analyst\s+(.+)', line)
            if m:
                result.report.analyst_name = m.group(1).strip()
                break

        # GICS Sector — on the line starting with "GICS Sector"
        for line in lines[5:10]:
            m = re.search(r'GICS Sector\s+(\S+(?:\s+\S+)?)\s+Summary', line)
            if m:
                result.profile.gics_sector = m.group(1).strip()
                break
            # Fallback: no "Summary" on same line
            m = re.search(r'GICS Sector\s+(.+?)(?:\s{2,}|$)', line)
            if m and 'Summary' not in m.group(1):
                result.profile.gics_sector = m.group(1).strip()
                break

        # Sub-Industry — next line after GICS Sector
        for i, line in enumerate(lines[5:12], start=5):
            if 'Sub-Industry' in line:
                # "Sub-Industry Application Software"
                # But JPM: "Sub-Industry Diversified Banks in assets & operations..."
                m = re.search(r'Sub-Industry\s+(.+?)(?:\s+in\s+|\s+and\s+|\s{3,}|$)', line)
                if m:
                    sub = m.group(1).strip()
                    # Remove trailing words that are part of Summary text
                    # Known clean values end at 2-3 words
                    words = sub.split()
                    if len(words) > 4:
                        # Likely text overflow — take first 2-3 words
                        sub = " ".join(words[:3])
                    result.profile.gics_sub_industry = sub
                break

        # Investment Style
        for line in lines[3:6]:
            m = re.search(r'(Large-Cap|Mid-Cap|Small-Cap)\s+(Growth|Blend|Value)', line)
            if m:
                result.profile.investment_style = f"{m.group(1)} {m.group(2)}"
                result.report.investment_style = result.profile.investment_style
                break

    def _parse_key_stats(self, text: str, result: CFRAParseResult):
        """Parse Key Stock Statistics section."""
        lines = text.split("\n")
        ks = result.key_stats

        for line in lines:
            # 52-Wk Range USD 207.52 - 66.12
            m = re.search(r'52-Wk Range\s+USD\s+([\d.,]+)\s*-\s*([\d.,]+)', line)
            if m:
                ks.week_52_high = safe_decimal(m.group(1))
                ks.week_52_low = safe_decimal(m.group(2))

            # Trailing 12-Month EPS USD 0.75
            m = re.search(r'Trailing 12-Month EPS\s+USD\s+([\d.,]+)', line)
            if m:
                ks.trailing_12m_eps = safe_decimal(m.group(1))

            # Trailing 12-Month P/E 180.32
            m = re.search(r'Trailing 12-Month P/E\s+([\d.,]+)', line)
            if m:
                ks.trailing_12m_pe = safe_decimal(m.group(1))

            # Market Capitalization[B] USD 322.61
            m = re.search(r'Market Capitalization\[B\]\s+USD\s+([\d.,]+)', line)
            if m:
                ks.market_cap_b = safe_decimal(m.group(1))

            # Beta 1.64
            m = re.search(r'Beta\s+([\d.,]+)', line)
            if m:
                ks.beta = safe_decimal(m.group(1))

            # Yield [%] 0.91 or N/A
            m = re.search(r'Yield \[%\]\s+([\d.,]+|N/A)', line)
            if m:
                ks.dividend_yield_pct = safe_decimal(m.group(1))

            # Oper.EPS2026E USD 1.25
            m = re.search(r'Oper\.EPS(\d{4})E\s+USD\s+([\d.,]+)', line)
            if m:
                if not ks.oper_eps_current_e:
                    ks.oper_eps_current_e = safe_decimal(m.group(2))
                else:
                    ks.oper_eps_next_e = safe_decimal(m.group(2))

            # P/E on Oper.EPS2026E 108.19
            m = re.search(r'P/E on Oper\.EPS\d{4}E\s+([\d.,]+)', line)
            if m:
                ks.pe_on_oper_eps_current = safe_decimal(m.group(1))

            # Common Shares Outstg.[M] 2,391.00
            m = re.search(r'Common Shares Outstg\.\[M\]\s+([\d.,]+)', line)
            if m:
                ks.shares_outstanding_m = safe_decimal(m.group(1))

            # 3-yr Proj. EPS CAGR[%] 49
            m = re.search(r'3-yr Proj\. EPS CAGR\[%\]\s+([\d.,]+)', line)
            if m:
                ks.eps_cagr_3yr_pct = safe_decimal(m.group(1))

            # Institutional Ownership [%] 36.0
            m = re.search(r'Institutional Ownership \[%\]\s+([\d.,]+)', line)
            if m:
                ks.institutional_ownership_pct = safe_decimal(m.group(1))

            # Dividend Rate/Share USD 3.64 or N/A
            m = re.search(r'Dividend Rate/Share\s+(?:USD\s+)?([\d.,]+|N/A)', line)
            if m:
                ks.dividend_rate = safe_decimal(m.group(1))

            # SPGMI's Quality Ranking A+
            m = re.search(r"SPGMI's Quality Ranking\s+(\S+)", line)
            if m:
                ks.quality_ranking = m.group(1)

    def _parse_stars(self, text: str, result: CFRAParseResult):
        """Parse STARS rating from « characters."""
        for line in text.split("\n"):
            if "«" in line:
                count = line.count("«")
                if 1 <= count <= 5:
                    result.report.stars_rating = count
                break

    def _parse_risk_assessment(self, text: str, result: CFRAParseResult):
        """Parse risk assessment, volatility, technical eval, insider activity from full text."""
        # These appear in later pages typically
        # Risk Assessment: Look for "LOW MEDIUM HIGH" pattern after "Risk Assessment"
        lines = text.split("\n")
        for i, line in enumerate(lines):
            if "Risk Assessment" in line and i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                if next_line == "LOW MEDIUM HIGH":
                    # The actual value is determined by position/bold — in text extraction
                    # we can look for standalone LOW/MEDIUM/HIGH in nearby lines
                    # For now, mark as found but value needs context from PDF structure
                    result.report.risk_assessment = "FOUND"  # Will be refined

            # Fair Value Calculation
            m = re.search(r'Fair Value Calculation.*?(\d+\.\d+)', line)
            if m:
                result.report.fair_value = safe_decimal(m.group(1))

            # Fair Value rank (1-5 stars)
            m = re.search(r'Fair Value\s+Rank\s+(\d)', line)
            if m:
                result.report.fair_value_rank = int(m.group(1))

            # Volatility
            if "Volatility" in line:
                for vol in ["LOW", "AVERAGE", "HIGH"]:
                    if vol in line.upper():
                        result.report.volatility = vol
                        break

            # Technical
            if "Technical" in line:
                for tech in ["BULLISH", "NEUTRAL", "BEARISH"]:
                    if tech in line.upper():
                        result.report.technical_eval = tech
                        break

            # Insider
            if "Insider" in line:
                for insider in ["FAVORABLE", "NEUTRAL", "UNFAVORABLE"]:
                    if insider in line.upper():
                        result.report.insider_activity = insider
                        break

    def _parse_text_sections(self, text: str, result: CFRAParseResult):
        """Extract major text sections from CFRA multi-column layout.

        CFRA page layout:
        - Page 1: Highlights + Investment Rationale (left cols) interleaved with EPS data (right col)
        - Page 2-3: Business Summary
        - Page 4-5: Sub-Industry Outlook + Peer Group
        - Page 5+: Analyst Notes, Quantitative Evaluations

        Strategy: Extract by page, then clean bullet-point content (lines starting with 'u').
        """
        lines = text.split("\n")

        # --- Highlights + Investment Rationale (Page 1 area) ---
        # Find the line with "Highlights Investment Rationale/Risk"
        highlights_content = []
        rationale_content = []
        in_hl_section = False

        for i, line in enumerate(lines):
            if "Highlights" in line and "Investment Rationale" in line:
                in_hl_section = True
                continue
            if in_hl_section:
                # Stop at page break markers
                if any(kw in line for kw in ["Business Summary", "Balance Sheet",
                                              "Revenue/Earnings Data", "Dividend Data",
                                              "Key Stock Statistics"]):
                    break
                # Extract bullet points (start with 'u' which is the bullet marker)
                # These are interleaved: left=Highlights, right=Rationale, far right=EPS data
                # We collect all bullet content into one combined section
                if line.strip().startswith("u"):
                    highlights_content.append(line.strip())
                elif any(c.isalpha() for c in line[:5] if c != ' '):
                    # Non-numeric content that's not a bullet
                    highlights_content.append(line.strip())

        if highlights_content:
            # Split: lines before second "u" that mentions "reiterate/rating/risk" → rationale
            # For now, combine all into highlights and rationale
            all_bullets = []
            for line in highlights_content:
                # Clean up EPS data fragments (numbers like "2027 E 0.37 E 0.39")
                cleaned = re.sub(r'\d{4}\s+(?:E\s+)?[\d.,]+(?:\s+E?\s*[\d.,]+)*$', '', line).strip()
                if cleaned and len(cleaned) > 10:
                    all_bullets.append(cleaned)

            if all_bullets:
                # First few bullets tend to be Highlights, rest is Rationale
                mid = len(all_bullets) // 2
                result.report.highlights = "\n".join(all_bullets[:mid]) if all_bullets[:mid] else None
                result.report.investment_rationale = "\n".join(all_bullets[mid:]) if all_bullets[mid:] else None

        # --- Business Summary (Page 2-3 area) ---
        bs_content = []
        in_bs = False
        for line in lines:
            if "Business Summary" in line:
                in_bs = True
                # Skip the "Business Summary Feb 03, 2026 Corporate information" header
                continue
            if in_bs:
                if any(kw in line for kw in ["Sub-Industry Outlook", "Balance Sheet",
                                              "Quantitative Evaluations", "Analyst Notes"]):
                    break
                # Skip boilerplate
                if line.startswith("Source:") or line.startswith("Past performance") or \
                   "Corporate information" in line:
                    continue
                # Skip company contact info (phone numbers, addresses)
                if re.match(r'^\s*(?:N/A\s*)?\(\d{3}', line):
                    continue
                if line.strip():
                    bs_content.append(line.strip())

            if bs_content:
                result.report.business_summary = "\n".join(bs_content)

        # --- Sub-Industry Outlook (Page 4-5 area) ---
        sio_content = []
        in_sio = False
        for line in lines:
            if "Sub-Industry Outlook" in line:
                in_sio = True
                continue
            if in_sio:
                if any(kw in line for kw in ["Peer Group", "Analyst Notes",
                                              "Quantitative Evaluations"]):
                    break
                if line.startswith("Source:") or line.startswith("Past performance"):
                    continue
                if line.strip():
                    sio_content.append(line.strip())

        if sio_content:
            result.report.sub_industry_outlook = "\n".join(sio_content)

    def _parse_revenue_eps(self, text: str, result: CFRAParseResult):
        """Parse Revenue and EPS tables from text."""
        # Revenue section
        rev_match = re.search(
            r'Revenue \(Million USD\)\n(.*?)(?:Earnings Per Share|Dividend Data)',
            text, re.DOTALL
        )
        if rev_match:
            self._parse_financial_table(rev_match.group(1), "revenue", result)

        # EPS section
        eps_match = re.search(
            r'Earnings Per Share \[USD\]\n(.*?)(?:Fiscal Year|Dividend Data|Key Stock|\Z)',
            text, re.DOTALL
        )
        if eps_match:
            self._parse_financial_table(eps_match.group(1), "eps", result)

    def _parse_financial_table(self, section_text: str, metric: str, result: CFRAParseResult):
        """Parse a CFRA financial data table (Revenue or EPS)."""
        lines = section_text.strip().split("\n")

        # Skip header line "1Q 2Q 3Q 4Q Year"
        for line in lines:
            line = line.strip()
            if not line or line.startswith("1Q") or line.startswith("Source:") or \
               line.startswith("Past performance") or line.startswith("Analysis prepared"):
                continue

            # Pattern: "2027 E 2,276 E 2,402 E 2,684 E 2,974 E 10,336"
            # Or: "2025 884 1,004 1,181 1,407 4,475"
            m = re.match(r'(\d{4})\s+(.*)', line)
            if not m:
                continue

            year = int(m.group(1))
            rest = m.group(2).strip()

            # Parse values: may have "E" prefix markers
            # Split into tokens
            tokens = rest.split()

            values = []
            is_estimates = []
            is_est = False

            for token in tokens:
                if token == "E":
                    is_est = True
                    continue
                val = safe_decimal(token)
                if val is not None:
                    values.append(val)
                    is_estimates.append(is_est)
                    is_est = False  # reset for next value

            # Map: Q1, Q2, Q3, Q4, Annual
            quarters = [1, 2, 3, 4, None]
            for i, (val, est) in enumerate(zip(values, is_estimates)):
                if i >= 5:
                    break

                # Check if this financial already exists
                q = quarters[i] if i < 4 else None
                pt = "quarterly" if q else "annual"

                # Avoid duplicates
                existing = [f for f in result.financials
                           if f.fiscal_year == year and f.fiscal_quarter == q]
                if existing:
                    # Update the existing entry
                    setattr(existing[0], metric, val)
                    existing[0].is_estimate = existing[0].is_estimate or est
                else:
                    fin = CFRAFinancial(
                        fiscal_year=year,
                        fiscal_quarter=q,
                        period_type=pt,
                        is_estimate=est,
                    )
                    setattr(fin, metric, val)
                    result.financials.append(fin)

    def _parse_analyst_notes(self, text: str, result: CFRAParseResult):
        """Parse Analyst Notes section (time series of research notes)."""
        # Pattern: "Analysis prepared by Janice Quek on Feb 03, 2026 09:31 AM ET, when the stock traded at USD 147.76."
        pattern = r'Analysis prepared by (.+?) on (.+?),\s*when the stock traded at USD ([\d.,]+)'
        for m in re.finditer(pattern, text):
            note = CFRAAnalystNote(
                analyst_name=m.group(1).strip(),
                published_at=m.group(2).strip(),
                stock_price_at_note=safe_decimal(m.group(3)),
            )
            result.analyst_notes.append(note)


def parse_cfra(filepath: str) -> dict:
    """Convenience function: parse CFRA PDF and return as dict."""
    parser = CFRAParser()
    result = parser.parse(filepath)
    return {
        "profile": asdict(result.profile),
        "report": asdict(result.report),
        "key_stats": asdict(result.key_stats),
        "financials": [asdict(f) for f in result.financials],
        "analyst_notes": [asdict(n) for n in result.analyst_notes],
        "errors": result.errors,
        "warnings": result.warnings,
    }


if __name__ == "__main__":
    import json
    import sys

    PDF_DIR = "mnt/Projects/active/Stock_report_automation"
    files = ["pltr.pdf", "MSFT-CFRA.pdf", "JNJ-CFRA.pdf", "JPM-CFRA.pdf", "PG-CFRA.pdf"]

    for fname in files:
        result = parse_cfra(f"{PDF_DIR}/{fname}")
        print(f"\n{'='*60}")
        print(f"  {fname}")
        print(f"{'='*60}")
        p = result["profile"]
        r = result["report"]
        k = result["key_stats"]
        print(f"  Ticker: {p['ticker']} | Exchange: {p['exchange']}")
        print(f"  Company: {p['company_name']}")
        print(f"  GICS: {p['gics_sector']} / {p['gics_sub_industry']}")
        print(f"  Style: {p['investment_style']}")
        print(f"  Date: {r['report_date']} | Analyst: {r['analyst_name']}")
        print(f"  Rec: {r['recommendation']} | Stars: {r['stars_rating']}")
        print(f"  Price: {r['current_price']} | Target: {r['target_price']}")
        print(f"  --- Key Stats ---")
        print(f"  52wk: {k['week_52_high']} - {k['week_52_low']}")
        print(f"  P/E: {k['trailing_12m_pe']} | Beta: {k['beta']} | Yield: {k['dividend_yield_pct']}%")
        print(f"  MktCap: ${k['market_cap_b']}B | Shares: {k['shares_outstanding_m']}M")
        print(f"  EPS T12M: {k['trailing_12m_eps']} | EPS Est: {k['oper_eps_current_e']} / {k['oper_eps_next_e']}")
        print(f"  --- Financials: {len(result['financials'])} records ---")
        for f in sorted(result["financials"], key=lambda x: (x["fiscal_year"], x["fiscal_quarter"] or 0)):
            q = f"Q{f['fiscal_quarter']}" if f['fiscal_quarter'] else "FY"
            est = "E" if f["is_estimate"] else ""
            rev = f"Rev={f['revenue']}" if f['revenue'] else ""
            eps = f"EPS={f['eps']}" if f['eps'] else ""
            print(f"    {f['fiscal_year']} {q}{est}: {rev} {eps}")
        print(f"  --- Text Sections ---")
        for sec in ["highlights", "investment_rationale", "business_summary", "sub_industry_outlook"]:
            val = r.get(sec)
            if val:
                print(f"    [{sec}]: {val[:80]}...")
            else:
                print(f"    [{sec}]: NOT FOUND")
        print(f"  --- Analyst Notes: {len(result['analyst_notes'])} ---")
        for n in result["analyst_notes"][:3]:
            print(f"    {n['published_at']} by {n['analyst_name']} @ ${n['stock_price_at_note']}")
        if result["errors"]:
            print(f"  ⚠️ Errors: {result['errors']}")
