#!/usr/bin/env python3
"""Run LLM parser on 5 PDFs and compare with regex parser."""

import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv()

from test_llm_parser import test_cfra, test_zacks

if __name__ == "__main__":
    base = os.path.dirname(os.path.abspath(__file__))
    results = []
    start = time.time()

    # 3 CFRA PDFs
    cfra_pdfs = [
        "NVDA-CFRA.pdf",
        "JNJ-CFRA.pdf",
        os.path.join("2026-03-05", "BRK-B_CFRA.pdf"),
    ]

    # 2 Zacks PDFs
    zacks_pdfs = [
        "NVDA-Zacks.pdf",
        os.path.join("2026-03-05", "UNH_ZACKS.pdf"),
    ]

    for pdf in cfra_pdfs:
        path = os.path.join(base, pdf)
        if os.path.exists(path):
            print(f"\n>>> Processing {pdf}...")
            t0 = time.time()
            r = test_cfra(path)
            elapsed = time.time() - t0
            print(f"  Time: {elapsed:.1f}s")
            if r:
                results.append(r)
        else:
            print(f"  SKIP: {pdf} not found")

    for pdf in zacks_pdfs:
        path = os.path.join(base, pdf)
        if os.path.exists(path):
            print(f"\n>>> Processing {pdf}...")
            t0 = time.time()
            r = test_zacks(path)
            elapsed = time.time() - t0
            print(f"  Time: {elapsed:.1f}s")
            if r:
                results.append(r)
        else:
            print(f"  SKIP: {pdf} not found")

    # Summary
    total_time = time.time() - start
    print(f"\n{'='*60}")
    print(f"SUMMARY (5 PDFs, {total_time:.0f}s total)")
    print(f"{'='*60}")
    for r in results:
        print(f"  {r['file']}: {r['overall']:.0f}% accuracy (regex={r['regex_filled']}, llm={r['llm_filled']} fields)")

    if results:
        avg = sum(r['overall'] for r in results) / len(results)
        print(f"\n  Average accuracy: {avg:.0f}%")
        print(f"  Tested: {len(results)}/{len(cfra_pdfs) + len(zacks_pdfs)} PDFs")
