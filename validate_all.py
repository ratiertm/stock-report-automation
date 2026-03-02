#!/usr/bin/env python3
"""Accuracy Validation — Run both parsers on all 9 PDFs, generate accuracy report."""

import json
from cfra_parser import parse_cfra
from zacks_parser import parse_zacks

PDF_DIR = "."

# === Ground Truth (manually verified from PDFs) ===

CFRA_GROUND_TRUTH = {
    "pltr.pdf": {
        "profile": {"ticker": "PLTR", "exchange": "NasdaqGS", "company_name": "Palantir Technologies Inc.",
                     "gics_sector": "Information Technology", "gics_sub_industry": "Application Software",
                     "investment_style": "Large-Cap Blend"},
        "report": {"report_date": "February 21, 2026", "recommendation": "BUY", "stars_rating": 4,
                    "current_price": "135.24", "target_price": "203.00",
                    "analyst_name": "Janice Quek"},
        "key_stats": {"trailing_12m_pe": "180.32", "beta": "1.64", "market_cap_b": "322.61",
                      "shares_outstanding_m": "2391.00", "trailing_12m_eps": "0.75",
                      "week_52_high": "207.52", "week_52_low": "66.12"},
        "financials_count_min": 20,
        "text_sections": ["highlights", "investment_rationale", "business_summary", "sub_industry_outlook"],
    },
    "MSFT-CFRA.pdf": {
        "profile": {"ticker": "MSFT", "exchange": "NasdaqGS", "company_name": "Microsoft Corporation",
                     "gics_sector": "Information Technology", "gics_sub_industry": "Systems Software",
                     "investment_style": "Large-Cap Blend"},
        "report": {"report_date": "February 21, 2026", "recommendation": "STRONG BUY", "stars_rating": 5,
                    "current_price": "397.23", "target_price": "550.00",
                    "analyst_name": "Angelo Zino, CFA"},
        "key_stats": {"trailing_12m_pe": "25.83", "beta": "1.08", "market_cap_b": "2957.73",
                      "dividend_yield_pct": "0.91"},
        "financials_count_min": 20,
        "text_sections": ["highlights", "investment_rationale", "business_summary", "sub_industry_outlook"],
    },
    "JNJ-CFRA.pdf": {
        "profile": {"ticker": "JNJ", "exchange": "NYSE", "company_name": "Johnson & Johnson",
                     "gics_sector": "Health Care", "gics_sub_industry": "Pharmaceuticals",
                     "investment_style": "Large-Cap Value"},
        "report": {"report_date": "February 21, 2026", "recommendation": "HOLD",
                    "current_price": "242.49", "target_price": "225.00"},
        "key_stats": {"trailing_12m_pe": "22.45", "beta": "0.34", "dividend_yield_pct": "2.11"},
        "financials_count_min": 20,
        "text_sections": ["highlights", "investment_rationale", "business_summary", "sub_industry_outlook"],
    },
    "JPM-CFRA.pdf": {
        "profile": {"ticker": "JPM", "exchange": "NYSE", "company_name": "JPMorgan Chase & Co.",
                     "gics_sector": "Financials", "gics_sub_industry": "Diversified Banks",
                     "investment_style": "Large-Cap Blend"},
        "report": {"report_date": "February 21, 2026", "recommendation": "BUY",
                    "current_price": "310.79", "target_price": "340.00"},
        "key_stats": {"trailing_12m_pe": "15.75", "beta": "1.07", "dividend_yield_pct": "1.95"},
        "financials_count_min": 20,
        "text_sections": ["highlights", "investment_rationale", "business_summary", "sub_industry_outlook"],
    },
    "PG-CFRA.pdf": {
        "profile": {"ticker": "PG", "exchange": "NYSE", "company_name": "The Procter & Gamble Company",
                     "gics_sector": "Consumer Staples", "gics_sub_industry": "Household Products",
                     "investment_style": "Large-Cap Value"},
        "report": {"report_date": "February 21, 2026", "recommendation": "SELL",
                    "current_price": "160.78", "target_price": "143.00"},
        "key_stats": {"trailing_12m_pe": "23.34", "beta": "0.37", "dividend_yield_pct": "2.67"},
        "financials_count_min": 20,
        "text_sections": ["highlights", "investment_rationale", "business_summary", "sub_industry_outlook"],
    },
}

