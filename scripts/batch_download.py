#!/usr/bin/env python3
"""Batch download CFRA/Zacks reports for S&P 500 and NASDAQ 100 tickers.

Usage:
    python batch_download.py --list all --source both
    python batch_download.py --list sp500 --source cfra --dry-run
    python batch_download.py --list nasdaq100 --source zacks
"""

import argparse
import asyncio
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from app.services.fetcher_service import batch_fetch

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(f"batch_download_{datetime.now():%Y%m%d_%H%M%S}.log"),
    ],
)
logger = logging.getLogger(__name__)

TICKER_DIR = Path(__file__).parent
TICKER_FILES = {
    "sp500": TICKER_DIR / "tickers_sp500.txt",
    "nasdaq100": TICKER_DIR / "tickers_nasdaq100.txt",
    "all": TICKER_DIR / "tickers_all.txt",
}


def load_tickers(list_name: str) -> list[str]:
    """Load tickers from file."""
    path = TICKER_FILES[list_name]
    if not path.exists():
        logger.error(f"Ticker file not found: {path}")
        sys.exit(1)
    tickers = [line.strip() for line in path.read_text().splitlines() if line.strip()]
    logger.info(f"Loaded {len(tickers)} tickers from {path.name}")
    return tickers


def build_targets(tickers: list[str], source: str) -> list[dict]:
    """Build fetch target list from tickers and source option."""
    targets = []
    sources = ["CFRA", "ZACKS"] if source == "both" else [source.upper()]
    for ticker in tickers:
        for src in sources:
            targets.append({"ticker": ticker, "source": src})
    return targets


async def run(args):
    tickers = load_tickers(args.list)
    targets = build_targets(tickers, args.source)

    logger.info(f"List: {args.list} | Source: {args.source} | Tickers: {len(tickers)} | Jobs: {len(targets)}")

    if args.dry_run:
        print(f"\n{'='*60}")
        print(f"DRY RUN — {len(targets)} downloads would be performed:")
        print(f"{'='*60}")
        for i, t in enumerate(targets, 1):
            print(f"  {i:4d}. {t['ticker']:6s} — {t['source']}")
        print(f"{'='*60}")
        return

    start = time.time()
    results = await batch_fetch(targets, storage_path=args.storage, delay=args.delay)
    elapsed = time.time() - start

    # Summary
    success = [r for r in results if r["status"] == "success"]
    errors = [r for r in results if r["status"] == "error"]

    print(f"\n{'='*60}")
    print(f"BATCH COMPLETE — {len(success)}/{len(results)} successful ({elapsed:.0f}s)")
    print(f"{'='*60}")

    if errors:
        fail_log = TICKER_DIR / f"batch_failures_{datetime.now():%Y%m%d_%H%M%S}.log"
        with open(fail_log, "w") as f:
            for r in errors:
                line = f"{r.get('ticker','?')}\t{r.get('source','?')}\t{r.get('error','unknown')}"
                f.write(line + "\n")
                logger.warning(f"FAIL: {line}")
        print(f"Failures logged to: {fail_log}")


def main():
    parser = argparse.ArgumentParser(description="Batch download stock reports")
    parser.add_argument("--list", choices=["sp500", "nasdaq100", "all"], default="all",
                        help="Ticker list to use (default: all)")
    parser.add_argument("--source", choices=["cfra", "zacks", "both"], default="both",
                        help="Report source (default: both)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print download plan without fetching")
    parser.add_argument("--storage", default="./storage/pdfs",
                        help="PDF storage directory (default: ./storage/pdfs)")
    parser.add_argument("--delay", type=float, default=5.0,
                        help="Delay between requests in seconds (default: 5.0)")
    args = parser.parse_args()

    asyncio.run(run(args))


if __name__ == "__main__":
    main()
