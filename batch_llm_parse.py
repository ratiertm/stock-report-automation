#!/usr/bin/env python3
"""Batch LLM parse: read pdf_inventory.json, parse pending PDFs, store to DB.

Resumable — tracks progress in pdf_inventory.json.
Run: python batch_llm_parse.py [--limit N] [--source CFRA|Zacks] [--dry-run]
"""

import argparse
import json
import os
import sys
import time
import logging
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv()

from app.database import SessionLocal
from app.services.parser_service import parse_and_store

BASE = Path(os.path.dirname(os.path.abspath(__file__)))
INVENTORY_PATH = BASE / "pdf_inventory.json"
LOG_DIR = BASE / "logs"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def load_inventory() -> dict:
    with open(INVENTORY_PATH, encoding="utf-8") as f:
        return json.load(f)


def save_inventory(inventory: dict):
    with open(INVENTORY_PATH, "w", encoding="utf-8") as f:
        json.dump(inventory, f, indent=2, ensure_ascii=False)


def main():
    parser = argparse.ArgumentParser(description="Batch LLM parse PDFs to DB")
    parser.add_argument("--limit", type=int, default=0, help="Max PDFs to process (0=all)")
    parser.add_argument("--source", type=str, default="", help="Filter by source: CFRA or Zacks")
    parser.add_argument("--date", type=str, default="", help="Filter by download_date: e.g. 2026-03-05")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be processed")
    args = parser.parse_args()

    inventory = load_inventory()
    files = inventory["files"]

    # Filter pending
    pending = [f for f in files if not f["db_synced"]]
    if args.source:
        pending = [f for f in pending if f["source"].upper() == args.source.upper()]
    if args.date:
        pending = [f for f in pending if f["download_date"] == args.date]
    if args.limit > 0:
        pending = pending[:args.limit]

    logger.info("Pending: %d PDFs to process", len(pending))

    if args.dry_run:
        for f in pending[:20]:
            print(f"  {f['ticker']:6s} {f['source']:6s} {f['download_date']:12s} {f['filename']}")
        if len(pending) > 20:
            print(f"  ... and {len(pending) - 20} more")
        return

    # Setup log file
    LOG_DIR.mkdir(exist_ok=True)
    log_file = LOG_DIR / f"batch_parse_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logging.getLogger().addHandler(file_handler)

    logger.info("Log file: %s", log_file)
    logger.info("Processing %d PDFs with LLM parser...", len(pending))

    # Stats
    success = 0
    failed = 0
    skipped = 0
    total_time = 0
    results_log = []

    for i, entry in enumerate(pending):
        pdf_path = BASE / entry["path"]
        if not pdf_path.exists():
            logger.warning("[%d/%d] SKIP - file not found: %s", i+1, len(pending), entry["path"])
            skipped += 1
            continue

        source = entry["source"].upper()
        logger.info("[%d/%d] %s %s (%s)", i+1, len(pending), entry["ticker"], source, entry["filename"])

        t0 = time.time()
        session = SessionLocal()
        try:
            result = parse_and_store(str(pdf_path), source, session, ticker_hint=entry["ticker"])
            elapsed = time.time() - t0
            total_time += elapsed

            if "error" in result:
                logger.error("  FAILED (%.1fs): %s", elapsed, result["error"])
                failed += 1
                results_log.append({
                    "file": entry["filename"],
                    "ticker": entry["ticker"],
                    "source": entry["source"],
                    "status": "failed",
                    "error": result["error"],
                    "time_s": round(elapsed, 1),
                })
            else:
                records = result.get("records_saved", {})
                warnings = result.get("warnings", [])
                parser_used = "regex" if any("regex fallback" in w for w in warnings) else "llm"
                logger.info("  OK (%.1fs) parser=%s records=%s", elapsed, parser_used, records)
                success += 1

                # Update inventory entry
                entry["db_synced"] = True
                entry["db_synced_at"] = datetime.now(timezone.utc).isoformat()
                entry["parser"] = parser_used

                results_log.append({
                    "file": entry["filename"],
                    "ticker": entry["ticker"],
                    "source": entry["source"],
                    "status": "success",
                    "parser": parser_used,
                    "records": records,
                    "time_s": round(elapsed, 1),
                })

        except Exception as e:
            elapsed = time.time() - t0
            total_time += elapsed
            logger.error("  EXCEPTION (%.1fs): %s", elapsed, str(e)[:200])
            failed += 1
            results_log.append({
                "file": entry["filename"],
                "ticker": entry["ticker"],
                "source": entry["source"],
                "status": "exception",
                "error": str(e)[:200],
                "time_s": round(elapsed, 1),
            })
            session.rollback()
        finally:
            session.close()

        # Save inventory every 5 PDFs (for resume capability)
        if (i + 1) % 5 == 0:
            inventory["summary"]["db_synced"] = sum(1 for f in files if f["db_synced"])
            inventory["summary"]["db_pending"] = sum(1 for f in files if not f["db_synced"])
            save_inventory(inventory)

        # Progress
        if (i + 1) % 10 == 0:
            avg_time = total_time / (success + failed) if (success + failed) > 0 else 0
            remaining = (len(pending) - i - 1) * avg_time
            logger.info("--- Progress: %d/%d (ok=%d, fail=%d, skip=%d) avg=%.0fs/pdf ETA=%.0fm ---",
                        i+1, len(pending), success, failed, skipped, avg_time, remaining/60)

    # Final save
    inventory["summary"]["db_synced"] = sum(1 for f in files if f["db_synced"])
    inventory["summary"]["db_pending"] = sum(1 for f in files if not f["db_synced"])
    inventory["summary"]["last_batch_run"] = datetime.now(timezone.utc).isoformat()
    save_inventory(inventory)

    # Summary
    logger.info("=" * 60)
    logger.info("BATCH COMPLETE")
    logger.info("=" * 60)
    logger.info("  Processed: %d", success + failed + skipped)
    logger.info("  Success:   %d", success)
    logger.info("  Failed:    %d", failed)
    logger.info("  Skipped:   %d", skipped)
    logger.info("  Total time: %.0fs (%.1f min)", total_time, total_time / 60)
    if success + failed > 0:
        logger.info("  Avg time:  %.1fs/pdf", total_time / (success + failed))
    logger.info("  Log: %s", log_file)

    # Write results log
    results_path = LOG_DIR / f"batch_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump({
            "run_at": datetime.now(timezone.utc).isoformat(),
            "total": len(pending),
            "success": success,
            "failed": failed,
            "skipped": skipped,
            "total_time_s": round(total_time, 1),
            "results": results_log,
        }, f, indent=2, ensure_ascii=False)
    logger.info("  Results: %s", results_path)


if __name__ == "__main__":
    main()