ZACKS_GROUND_TRUTH = {
    "DHR.pdf": {
        "profile": {"ticker": "DHR", "company_name": "Danaher Corporation"},
        "report": {"report_date": "February 20, 2026", "recommendation": "Neutral",
                    "prior_recommendation": "Underperform", "zacks_rank": 3,
                    "zacks_rank_label": "Hold",
                    "current_price": "211.25", "target_price": "224.00",
                    "style_scores": {"vgm": "C", "value": "D", "growth": "D", "momentum": "B"}},
        "text_sections": ["reasons_to_buy", "reasons_to_sell", "last_earnings_summary", "outlook"],
        "peers_min": 3,
    },
    "AAPL-Zacks.pdf": {
        "profile": {"ticker": "AAPL", "company_name": "Apple Inc."},
        "report": {"report_date": "February 03, 2026", "recommendation": "Neutral",
                    "prior_recommendation": "Outperform", "zacks_rank": 2,
                    "zacks_rank_label": "Buy",
                    "current_price": "270.01", "target_price": "284.00",
                    "style_scores": {"vgm": "B", "value": "D", "growth": "A", "momentum": "A"}},
        "text_sections": ["reasons_to_buy", "reasons_to_sell", "last_earnings_summary"],
        "peers_min": 3,
    },
    "MSFT-Zacks.pdf": {
        "profile": {"ticker": "MSFT", "company_name": "Microsoft Corporation"},
        "report": {"report_date": "February 27, 2026", "recommendation": "Neutral",
                    "prior_recommendation": "Underperform", "zacks_rank": 3,
                    "zacks_rank_label": "Hold",
                    "current_price": "401.72", "target_price": "422.00",
                    "style_scores": {"vgm": "C", "value": "D", "growth": "C", "momentum": "B"}},
        "text_sections": ["reasons_to_buy", "reasons_to_sell", "last_earnings_summary", "outlook"],
        "peers_min": 3,
    },
    "JPM-Zacks.pdf": {
        "profile": {"ticker": "JPM", "company_name": "JPMorgan Chase & Co."},
        "report": {"report_date": "February 27, 2026", "recommendation": "Neutral",
                    "prior_recommendation": "Outperform", "zacks_rank": 3,
                    "zacks_rank_label": "Hold",
                    "current_price": "306.13", "target_price": "322.00",
                    "style_scores": {"vgm": "B", "value": "C", "growth": "C", "momentum": "A"}},
        "text_sections": ["reasons_to_buy", "reasons_to_sell", "last_earnings_summary", "outlook"],
        "peers_min": 3,
    },
}


def validate_fields(actual: dict, expected: dict, path: str = "") -> list:
    """Compare actual parsed values against expected ground truth."""
    results = []
    for key, exp_val in expected.items():
        act_val = actual.get(key)
        full_key = f"{path}.{key}" if path else key

        if isinstance(exp_val, dict):
            if isinstance(act_val, dict):
                results.extend(validate_fields(act_val, exp_val, full_key))
            else:
                results.append(("FAIL", full_key, f"expected dict, got {type(act_val).__name__}"))
        else:
            if str(act_val) == str(exp_val):
                results.append(("PASS", full_key, str(exp_val)))
            else:
                results.append(("FAIL", full_key, f"expected={exp_val}, got={act_val}"))
    return results


