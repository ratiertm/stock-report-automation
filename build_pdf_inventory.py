#!/usr/bin/env python3
"""Scan all PDFs, check DB status, and generate pdf_inventory.json."""

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv()

from app.database import SessionLocal
from app.models.stock_report import StockReport
from app.models.stock_profile import StockProfile

BASE = Path(os.path.dirname(os.path.abspath(__file__)))
STORAGE = BASE / "storage" / "pdfs"

# Filename patterns: TICKER_SOURCE.pdf or TICKER-SOURCE.pdf
PATTERN_UNDERSCORE = re.compile(r'^([A-Z0-9\-]+)_(CFRA|ZACKS)\.pdf$', re.IGNORECASE)
PATTERN_DASH = re.compile(r'^([A-Za-z0-9\-]+)-(CFRA|Zacks|ZACKS)\.pdf$')
PATTERN_BARE = re.compile(r'^([a-z]+)\.pdf$')  # e.g. pltr.pdf


def parse_filename(filename: str) -> tuple:
    """Extract (ticker, source) from PDF filename."""
    m = PATTERN_UNDERSCORE.match(filename)
    if m:
        ticker = m.group(1).upper()
        source = "CFRA" if m.group(2).upper() == "CFRA" else "Zacks"
        return ticker, source

    m = PATTERN_DASH.match(filename)
    if m:
        ticker = m.group(1).upper()
        source = "CFRA" if m.group(2).upper() == "CFRA" else "Zacks"
        return ticker, source

    m = PATTERN_BARE.match(filename)
    if m:
        return m.group(1).upper(), "CFRA"  # bare names are CFRA (e.g. pltr.pdf)

    return None, None


def scan_pdfs() -> list:
    """Scan all PDF locations and return list of entries."""
    entries = []
    seen = set()

    # 1. storage/pdfs/YYYY-MM-DD/*.pdf
    if STORAGE.exists():
        for date_dir in sorted(STORAGE.iterdir()):
            if date_dir.is_dir() and re.match(r'^\d{4}-\d{2}-\d{2}$', date_dir.name):
                for pdf in sorted(date_dir.glob("*.pdf")):
                    ticker, source = parse_filename(pdf.name)
                    if ticker:
                        key = f"{ticker}_{source}_{date_dir.name}"
                        if key not in seen:
                            seen.add(key)
                            entries.append({
                                "ticker": ticker,
                                "source": source,
                                "filename": pdf.name,
                                "path": str(pdf.relative_to(BASE)),
                                "download_date": date_dir.name,
                                "file_size_kb": round(pdf.stat().st_size / 1024, 1),
                                "db_synced": None,
                                "db_synced_at": None,
                                "parser": None,
                            })

    # 2. storage/pdfs/legacy/*.pdf (moved from project root)
    legacy_dir = STORAGE / "legacy"
    if legacy_dir.exists():
        for pdf in sorted(legacy_dir.glob("*.pdf")):
            ticker, source = parse_filename(pdf.name)
            if ticker:
                key = f"{ticker}_{source}_legacy"
                if key not in seen:
                    seen.add(key)
                    entries.append({
                        "ticker": ticker,
                        "source": source,
                        "filename": pdf.name,
                        "path": str(pdf.relative_to(BASE)),
                        "download_date": "legacy",
                        "file_size_kb": round(pdf.stat().st_size / 1024, 1),
                        "db_synced": None,
                        "db_synced_at": None,
                        "parser": None,
                    })

    return entries


def check_db_status(entries: list):
    """Check which PDFs have matching reports in DB."""
    session = SessionLocal()
    try:
        # Load all profiles and reports
        profiles = {p.ticker: p for p in session.query(StockProfile).all()}
        reports = session.query(StockReport).all()

        # Build lookup: (ticker, source) -> latest report
        report_map = {}
        for r in reports:
            profile = profiles.get(next(
                (t for t, p in profiles.items() if p.id == r.stock_profile_id), None
            ))
            if profile:
                key = (profile.ticker, r.source)
                if key not in report_map or (r.created_at and (
                    report_map[key].created_at is None or r.created_at > report_map[key].created_at
                )):
                    report_map[key] = r

        # Mark entries
        for entry in entries:
            key = (entry["ticker"], entry["source"])
            if key in report_map:
                r = report_map[key]
                entry["db_synced"] = True
                entry["db_synced_at"] = r.created_at.isoformat() if r.created_at else None
                entry["parser"] = "regex"  # All existing DB data is from regex
            else:
                entry["db_synced"] = False

        print(f"  DB: {len(profiles)} profiles, {len(reports)} reports")
        synced = sum(1 for e in entries if e["db_synced"])
        print(f"  Matched: {synced}/{len(entries)} PDFs have DB records")

    finally:
        session.close()


def main():
    print("Scanning PDFs...")
    entries = scan_pdfs()
    print(f"  Found: {len(entries)} PDFs")

    # Stats
    sources = {}
    dates = {}
    for e in entries:
        sources[e["source"]] = sources.get(e["source"], 0) + 1
        dates[e["download_date"]] = dates.get(e["download_date"], 0) + 1

    for s, c in sorted(sources.items()):
        print(f"    {s}: {c}")
    for d, c in sorted(dates.items()):
        print(f"    {d}: {c}")

    print("\nChecking DB status...")
    check_db_status(entries)

    # Unique tickers
    tickers = sorted(set(e["ticker"] for e in entries))

    # Build output
    inventory = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "total_pdfs": len(entries),
            "unique_tickers": len(tickers),
            "by_source": sources,
            "by_date": dates,
            "db_synced": sum(1 for e in entries if e["db_synced"]),
            "db_pending": sum(1 for e in entries if not e["db_synced"]),
        },
        "tickers": tickers,
        "files": entries,
    }

    out_path = BASE / "pdf_inventory.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(inventory, f, indent=2, ensure_ascii=False)

    print(f"\nWritten to: {out_path}")
    print(f"  Total: {inventory['summary']['total_pdfs']} PDFs, {inventory['summary']['unique_tickers']} tickers")
    print(f"  DB synced: {inventory['summary']['db_synced']}, pending: {inventory['summary']['db_pending']}")


if __name__ == "__main__":
    main()
