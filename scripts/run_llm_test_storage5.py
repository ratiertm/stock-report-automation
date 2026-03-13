#!/usr/bin/env python3
"""Run LLM parser on 5 storage PDFs, compare with regex, and write log file."""

import sys
import os
import time
import io

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv()

from test_llm_parser import test_cfra, test_zacks

if __name__ == "__main__":
    base = os.path.dirname(os.path.abspath(__file__))
    results = []
    start = time.time()

    # 3 CFRA PDFs from storage
    cfra_pdfs = [
        os.path.join("storage", "pdfs", "2026-03-05", "HD_CFRA.pdf"),
        os.path.join("storage", "pdfs", "2026-03-05", "REGN_CFRA.pdf"),
        os.path.join("storage", "pdfs", "2026-03-05", "EA_CFRA.pdf"),
    ]

    # 2 Zacks PDFs from storage
    zacks_pdfs = [
        os.path.join("storage", "pdfs", "2026-03-05", "BAC_ZACKS.pdf"),
        os.path.join("storage", "pdfs", "2026-03-05", "DAL_ZACKS.pdf"),
    ]

    log_lines = []

    def log(msg=""):
        try:
            print(msg)
        except UnicodeEncodeError:
            print(msg.encode("ascii", "replace").decode())
        log_lines.append(msg)

    for pdf in cfra_pdfs:
        path = os.path.join(base, pdf)
        if os.path.exists(path):
            log(f"\n>>> Processing {pdf}...")
            t0 = time.time()
            # Capture stdout
            old_stdout = sys.stdout
            sys.stdout = buffer = io.StringIO()
            r = test_cfra(path)
            output = buffer.getvalue()
            sys.stdout = old_stdout
            elapsed = time.time() - t0
            # Print and log captured output
            for line in output.splitlines():
                log(line)
            log(f"  Time: {elapsed:.1f}s")
            if r:
                results.append(r)
        else:
            log(f"  SKIP: {pdf} not found")

    for pdf in zacks_pdfs:
        path = os.path.join(base, pdf)
        if os.path.exists(path):
            log(f"\n>>> Processing {pdf}...")
            t0 = time.time()
            old_stdout = sys.stdout
            sys.stdout = buffer = io.StringIO()
            r = test_zacks(path)
            output = buffer.getvalue()
            sys.stdout = old_stdout
            elapsed = time.time() - t0
            for line in output.splitlines():
                log(line)
            log(f"  Time: {elapsed:.1f}s")
            if r:
                results.append(r)
        else:
            log(f"  SKIP: {pdf} not found")

    # Summary
    total_time = time.time() - start
    log(f"\n{'='*60}")
    log(f"SUMMARY (5 PDFs, {total_time:.0f}s total)")
    log(f"{'='*60}")
    for r in results:
        log(f"  {r['file']}: {r['overall']:.0f}% accuracy (regex={r['regex_filled']}, llm={r['llm_filled']} fields)")

    if results:
        avg = sum(r['overall'] for r in results) / len(results)
        log(f"\n  Average accuracy: {avg:.0f}%")
        log(f"  Tested: {len(results)}/{len(cfra_pdfs) + len(zacks_pdfs)} PDFs")

    # Write markdown log
    log_path = os.path.join(base, "LLM_TEST_LOG_2026-03-06.md")
    with open(log_path, "w", encoding="utf-8") as f:
        f.write("# LLM Parser Accuracy Test Log — 2026-03-06\n\n")
        f.write("## Test Config\n\n")
        f.write(f"- **Model**: claude-sonnet-4-20250514 (via Anthropic API, PDF direct upload)\n")
        f.write(f"- **Parser**: LLM as default, regex as baseline for comparison\n")
        f.write(f"- **PDFs**: 5 files from `storage/pdfs/2026-03-05/`\n")
        f.write(f"  - CFRA: HD, REGN, EA\n")
        f.write(f"  - Zacks: BAC, DAL\n")
        f.write(f"- **Total time**: {total_time:.0f}s\n\n")
        f.write("## Results\n\n")
        f.write("```\n")
        f.write("\n".join(log_lines))
        f.write("\n```\n\n")

        if results:
            f.write("## Summary Table\n\n")
            f.write("| PDF | Source | Accuracy | Regex Fields | LLM Fields | Profile | Report | Key Stats |\n")
            f.write("|-----|--------|----------|--------------|------------|---------|--------|-----------|\n")
            for r in results:
                s = r.get("sections", {})
                f.write(f"| {r['file']} | {'CFRA' if 'CFRA' in r['file'] else 'Zacks'} ")
                f.write(f"| {r['overall']:.0f}% | {r['regex_filled']} | {r['llm_filled']} ")
                f.write(f"| {s.get('profile', 0):.0f}% | {s.get('report', 0):.0f}% | {s.get('key_stats', 0):.0f}% |\n")

            avg = sum(r['overall'] for r in results) / len(results)
            f.write(f"\n**Average accuracy: {avg:.0f}%** ({len(results)}/{len(cfra_pdfs) + len(zacks_pdfs)} PDFs)\n")

    print(f"\nLog written to: {log_path}")
