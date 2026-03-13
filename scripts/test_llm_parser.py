#!/usr/bin/env python3
"""Compare LLM parser results against regex parser results for accuracy reporting."""

import sys
import os
import json
from dataclasses import asdict

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from cfra_parser import CFRAParser
from zacks_parser import ZacksParser
from llm_parser import CFRALLMParser, ZacksLLMParser


def compare_dicts(regex_data: dict, llm_data: dict, path: str = "") -> list:
    """Compare two dicts recursively, return list of differences."""
    diffs = []
    all_keys = set(list(regex_data.keys()) + list(llm_data.keys()))

    for key in sorted(all_keys):
        full_path = f"{path}.{key}" if path else key
        rv = regex_data.get(key)
        lv = llm_data.get(key)

        # Skip None vs None
        if rv is None and lv is None:
            continue

        # Normalize for comparison
        rv_str = str(rv).strip() if rv is not None else None
        lv_str = str(lv).strip() if lv is not None else None

        if isinstance(rv, dict) and isinstance(lv, dict):
            diffs.extend(compare_dicts(rv, lv, full_path))
        elif isinstance(rv, list) and isinstance(lv, list):
            for i in range(max(len(rv), len(lv))):
                if i >= len(rv):
                    diffs.append((f"{full_path}[{i}]", "MISSING_REGEX", lv[i]))
                elif i >= len(lv):
                    diffs.append((f"{full_path}[{i}]", rv[i], "MISSING_LLM"))
                elif isinstance(rv[i], dict) and isinstance(lv[i], dict):
                    diffs.extend(compare_dicts(rv[i], lv[i], f"{full_path}[{i}]"))
                elif rv_str != lv_str:
                    diffs.append((f"{full_path}[{i}]", rv[i], lv[i]))
        elif rv_str != lv_str:
            diffs.append((full_path, rv, lv))

    return diffs


def count_fields(data: dict) -> tuple:
    """Count total fields and non-null fields."""
    total = 0
    non_null = 0
    for k, v in data.items():
        if isinstance(v, dict):
            t, n = count_fields(v)
            total += t
            non_null += n
        elif isinstance(v, list):
            for item in v:
                if isinstance(item, dict):
                    t, n = count_fields(item)
                    total += t
                    non_null += n
        else:
            total += 1
            if v is not None:
                non_null += 1
    return total, non_null


def test_cfra(pdf_path: str):
    """Test CFRA parser comparison."""
    name = os.path.basename(pdf_path)
    print(f"\n{'='*60}")
    print(f"CFRA: {name}")
    print(f"{'='*60}")

    # Regex parse
    regex_parser = CFRAParser()
    regex_result = regex_parser.parse(pdf_path)
    regex_data = {
        "profile": asdict(regex_result.profile),
        "report": asdict(regex_result.report),
        "key_stats": asdict(regex_result.key_stats),
        "financials": [asdict(f) for f in regex_result.financials],
        "balance_sheets": [asdict(b) for b in regex_result.balance_sheets],
        "analyst_notes": [asdict(n) for n in regex_result.analyst_notes],
    }

    # LLM parse
    llm_parser = CFRALLMParser()
    llm_result = llm_parser.parse(pdf_path)

    if llm_result.errors:
        print(f"  [X] LLM ERRORS: {llm_result.errors}")
        return None

    llm_data = {
        "profile": asdict(llm_result.profile),
        "report": asdict(llm_result.report),
        "key_stats": asdict(llm_result.key_stats),
        "financials": [asdict(f) for f in llm_result.financials],
        "balance_sheets": [asdict(b) for b in llm_result.balance_sheets],
        "analyst_notes": [asdict(n) for n in llm_result.analyst_notes],
    }

    return compare_and_report(regex_data, llm_data, name)


