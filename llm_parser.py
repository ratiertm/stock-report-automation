#!/usr/bin/env python3
"""LLM-based PDF Parser — Sends PDF directly to Claude API for structured data extraction.

Drop-in replacement for cfra_parser.py and zacks_parser.py that uses LLM instead of regex.
Returns the same dataclass structures for compatibility with parser_service.py.
"""

import base64
import json
import os
import logging
from typing import Optional

import time

import anthropic

from cfra_parser import (
    CFRAProfile, CFRAReport, CFRAKeyStats, CFRAFinancial,
    CFRABalanceSheet, CFRAAnalystNote, CFRAParseResult,
    safe_decimal, safe_int,
)
from zacks_parser import (
    ZacksProfile, ZacksReport, ZacksKeyStats, ZacksFinancial,
    ZacksPeer, ZacksParseResult,
    safe_decimal as zacks_safe_decimal,
)

logger = logging.getLogger(__name__)

# ─── Prompts ────────────────────────────────────────────────────────────────

CFRA_SYSTEM_PROMPT = """You are a financial data extraction machine. You extract structured data from CFRA Stock Report PDFs into a database schema.

ABSOLUTE RULES — violating any of these is a critical error:
1. NUMBERS: Copy EXACTLY as printed in the PDF. NEVER round, truncate, or recalculate.
   "25.02" → "25.02" (NOT "25.0"). "3.07" → "3.07" (NOT "3.1"). "0.02" → "0.02" (NOT "0.0").
2. PERCENTAGES: Strip the % sign but keep the exact number. "4.12%" → "4.12". "0.02%" → "0.02".
3. TEXT: Copy VERBATIM character-for-character from the PDF. Do NOT summarize, paraphrase, or rewrite.
   Include "Corporate Overview." prefix if it exists. Include bullet markers if they exist.
4. DATES: Always output YYYY-MM-DD format. Convert "Feb 27, 2026" → "2026-02-27".
5. COMPLETENESS: Extract EVERY row from EVERY table. If a table has 10 years, output 10 rows. If 30 financial entries exist, output 30 rows.
6. NULL: Use null for genuinely missing data. NEVER use null for data that exists in the PDF but you failed to find.
7. FORMAT: Return ONLY valid JSON. No markdown, no code blocks, no explanation text."""