def run_validation():
    """Run full validation suite."""
    total_pass = 0
    total_fail = 0
    total_warn = 0
    report_lines = []

    report_lines.append("=" * 80)
    report_lines.append("  CFRA Parser Accuracy Validation")
    report_lines.append("=" * 80)

    for fname, truth in CFRA_GROUND_TRUTH.items():
        result = parse_cfra(f"{PDF_DIR}/{fname}")
        report_lines.append(f"\n--- {fname} ---")

        # Profile fields
        profile_results = validate_fields(result["profile"], truth["profile"], "profile")
        for status, key, msg in profile_results:
            report_lines.append(f"  {'✅' if status == 'PASS' else '❌'} {key}: {msg}")
            if status == "PASS":
                total_pass += 1
            else:
                total_fail += 1

        # Report fields
        report_results = validate_fields(result["report"], truth["report"], "report")
        for status, key, msg in report_results:
            report_lines.append(f"  {'✅' if status == 'PASS' else '❌'} {key}: {msg}")
            if status == "PASS":
                total_pass += 1
            else:
                total_fail += 1

        # Key Stats
        if "key_stats" in truth:
            ks_results = validate_fields(result["key_stats"], truth["key_stats"], "key_stats")
            for status, key, msg in ks_results:
                report_lines.append(f"  {'✅' if status == 'PASS' else '❌'} {key}: {msg}")
                if status == "PASS":
                    total_pass += 1
                else:
                    total_fail += 1

        # Financials count
        fin_count = len(result["financials"])
        min_count = truth.get("financials_count_min", 0)
        if fin_count >= min_count:
            report_lines.append(f"  ✅ financials_count: {fin_count} (>= {min_count})")
            total_pass += 1
        else:
            report_lines.append(f"  ❌ financials_count: {fin_count} (< {min_count})")
            total_fail += 1

        # Text sections
        for sec in truth.get("text_sections", []):
            val = result["report"].get(sec)
            if val and len(val) > 20:
                report_lines.append(f"  ✅ {sec}: found ({len(val)} chars)")
                total_pass += 1
            else:
                report_lines.append(f"  ⚠️  {sec}: NOT FOUND or too short")
                total_warn += 1

    report_lines.append("\n" + "=" * 80)
    report_lines.append("  Zacks Parser Accuracy Validation")
    report_lines.append("=" * 80)

    for fname, truth in ZACKS_GROUND_TRUTH.items():
        result = parse_zacks(f"{PDF_DIR}/{fname}")
        report_lines.append(f"\n--- {fname} ---")

        # Profile fields
        profile_results = validate_fields(result["profile"], truth["profile"], "profile")
        for status, key, msg in profile_results:
            report_lines.append(f"  {'✅' if status == 'PASS' else '❌'} {key}: {msg}")
            if status == "PASS":
                total_pass += 1
            else:
                total_fail += 1

        # Report fields
        report_results = validate_fields(result["report"], truth["report"], "report")
        for status, key, msg in report_results:
            report_lines.append(f"  {'✅' if status == 'PASS' else '❌'} {key}: {msg}")
            if status == "PASS":
                total_pass += 1
            else:
                total_fail += 1

        # Text sections
        for sec in truth.get("text_sections", []):
            val = result["report"].get(sec)
            if val and len(val) > 20:
                report_lines.append(f"  ✅ {sec}: found ({len(val)} chars)")
                total_pass += 1
            else:
                report_lines.append(f"  ⚠️  {sec}: NOT FOUND or too short")
                total_warn += 1

        # Peers count
        peer_count = len(result["peers"])
        min_peers = truth.get("peers_min", 0)
        if peer_count >= min_peers:
            report_lines.append(f"  ✅ peers_count: {peer_count} (>= {min_peers})")
            total_pass += 1
        else:
            report_lines.append(f"  ⚠️  peers_count: {peer_count} (< {min_peers})")
            total_warn += 1

    # Summary
    total = total_pass + total_fail + total_warn
    accuracy = total_pass / (total_pass + total_fail) * 100 if (total_pass + total_fail) > 0 else 0

    report_lines.append("\n" + "=" * 80)
    report_lines.append("  SUMMARY")
    report_lines.append("=" * 80)
    report_lines.append(f"  Total checks: {total}")
    report_lines.append(f"  ✅ PASS: {total_pass}")
    report_lines.append(f"  ❌ FAIL: {total_fail}")
    report_lines.append(f"  ⚠️  WARN: {total_warn}")
    report_lines.append(f"  Accuracy (PASS/PASS+FAIL): {accuracy:.1f}%")
    report_lines.append(f"  Coverage (PASS+WARN/Total): {(total_pass + total_warn) / total * 100:.1f}%")

    return "\n".join(report_lines)


if __name__ == "__main__":
    report = run_validation()
    print(report)
