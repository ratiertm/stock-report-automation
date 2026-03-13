#!/usr/bin/env python3
"""Run regex parsers on test PDFs and output JSON results."""
import json
import sys
from dataclasses import asdict

sys.path.insert(0, '.')
from cfra_parser import CFRAParser, parse_cfra
from zacks_parser import ZacksParser, parse_zacks

tests = {
    "MSFT-CFRA": ("cfra", "MSFT-CFRA.pdf"),
    "NVDA-CFRA": ("cfra", "NVDA-CFRA.pdf"),
    "AAPL-Zacks": ("zacks", "AAPL-Zacks.pdf"),
}

results = {}
for name, (ptype, fname) in tests.items():
    print(f"Parsing {fname}...", file=sys.stderr)
    if ptype == "cfra":
        r = parse_cfra(fname)
    else:
        r = parse_zacks(fname)
    results[name] = r

print(json.dumps(results, indent=2, default=str))