CFRA_USER_PROMPT = """Extract ALL data from this CFRA stock report into the exact JSON schema below.

SCHEMA DEFINITION (each section = one database table):

### profile (1 row)
- ticker: Stock symbol only, NO exchange suffix. "BRK.B" → "BRK-B". "AAPL" → "AAPL".
- company_name: Full company name
- exchange: Exchange name exactly as shown (e.g. "NasdaqGS", "NYSE")
- gics_sector: GICS sector (e.g. "Information Technology")
- gics_sub_industry: GICS sub-industry
- investment_style: e.g. "Large-Cap Growth"

### report (1 row)
- report_date: Report date in YYYY-MM-DD
- analyst_name: Full name with credentials (e.g. "Angelo Zino, CFA")
- current_price: Price as shown, exact decimal places
- price_date: Price date in YYYY-MM-DD
- target_price: 12-month target price

### rating (1 row)
- recommendation: One of: "STRONG BUY", "BUY", "HOLD", "SELL", "STRONG SELL"
- stars_rating: Integer 1-5 (count the stars ★)
- risk_assessment: Read from Risk Assessment section. One of: "LOW", "MEDIUM", "HIGH"
- fair_value: Dollar amount from "Fair Value Calculation" on page 3 Quantitative Evaluations
- fair_value_rank: Integer 1-5 from "Fair Value" rank on page 3 (1=greatly overvalued to 5=greatly undervalued)
- volatility: From page 3 Quantitative Evaluations. One of: "LOW", "AVERAGE", "HIGH"
- technical_eval: From page 3. One of: "BULLISH", "NEUTRAL", "BEARISH"
- insider_activity: From page 3 Quantitative Evaluations section — look for the Insider Activity indicator specifically. One of: "FAVORABLE", "NEUTRAL", "UNFAVORABLE". If marked "NA" or not available, use null.
- investment_style: Same as profile.investment_style

### key_stats (1 row) — from "Key Stock Statistics" box on page 1
All values EXACTLY as printed. Do NOT recalculate or round.
- quality_ranking: IMPORTANT — look in the "Key Stock Statistics" box on page 1, right column.
  It appears as "Quality Ranking" followed by a letter grade. Copy the EXACT string: "A+", "A", "A-", "B+", "B", "B-", "C", "D".
  Do NOT confuse with "Fair Value" rank (which is a number 1-5). This is a LETTER grade.
  If the PDF shows "Quality Ranking B+" then output "B+". NEVER return null for this field.
- week_52_high, week_52_low
- trailing_12m_eps: "Trailing 12M EPS"
- trailing_12m_pe: "Trailing 12M P/E"
- market_cap_b: in billions (e.g. "3410.46")
- shares_outstanding_m: in millions
- beta
- eps_cagr_3yr_pct: "3-Yr EPS CAGR"
- institutional_ownership_pct: "% Held by Institutions"
- dividend_yield_pct, dividend_rate
- price_to_sales: From "Expanded Ratio Analysis" table on page 3, most recent year "Price/Sales"
- price_to_ebitda: From page 3, "Price/EBITDA"
- price_to_pretax: From page 3, "Price/Pretax Income"
- oper_eps_current_e: Operating EPS estimate for the FIRST year labeled "E" in the Revenue & Earnings table.
  If columns show "2025" then "2026E" then "2027E", oper_eps_current_e = the "2026E" value.
- oper_eps_next_e: Operating EPS estimate for the SECOND year labeled "E".
  In the example above, oper_eps_next_e = the "2027E" value.
- pe_on_oper_eps_current: "P/E on Oper. EPS" from Key Stock Statistics box — copy exact value

### text_sections (array of objects) — VERBATIM extraction
Copy the ENTIRE text of each section exactly as it appears, character for character.
Include all bullet points, line breaks, and formatting markers.
- {section_type: "highlights", content: "..."}  — from page 1 "Highlights"
- {section_type: "investment_rationale", content: "..."}  — from page 1 "Investment Rationale"
- {section_type: "business_summary", content: "..."}  — from page 2 "Corporate Overview" or "Business Summary"
- {section_type: "sub_industry_outlook", content: "..."}  — from page 4

### financials (array — EVERY row from Revenue & Earnings Data table on page 1)
The table has Revenue row and EPS row for each year. For each YEAR-column:
- Create one row with both revenue and eps merged.
- fiscal_year: integer (e.g. 2024)
- fiscal_quarter: null for annual, 1-4 for quarterly columns
- period_type: "annual" or "quarterly"
- is_estimate: true if the column header has "E" suffix
- revenue: In millions, exact value (e.g. "130497" not "130,497")
- eps: Exact value including negative sign if present
IMPORTANT: Extract ALL columns. Typically 6 year-columns × 5 period-rows = 30 entries.

### balance_sheets (array — ALL years from Balance Sheet & Per Share Data table on page 3)
Typically 10 columns (years). Extract EVERY column as one row.
- fiscal_year, cash, current_assets, total_assets, current_liabilities, long_term_debt
- total_capital, capital_expenditures, cash_from_operations
- current_ratio, ltd_to_cap_pct, net_income_to_revenue_pct, return_on_assets_pct, return_on_equity_pct

### income_statements (array — ALL years from Income Statement Analysis on page 3)
- fiscal_year, revenue, operating_income, depreciation, interest_expense
- pretax_income, effective_tax_rate, net_income, sp_core_eps

### per_share_data (array — ALL years from Per Share Data section on page 3)
- fiscal_year, tangible_book_value, free_cash_flow, earnings, earnings_normalized
- dividends, payout_ratio_pct, price_high, price_low, pe_high, pe_low

### analyst_notes (array — ALL notes from page 5, typically 5-10 entries)
- published_at: YYYY-MM-DD
- analyst_name, title, action (Maintain/Upgrade/Downgrade/Initiate)
- stock_price_at_note, target_price, content (FULL note text verbatim)

OUTPUT FORMAT:
{
  "profile": {"ticker":"","company_name":"","exchange":"","gics_sector":"","gics_sub_industry":"","investment_style":""},
  "report": {"report_date":"","analyst_name":"","current_price":"","price_date":"","target_price":""},
  "rating": {"recommendation":"","stars_rating":0,"risk_assessment":"","fair_value":"","fair_value_rank":0,"volatility":"","technical_eval":"","insider_activity":"","investment_style":""},
  "key_stats": {"quality_ranking":"","week_52_high":"","week_52_low":"","trailing_12m_eps":"","trailing_12m_pe":"","market_cap_b":"","shares_outstanding_m":"","beta":"","eps_cagr_3yr_pct":"","institutional_ownership_pct":"","dividend_yield_pct":"","dividend_rate":"","price_to_sales":"","price_to_ebitda":"","price_to_pretax":"","oper_eps_current_e":"","oper_eps_next_e":"","pe_on_oper_eps_current":""},
  "text_sections": [{"section_type":"","content":""}],
  "financials": [{"fiscal_year":0,"fiscal_quarter":null,"period_type":"","is_estimate":false,"revenue":"","eps":""}],
  "balance_sheets": [{"fiscal_year":0,"cash":"","current_assets":"","total_assets":"","current_liabilities":"","long_term_debt":"","total_capital":"","capital_expenditures":"","cash_from_operations":"","current_ratio":"","ltd_to_cap_pct":"","net_income_to_revenue_pct":"","return_on_assets_pct":"","return_on_equity_pct":""}],
  "income_statements": [{"fiscal_year":0,"revenue":"","operating_income":"","depreciation":"","interest_expense":"","pretax_income":"","effective_tax_rate":"","net_income":"","sp_core_eps":""}],
  "per_share_data": [{"fiscal_year":0,"tangible_book_value":"","free_cash_flow":"","earnings":"","earnings_normalized":"","dividends":"","payout_ratio_pct":"","price_high":"","price_low":"","pe_high":"","pe_low":""}],
  "analyst_notes": [{"published_at":"","analyst_name":"","title":"","action":"","stock_price_at_note":"","target_price":"","content":""}]
}
"""