def test_zacks(pdf_path: str):
    """Test Zacks parser comparison."""
    name = os.path.basename(pdf_path)
    print(f"\n{'='*60}")
    print(f"ZACKS: {name}")
    print(f"{'='*60}")

    regex_parser = ZacksParser()
    regex_result = regex_parser.parse(pdf_path)
    regex_data = {
        "profile": asdict(regex_result.profile),
        "report": asdict(regex_result.report),
        "key_stats": asdict(regex_result.key_stats),
        "financials": [asdict(f) for f in regex_result.financials],
        "peers": [asdict(p) for p in regex_result.peers],
    }

    llm_parser = ZacksLLMParser()
    llm_result = llm_parser.parse(pdf_path)

    if llm_result.errors:
        print(f"  [X] LLM ERRORS: {llm_result.errors}")
        return None

    llm_data = {
        "profile": asdict(llm_result.profile),
        "report": asdict(llm_result.report),
        "key_stats": asdict(llm_result.key_stats),
        "financials": [asdict(f) for f in llm_result.financials],
        "peers": [asdict(p) for p in llm_result.peers],
    }

    return compare_and_report(regex_data, llm_data, name)


def compare_and_report(regex_data, llm_data, name):
    """Compare and print report."""
    # Count fields
    regex_total, regex_filled = count_fields(regex_data)
    llm_total, llm_filled = count_fields(llm_data)

    print(f"  Regex: {regex_filled}/{regex_total} fields filled")
    print(f"  LLM:   {llm_filled}/{llm_total} fields filled")

    # Compare key sections
    sections = ["profile", "report", "key_stats"]
    section_results = {}

    for section in sections:
        rd = regex_data.get(section, {})
        ld = llm_data.get(section, {})
        if isinstance(rd, dict) and isinstance(ld, dict):
            diffs = compare_dicts(rd, ld)
            total_keys = len(set(list(rd.keys()) + list(ld.keys())))
            matching = total_keys - len(diffs)
            pct = (matching / total_keys * 100) if total_keys > 0 else 100
            section_results[section] = pct
            print(f"  {section}: {matching}/{total_keys} match ({pct:.0f}%)")
            if diffs:
                for path, rv, lv in diffs[:5]:  # Show first 5 diffs
                    rv_short = str(rv)[:50] if rv else "None"
                    lv_short = str(lv)[:50] if lv else "None"
                    print(f"    != {path}: regex={rv_short} | llm={lv_short}")
                if len(diffs) > 5:
                    print(f"    ... and {len(diffs)-5} more differences")

    # Financials count
    rf = regex_data.get("financials", [])
    lf = llm_data.get("financials", [])
    print(f"  financials: regex={len(rf)} rows, llm={len(lf)} rows")

    # Balance sheets (CFRA)
    if "balance_sheets" in regex_data:
        rb = regex_data.get("balance_sheets", [])
        lb = llm_data.get("balance_sheets", [])
        print(f"  balance_sheets: regex={len(rb)} rows, llm={len(lb)} rows")

    # Peers (Zacks)
    if "peers" in regex_data:
        rp = regex_data.get("peers", [])
        lp = llm_data.get("peers", [])
        print(f"  peers: regex={len(rp)}, llm={len(lp)}")

    overall = sum(section_results.values()) / len(section_results) if section_results else 0
    print(f"  [*] Overall accuracy: {overall:.0f}%")

    return {
        "file": name,
        "sections": section_results,
        "overall": overall,
        "regex_filled": regex_filled,
        "llm_filled": llm_filled,
    }


if __name__ == "__main__":
    base = os.path.dirname(os.path.abspath(__file__))

    results = []

    # CFRA tests
    for pdf in ["MSFT-CFRA.pdf", "NVDA-CFRA.pdf"]:
        path = os.path.join(base, pdf)
        if os.path.exists(path):
            r = test_cfra(path)
            if r:
                results.append(r)

    # Zacks tests
    for pdf in ["AAPL-Zacks.pdf"]:
        path = os.path.join(base, pdf)
        if os.path.exists(path):
            r = test_zacks(path)
            if r:
                results.append(r)

    # Summary
    if results:
        print(f"\n{'='*60}")
        print("SUMMARY")
        print(f"{'='*60}")
        for r in results:
            print(f"  {r['file']}: {r['overall']:.0f}% accuracy (regex={r['regex_filled']}, llm={r['llm_filled']} fields)")
        avg = sum(r['overall'] for r in results) / len(results)
        print(f"\n  Average accuracy: {avg:.0f}%")
