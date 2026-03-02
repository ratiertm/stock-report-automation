#!/usr/bin/env python3
"""CLI wrapper for stock report parsers.

Usage:
    python parse_report.py <pdf_path> <source>

Args:
    pdf_path: Path to the PDF file
    source: Report source ("CFRA" or "Zacks")

Output:
    JSON to stdout with keys:
    {profile, report, key_stats, financials, analyst_notes, peers, errors, warnings}

Exit codes:
    0: Success
    1: Invalid arguments
    2: File not found
    3: Unsupported source
    4: Parse error
"""

import sys
import os
import json

# Add parsers directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "parsers"))

from cfra_parser import parse_cfra
from zacks_parser import parse_zacks


PARSERS = {
    "CFRA": parse_cfra,
    "ZACKS": parse_zacks,
}


def main():
    if len(sys.argv) != 3:
        print(json.dumps({
            "errors": ["Usage: python parse_report.py <pdf_path> <source>"],
            "warnings": []
        }))
        sys.exit(1)

    pdf_path = sys.argv[1]
    source = sys.argv[2].upper()

    if not os.path.isfile(pdf_path):
        print(json.dumps({
            "errors": [f"File not found: {pdf_path}"],
            "warnings": []
        }))
        sys.exit(2)

    if source not in PARSERS:
        print(json.dumps({
            "errors": [f"Unsupported source: {source}. Supported: {list(PARSERS.keys())}"],
            "warnings": []
        }))
        sys.exit(3)

    try:
        result = PARSERS[source](pdf_path)
        sys.stdout.reconfigure(encoding='utf-8')
        print(json.dumps(result, ensure_ascii=False, default=str))
        sys.exit(0)
    except Exception as e:
        print(json.dumps({
            "errors": [f"Parse error: {str(e)}"],
            "warnings": []
        }))
        sys.exit(4)


if __name__ == "__main__":
    main()