ZACKS_SYSTEM_PROMPT = """You are a financial data extraction machine. You extract structured data from Zacks Equity Research Report PDFs into a database schema.

ABSOLUTE RULES — violating any of these is a critical error:
1. NUMBERS: Copy EXACTLY as printed in the PDF. NEVER round, truncate, or recalculate.
   "25.02" → "25.02" (NOT "25.0"). "3.07" → "3.07" (NOT "3.1"). "0.02" → "0.02" (NOT "0.0").
2. PERCENTAGES: Strip the % sign but keep the exact number. "4.12%" → "4.12". "0.02%" → "0.02".
3. TEXT: Copy VERBATIM character-for-character from the PDF. Do NOT summarize, paraphrase, or rewrite.
4. DATES: Always output YYYY-MM-DD format. Convert "02/26/2026" → "2026-02-26".
5. COMPLETENESS: Extract EVERY row from EVERY table. Sales & EPS tables each have 3 years × 5 periods = 15 entries per table, merge into 15 rows.
6. NULL: Use null for genuinely missing data. NEVER use null for data that exists in the PDF but you failed to find.
7. FORMAT: Return ONLY valid JSON. No markdown, no code blocks, no explanation text."""

ZACKS_USER_PROMPT = """Extract ALL data from this Zacks stock report into the exact JSON schema below.

SCHEMA DEFINITION (each section = one database table):

### profile (1 row)
- ticker: Stock symbol exactly as shown
- company_name: Full company name
- zacks_industry: From "Industry" field, preserve EXACT original casing from PDF (e.g. "Semiconductor - General" not "semiconductor - general")

### report (1 row)
- report_date: YYYY-MM-DD
- current_price: EXACT value as printed
- price_date: YYYY-MM-DD
- target_price: EXACT value as printed

### rating (1 row)
- recommendation: e.g. "Outperform", "Neutral", "Underperform" — exact text from PDF
- prior_recommendation: Previous recommendation text
- zacks_rank: Integer 1-5
- zacks_rank_label: Full label e.g. "2-Buy", "3-Hold"
- style_scores: {"value":"A","growth":"B","momentum":"C","vgm":"B"} — exact letter grades
- zacks_industry_rank: FULL string e.g. "Bottom 5% (231 out of 243)"

### key_stats (1 row)
PRIORITY: Use the INDUSTRY COMPARISON table on page 8 as the primary source for all metrics
(it has the most precise values with full decimal places). Fall back to page 1 Data Overview only
for fields not in the comparison table (like avg_volume_20d, expected_report_date, eps_esp).
The page 8 table's first data column is the subject company's values.

ALL values EXACTLY as printed. Do NOT round or recalculate.
- week_52_high, week_52_low: From page 1 "52 Week High-Low"
- beta: From page 1 Data Overview, EXACT
- avg_volume_20d: Integer, from page 1 "20 Day Avg Volume"
- ytd_price_change_pct: From page 1 "YTD Price Change"
- pe_forward_12m: From page 8 "P/E (F1)" row, EXACT (e.g. "25.02" NOT "25.0")
- market_cap_b: From page 8 "Market Cap" row, in billions, EXACT
- dividend_yield_pct: From page 8 "Dividend Yield" row, number only without % sign (e.g. "0.02" not "0.02%")
- dividend_rate: From page 1 "Dividend" field, EXACT
- peg_ratio: From page 8 "PEG Ratio" row, EXACT
- price_to_book: From page 8 "Price/Book (P/B)" row, EXACT
- price_to_cashflow: From page 8 "Price/Cash Flow (P/CF)" row, EXACT
- ev_ebitda: From page 8 "EV/EBITDA" row, EXACT
- debt_equity: From page 8 "Debt/Equity" row, EXACT
- cash_per_share: From page 8 "Cash Flow ($/share)" row, EXACT
- earnings_yield_pct: From page 8 "Earnings Yield" row, number only without % sign (e.g. "4.12" not "4.12%")
- earnings_esp_pct: From page 1 "Earnings ESP"
- last_eps_surprise_pct: From page 1 "Last EPS Surprise"
- last_sales_surprise_pct: From page 1 "Last Sales Surprise"
- expected_report_date: From page 1 "Expected Report Date", YYYY-MM-DD
- valuation_multiples: From page 1 summary — {"pe_ttm":"","pe_f1":"","peg_f1":"","ps_ttm":""}

### text_sections (array of objects) — VERBATIM extraction, character for character
Do NOT add section headers that don't exist in the original text.
- {section_type: "reasons_to_buy", content: "..."} — Full text from "Reasons To Buy" pages
- {section_type: "reasons_to_sell", content: "..."} — Full text from "Reasons To Sell" pages
- {section_type: "last_earnings_summary", content: "..."} — Full text from "Last Earnings Report" page
- {section_type: "outlook", content: "..."} — From Outlook section only (no section header prefix)
- {section_type: "business_summary", content: "..."} — From Overview/Summary page 2

### financials (array — merge Sales Estimates + EPS Estimates into unified rows)
The PDF has TWO tables: "Sales Estimates" and "EPS Estimates", each with 3 years × 5 periods (Q1,Q2,Q3,Q4,Annual).
Merge them: for each (year, period) pair, create ONE row with both revenue and eps.
- fiscal_year: Integer
- fiscal_quarter: null for Annual, 1 for Q1, 2 for Q2, 3 for Q3, 4 for Q4
- period_type: "annual" or "quarterly"
- is_estimate: true if cell marked "E", false if marked "A"
- revenue: Sales value in millions, EXACT (e.g. "44062" not "44,062")
- eps: EPS value, EXACT
- eps_surprise_pct: If actual columns show surprise %, extract EXACT
- sales_surprise_pct: If actual columns show surprise %, extract EXACT
Total should be ~15 rows (3 years × 5 periods).

### peers (array — extract from TWO sources, merge into one list)
SOURCE 1: "Top Peers" section on page 7-8. Lists peers as "CompanyName (TICKER) Recommendation".
  Extract: peer_ticker, peer_name, recommendation.
SOURCE 2: Industry Comparison table on page 8. The header row lists tickers as columns.
  The FIRST column is the subject company (skip it). ALL OTHER columns are peers.
  Extract: peer_ticker, rank (from "Zacks Rank" row), and ALL metrics from the table rows.
MERGE: If a peer appears in both sources, combine the data into one entry.
Typically 7-8 peers total. If you only find 3-4, look harder — there are more in the comparison table.
- peer_ticker: Stock symbol
- peer_name: Full company name (from Top Peers section, null if only in comparison table)
- recommendation: Zacks recommendation text (from Top Peers section)
- rank: Zacks rank integer from comparison table "Zacks Rank" row, or null
- metrics: JSON object with ALL comparison metrics from the table, using these exact keys:
  {market_cap, div_yield, ev_ebitda, peg, pb, pcf, pe_f1, ps, earnings_yield, de, cash_share, hist_eps_growth, proj_eps_growth, current_ratio, net_margin, roe, sales_assets}
  ALL values as EXACT strings from PDF. Include metrics for EVERY peer column.

### events (array — ALL items from "Recent News" section, typically page 6)
- event_date: YYYY-MM-DD
- headline: News headline
- content: Full text of the news item

OUTPUT FORMAT:
{
  "profile": {"ticker":"","company_name":"","zacks_industry":""},
  "report": {"report_date":"","current_price":"","price_date":"","target_price":""},
  "rating": {"recommendation":"","prior_recommendation":"","zacks_rank":0,"zacks_rank_label":"","style_scores":{},"zacks_industry_rank":""},
  "key_stats": {"week_52_high":"","week_52_low":"","beta":"","avg_volume_20d":0,"ytd_price_change_pct":"","pe_forward_12m":"","market_cap_b":"","dividend_yield_pct":"","dividend_rate":"","peg_ratio":"","price_to_book":"","price_to_cashflow":"","ev_ebitda":"","debt_equity":"","cash_per_share":"","earnings_yield_pct":"","earnings_esp_pct":"","last_eps_surprise_pct":"","last_sales_surprise_pct":"","expected_report_date":"","valuation_multiples":{}},
  "text_sections": [{"section_type":"","content":""}],
  "financials": [{"fiscal_year":0,"fiscal_quarter":null,"period_type":"","is_estimate":false,"revenue":"","eps":"","eps_surprise_pct":"","sales_surprise_pct":""}],
  "peers": [{"peer_ticker":"","peer_name":"","recommendation":"","rank":null,"metrics":{}}],
  "events": [{"event_date":"","headline":"","content":""}]
}
"""



# ─── API Configuration ──────────────────────────────────────────────────────

LLM_MODEL = os.environ.get("LLM_PARSER_MODEL", "claude-sonnet-4-20250514")
MAX_RETRIES = int(os.environ.get("LLM_PARSER_RETRIES", "3"))
RETRY_DELAY = int(os.environ.get("LLM_PARSER_RETRY_DELAY", "30"))


def _read_pdf_as_base64(filepath: str) -> str:
    """Read PDF file and return base64-encoded string."""
    with open(filepath, "rb") as f:
        return base64.standard_b64encode(f.read()).decode("utf-8")


def _get_anthropic_client() -> anthropic.Anthropic:
    """Get Anthropic client. Checks ANTHROPIC_API_KEY first, then CLI OAuth credentials."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if api_key:
        return anthropic.Anthropic(api_key=api_key)

    # OAuth token from Claude CLI credentials — re-read each call to pick up refreshed tokens
    creds_path = os.path.join(
        os.environ.get("USERPROFILE", os.path.expanduser("~")),
        ".claude", ".credentials.json",
    )
    if not os.path.exists(creds_path):
        raise RuntimeError("No ANTHROPIC_API_KEY or Claude CLI credentials found")

    with open(creds_path) as f:
        creds = json.load(f)

    oauth = creds.get("claudeAiOauth", {})
    api_key = oauth.get("accessToken")
    if not api_key:
        raise RuntimeError("No valid OAuth token found in CLI credentials")

    return anthropic.Anthropic(api_key=api_key)


def _call_llm_with_pdf(system_prompt: str, user_prompt: str, pdf_path: str) -> dict:
    """Call Claude API with PDF file directly. Re-reads OAuth token each attempt."""
    pdf_b64 = _read_pdf_as_base64(pdf_path)

    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        # Re-create client each attempt (picks up refreshed OAuth tokens)
        client = _get_anthropic_client()
        try:
            response = client.messages.create(
                model=LLM_MODEL,
                max_tokens=16384,
                system=system_prompt,
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "document",
                            "source": {
                                "type": "base64",
                                "media_type": "application/pdf",
                                "data": pdf_b64,
                            },
                        },
                        {
                            "type": "text",
                            "text": user_prompt,
                        },
                    ],
                }],
            )

            response_text = response.content[0].text.strip()

            # Strip markdown code blocks if present
            if response_text.startswith("```"):
                lines = response_text.split("\n")
                lines = [l for l in lines if not l.strip().startswith("```")]
                response_text = "\n".join(lines)

            return json.loads(response_text)

        except anthropic.AuthenticationError as e:
            last_error = e
            logger.warning("Auth error (attempt %d/%d): %s", attempt, MAX_RETRIES, str(e)[:100])
            if attempt < MAX_RETRIES:
                time.sleep(5)  # Short delay, then re-read creds on next attempt
            else:
                raise

        except (anthropic.APIConnectionError, anthropic.APIStatusError) as e:
            last_error = e
            if attempt < MAX_RETRIES:
                logger.warning("API error (attempt %d/%d): %s. Retrying in %ds...",
                               attempt, MAX_RETRIES, str(e)[:100], RETRY_DELAY)
                time.sleep(RETRY_DELAY)
            else:
                raise

    raise last_error

# ─── CFRA LLM Parser ────────────────────────────────────────────────────────

class CFRALLMParser:
    """Parse CFRA stock report PDFs using LLM."""

    def parse(self, filepath: str) -> CFRAParseResult:
        result = CFRAParseResult()

        try:
            data = _call_llm_with_pdf(CFRA_SYSTEM_PROMPT, CFRA_USER_PROMPT, filepath)

            # Profile
            p = data.get("profile", {})
            result.profile = CFRAProfile(
                ticker=p.get("ticker"),
                company_name=p.get("company_name"),
                exchange=p.get("exchange"),
                gics_sector=p.get("gics_sector"),
                gics_sub_industry=p.get("gics_sub_industry"),
                investment_style=p.get("investment_style"),
            )

            # Report — merge report + rating + text_sections into CFRAReport
            r = data.get("report", {})
            rat = data.get("rating", {})

            # Stars from rating or infer from recommendation
            stars = rat.get("stars_rating")
            if stars is None:
                rec = rat.get("recommendation", "")
                if rec:
                    stars_map = {"STRONG BUY": 5, "BUY": 4, "HOLD": 3, "SELL": 2, "STRONG SELL": 1}
                    stars = stars_map.get(rec.upper())

            # Build text section lookup
            text_map = {}
            for ts in data.get("text_sections", []):
                text_map[ts.get("section_type", "")] = ts.get("content")

            result.report = CFRAReport(
                source="CFRA",
                report_date=r.get("report_date"),
                analyst_name=r.get("analyst_name"),
                recommendation=rat.get("recommendation"),
                stars_rating=stars,
                target_price=safe_decimal(str(r.get("target_price", ""))) if r.get("target_price") else None,
                current_price=safe_decimal(str(r.get("current_price", ""))) if r.get("current_price") else None,
                price_date=r.get("price_date"),
                risk_assessment=rat.get("risk_assessment"),
                fair_value=safe_decimal(str(rat.get("fair_value", ""))) if rat.get("fair_value") else None,
                fair_value_rank=rat.get("fair_value_rank"),
                volatility=rat.get("volatility"),
                technical_eval=rat.get("technical_eval"),
                insider_activity=rat.get("insider_activity"),
                investment_style=rat.get("investment_style") or p.get("investment_style"),
                highlights=text_map.get("highlights"),
                investment_rationale=text_map.get("investment_rationale"),
                business_summary=text_map.get("business_summary"),
                sub_industry_outlook=text_map.get("sub_industry_outlook"),
            )

            # Key Stats
            ks = data.get("key_stats", {})
            result.key_stats = CFRAKeyStats(
                week_52_high=safe_decimal(str(ks.get("week_52_high", ""))) if ks.get("week_52_high") else None,
                week_52_low=safe_decimal(str(ks.get("week_52_low", ""))) if ks.get("week_52_low") else None,
                trailing_12m_eps=safe_decimal(str(ks.get("trailing_12m_eps", ""))) if ks.get("trailing_12m_eps") else None,
                trailing_12m_pe=safe_decimal(str(ks.get("trailing_12m_pe", ""))) if ks.get("trailing_12m_pe") else None,
                market_cap_b=safe_decimal(str(ks.get("market_cap_b", ""))) if ks.get("market_cap_b") else None,
                shares_outstanding_m=safe_decimal(str(ks.get("shares_outstanding_m", ""))) if ks.get("shares_outstanding_m") else None,
                beta=safe_decimal(str(ks.get("beta", ""))) if ks.get("beta") else None,
                eps_cagr_3yr_pct=safe_decimal(str(ks.get("eps_cagr_3yr_pct", ""))) if ks.get("eps_cagr_3yr_pct") else None,
                institutional_ownership_pct=safe_decimal(str(ks.get("institutional_ownership_pct", ""))) if ks.get("institutional_ownership_pct") else None,
                dividend_yield_pct=safe_decimal(str(ks.get("dividend_yield_pct", ""))) if ks.get("dividend_yield_pct") else None,
                dividend_rate=safe_decimal(str(ks.get("dividend_rate", ""))) if ks.get("dividend_rate") else None,
                price_to_sales=safe_decimal(str(ks.get("price_to_sales", ""))) if ks.get("price_to_sales") else None,
                price_to_ebitda=safe_decimal(str(ks.get("price_to_ebitda", ""))) if ks.get("price_to_ebitda") else None,
                price_to_pretax=safe_decimal(str(ks.get("price_to_pretax", ""))) if ks.get("price_to_pretax") else None,
                quality_ranking=ks.get("quality_ranking") or rat.get("quality_ranking"),
                oper_eps_current_e=safe_decimal(str(ks.get("oper_eps_current_e", ""))) if ks.get("oper_eps_current_e") else None,
                oper_eps_next_e=safe_decimal(str(ks.get("oper_eps_next_e", ""))) if ks.get("oper_eps_next_e") else None,
                pe_on_oper_eps_current=safe_decimal(str(ks.get("pe_on_oper_eps_current", ""))) if ks.get("pe_on_oper_eps_current") else None,
            )

            # Financials
            for f in data.get("financials", []):
                fy = f.get("fiscal_year")
                if not fy:
                    continue
                result.financials.append(CFRAFinancial(
                    fiscal_year=int(fy),
                    fiscal_quarter=f.get("fiscal_quarter"),
                    period_type=f.get("period_type", "annual"),
                    is_estimate=f.get("is_estimate", False),
                    revenue=safe_decimal(str(f.get("revenue", ""))) if f.get("revenue") else None,
                    eps=safe_decimal(str(f.get("eps", ""))) if f.get("eps") else None,
                ))

            # Balance Sheets
            for bs in data.get("balance_sheets", []):
                fy = bs.get("fiscal_year")
                if not fy:
                    continue
                result.balance_sheets.append(CFRABalanceSheet(
                    fiscal_year=int(fy),
                    cash=safe_decimal(str(bs.get("cash", ""))) if bs.get("cash") else None,
                    current_assets=safe_decimal(str(bs.get("current_assets", ""))) if bs.get("current_assets") else None,
                    total_assets=safe_decimal(str(bs.get("total_assets", ""))) if bs.get("total_assets") else None,
                    current_liabilities=safe_decimal(str(bs.get("current_liabilities", ""))) if bs.get("current_liabilities") else None,
                    long_term_debt=safe_decimal(str(bs.get("long_term_debt", ""))) if bs.get("long_term_debt") else None,
                    total_capital=safe_decimal(str(bs.get("total_capital", ""))) if bs.get("total_capital") else None,
                    capital_expenditures=safe_decimal(str(bs.get("capital_expenditures", ""))) if bs.get("capital_expenditures") else None,
                    cash_from_operations=safe_decimal(str(bs.get("cash_from_operations", ""))) if bs.get("cash_from_operations") else None,
                    current_ratio=safe_decimal(str(bs.get("current_ratio", ""))) if bs.get("current_ratio") else None,
                    ltd_to_cap_pct=safe_decimal(str(bs.get("ltd_to_cap_pct", ""))) if bs.get("ltd_to_cap_pct") else None,
                    net_income_to_revenue_pct=safe_decimal(str(bs.get("net_income_to_revenue_pct", ""))) if bs.get("net_income_to_revenue_pct") else None,
                    return_on_assets_pct=safe_decimal(str(bs.get("return_on_assets_pct", ""))) if bs.get("return_on_assets_pct") else None,
                    return_on_equity_pct=safe_decimal(str(bs.get("return_on_equity_pct", ""))) if bs.get("return_on_equity_pct") else None,
                ))

            # Analyst Notes
            for n in data.get("analyst_notes", []):
                result.analyst_notes.append(CFRAAnalystNote(
                    source="CFRA",
                    published_at=n.get("published_at"),
                    analyst_name=n.get("analyst_name"),
                    title=n.get("title"),
                    action=n.get("action"),
                    stock_price_at_note=safe_decimal(str(n.get("stock_price_at_note", ""))) if n.get("stock_price_at_note") else None,
                    target_price=safe_decimal(str(n.get("target_price", ""))) if n.get("target_price") else None,
                    content=n.get("content"),
                ))

        except json.JSONDecodeError as e:
            result.errors.append(f"LLM returned invalid JSON: {e}")
        except RuntimeError as e:
            result.errors.append(f"Claude CLI error: {e}")
        except Exception as e:
            result.errors.append(f"LLM parsing error: {e}")

        return result


# ─── Zacks LLM Parser ───────────────────────────────────────────────────────

class ZacksLLMParser:
    """Parse Zacks stock report PDFs using LLM."""

    def parse(self, filepath: str) -> ZacksParseResult:
        result = ZacksParseResult()

        try:
            data = _call_llm_with_pdf(ZACKS_SYSTEM_PROMPT, ZACKS_USER_PROMPT, filepath)

            # Profile
            p = data.get("profile", {})
            result.profile = ZacksProfile(
                ticker=p.get("ticker"),
                company_name=p.get("company_name"),
                industry=p.get("industry") or p.get("zacks_industry"),
            )

            # Report — merge report + rating + text_sections
            r = data.get("report", {})
            rat = data.get("rating", {})

            # Extract rank number from label like "2-Buy"
            zacks_rank = rat.get("zacks_rank")
            rank_label = rat.get("zacks_rank_label", "")
            if zacks_rank is None and rank_label:
                try:
                    zacks_rank = int(rank_label.split("-")[0])
                except (ValueError, IndexError):
                    pass

            # Build text section lookup
            text_map = {}
            for ts in data.get("text_sections", []):
                text_map[ts.get("section_type", "")] = ts.get("content")

            result.report = ZacksReport(
                source="Zacks",
                report_date=r.get("report_date"),
                recommendation=rat.get("recommendation"),
                prior_recommendation=rat.get("prior_recommendation"),
                zacks_rank=zacks_rank,
                zacks_rank_label=rank_label or rat.get("zacks_rank_label"),
                style_scores=rat.get("style_scores"),
                target_price=zacks_safe_decimal(str(r.get("target_price", ""))) if r.get("target_price") else None,
                current_price=zacks_safe_decimal(str(r.get("current_price", ""))) if r.get("current_price") else None,
                price_date=r.get("price_date"),
                industry_rank=rat.get("zacks_industry_rank") or r.get("industry_rank"),
                reasons_to_buy=text_map.get("reasons_to_buy"),
                reasons_to_sell=text_map.get("reasons_to_sell"),
                last_earnings_summary=text_map.get("last_earnings_summary"),
                outlook=text_map.get("outlook"),
                business_summary=text_map.get("business_summary"),
                recent_news=data.get("events"),  # company_events → recent_news
            )

            # Key Stats
            ks = data.get("key_stats", {})
            result.key_stats = ZacksKeyStats(
                pe_forward_12m=zacks_safe_decimal(str(ks.get("pe_forward_12m", ""))) if ks.get("pe_forward_12m") else None,
                ps_forward_12m=zacks_safe_decimal(str(ks.get("ps_forward_12m", ""))) if ks.get("ps_forward_12m") else None,
                ev_ebitda=zacks_safe_decimal(str(ks.get("ev_ebitda", ""))) if ks.get("ev_ebitda") else None,
                peg_ratio=zacks_safe_decimal(str(ks.get("peg_ratio", ""))) if ks.get("peg_ratio") else None,
                price_to_book=zacks_safe_decimal(str(ks.get("price_to_book", ""))) if ks.get("price_to_book") else None,
                price_to_cashflow=zacks_safe_decimal(str(ks.get("price_to_cashflow", ""))) if ks.get("price_to_cashflow") else None,
                debt_equity=zacks_safe_decimal(str(ks.get("debt_equity", ""))) if ks.get("debt_equity") else None,
                cash_per_share=zacks_safe_decimal(str(ks.get("cash_per_share", ""))) if ks.get("cash_per_share") else None,
                earnings_yield_pct=zacks_safe_decimal(str(ks.get("earnings_yield_pct", ""))) if ks.get("earnings_yield_pct") else None,
                dividend_yield_pct=zacks_safe_decimal(str(ks.get("dividend_yield_pct", ""))) if ks.get("dividend_yield_pct") else None,
                dividend_rate=zacks_safe_decimal(str(ks.get("dividend_rate", ""))) if ks.get("dividend_rate") else None,
                beta=zacks_safe_decimal(str(ks.get("beta", ""))) if ks.get("beta") else None,
                market_cap_b=zacks_safe_decimal(str(ks.get("market_cap_b", ""))) if ks.get("market_cap_b") else None,
                week_52_high=zacks_safe_decimal(str(ks.get("week_52_high", ""))) if ks.get("week_52_high") else None,
                week_52_low=zacks_safe_decimal(str(ks.get("week_52_low", ""))) if ks.get("week_52_low") else None,
                valuation_multiples=ks.get("valuation_multiples"),
            )

            # Financials
            for f in data.get("financials", []):
                fy = f.get("fiscal_year")
                if not fy:
                    continue
                result.financials.append(ZacksFinancial(
                    fiscal_year=int(fy),
                    fiscal_quarter=f.get("fiscal_quarter"),
                    period_type=f.get("period_type", "annual"),
                    is_estimate=f.get("is_estimate", False),
                    revenue=zacks_safe_decimal(str(f.get("revenue", ""))) if f.get("revenue") else None,
                    eps=zacks_safe_decimal(str(f.get("eps", ""))) if f.get("eps") else None,
                    gross_margin_pct=zacks_safe_decimal(str(f.get("gross_margin_pct", ""))) if f.get("gross_margin_pct") else None,
                    operating_margin_pct=zacks_safe_decimal(str(f.get("operating_margin_pct", ""))) if f.get("operating_margin_pct") else None,
                    eps_surprise_pct=zacks_safe_decimal(str(f.get("eps_surprise_pct", ""))) if f.get("eps_surprise_pct") else None,
                    sales_surprise_pct=zacks_safe_decimal(str(f.get("sales_surprise_pct", ""))) if f.get("sales_surprise_pct") else None,
                ))

            # Peers
            for peer in data.get("peers", []):
                result.peers.append(ZacksPeer(
                    peer_ticker=peer.get("peer_ticker"),
                    peer_name=peer.get("peer_name"),
                    recommendation=peer.get("recommendation"),
                    rank=peer.get("rank"),
                    detailed_comparison=peer.get("detailed_comparison"),
                ))

        except json.JSONDecodeError as e:
            result.errors.append(f"LLM returned invalid JSON: {e}")
        except RuntimeError as e:
            result.errors.append(f"Claude CLI error: {e}")
        except Exception as e:
            result.errors.append(f"LLM parsing error: {e}")

        return result


# ─── Convenience functions ───────────────────────────────────────────────────

def parse_cfra_llm(filepath: str) -> CFRAParseResult:
    """Parse a CFRA PDF using LLM."""
    return CFRALLMParser().parse(filepath)


def parse_zacks_llm(filepath: str) -> ZacksParseResult:
    """Parse a Zacks PDF using LLM."""
    return ZacksLLMParser().parse(filepath)
