#!/usr/bin/env python3
"""Fetch only NEW/UPDATED reports from Fidelity Research portal.

Compares portal report dates against DB, downloads only newer ones.
Usage:
    python fetch_updates.py                    # All tickers in DB
    python fetch_updates.py --tickers AAPL MSFT NVDA  # Specific tickers
    python fetch_updates.py --source CFRA      # One source only
    python fetch_updates.py --dry-run          # Show what would be fetched
    python fetch_updates.py --limit 10         # Max downloads
"""

import argparse
import asyncio
import json
import logging
import os
import sys
import time
import random
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv()

from app.database import SessionLocal
from app.models.stock_profile import StockProfile
from app.models.stock_report import StockReport
from app.services.parser_service import parse_and_store
from sqlalchemy import select, and_, func

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

BASE = Path(os.path.dirname(os.path.abspath(__file__)))
STORAGE = BASE / "storage" / "pdfs"
SOURCES = ["CFRA", "ZACKS"]


def get_db_latest_dates() -> dict:
    """Get latest report_date per (ticker, source) from DB.

    Returns: {("AAPL", "CFRA"): date(2026, 2, 28), ...}
    """
    session = SessionLocal()
    try:
        rows = session.execute(
            select(
                StockProfile.ticker,
                StockReport.source,
                func.max(StockReport.report_date).label("latest_date"),
            )
            .join(StockReport, StockProfile.id == StockReport.stock_profile_id)
            .group_by(StockProfile.ticker, StockReport.source)
        ).all()
        return {(r.ticker, r.source.upper()): r.latest_date for r in rows}
    finally:
        session.close()


def get_all_tickers() -> list[str]:
    """Get all tickers from DB."""
    session = SessionLocal()
    try:
        rows = session.execute(
            select(StockProfile.ticker).order_by(StockProfile.ticker)
        ).all()
        return [r.ticker for r in rows]
    finally:
        session.close()


async def check_report_date(page, ticker: str, source: str) -> dict:
    """Check report date on the portal without downloading.

    Returns: {"ticker", "source", "has_report", "report_date_text", "href"}
    """
    from playwright.async_api import TimeoutError as PlaywrightTimeout

    firm_map = {"CFRA": "CFRA", "ZACKS": "Zacks"}
    firm = firm_map.get(source)

    portal_url = "https://public.fidelityresearch.com/NationalFinancialNet/MurielSiebert/PageContent"

    try:
        await page.goto(portal_url, wait_until="networkidle", timeout=30000)
        await page.select_option("#selectFirm", label=firm)
        await page.wait_for_timeout(800)

        search_input = page.locator("#symbolLookupInput")
        await search_input.fill("")
        await search_input.type(ticker, delay=100)
        await page.wait_for_timeout(2500)

        # Click autocomplete or press enter
        try:
            match = page.locator(f"text=/{ticker}/i").first
            await match.click(timeout=3000)
        except Exception:
            await search_input.press("Enter")

        await page.wait_for_timeout(800)
        await page.click("span.searchButton")
        await page.wait_for_timeout(2500)

        # Check results
        report_link = page.locator(".searchReportsResults a.itemReport").first
        try:
            await report_link.wait_for(timeout=8000)
        except (PlaywrightTimeout, Exception):
            return {"ticker": ticker, "source": source, "has_report": False}

        # Get report date text (usually near the link)
        href = await report_link.get_attribute("href") or ""
        report_text = await report_link.inner_text()

        # Try to find date in the results area
        date_text = ""
        try:
            date_el = page.locator(".searchReportsResults .itemDate, .searchReportsResults .reportDate").first
            date_text = await date_el.inner_text(timeout=2000)
        except Exception:
            pass

        return {
            "ticker": ticker,
            "source": source,
            "has_report": True,
            "report_text": report_text.strip(),
            "date_text": date_text.strip(),
            "href": href,
        }

    except Exception as e:
        return {"ticker": ticker, "source": source, "has_report": False, "error": str(e)[:100]}


async def fetch_and_parse(page, ticker: str, source: str) -> dict:
    """Download PDF and parse to DB."""
    from playwright.async_api import TimeoutError as PlaywrightTimeout

    firm_map = {"CFRA": "CFRA", "ZACKS": "Zacks"}
    firm = firm_map.get(source)
    portal_url = "https://public.fidelityresearch.com/NationalFinancialNet/MurielSiebert/PageContent"

    today = date.today().isoformat()
    save_dir = STORAGE / today
    save_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = save_dir / f"{ticker}_{source}.pdf"

    try:
        await page.goto(portal_url, wait_until="networkidle", timeout=30000)
        await page.select_option("#selectFirm", label=firm)
        await page.wait_for_timeout(800)

        search_input = page.locator("#symbolLookupInput")
        await search_input.fill("")
        await search_input.type(ticker, delay=100)
        await page.wait_for_timeout(2500)

        try:
            match = page.locator(f"text=/{ticker}/i").first
            await match.click(timeout=3000)
        except Exception:
            await search_input.press("Enter")

        await page.wait_for_timeout(800)
        await page.click("span.searchButton")
        await page.wait_for_timeout(2500)

        report_link = page.locator(".searchReportsResults a.itemReport").first
        try:
            await report_link.wait_for(timeout=8000)
        except (PlaywrightTimeout, Exception):
            return {"status": "error", "error": "No report found", "ticker": ticker, "source": source}

        # Download PDF
        href = await report_link.get_attribute("href")
        if href and href.startswith(".."):
            base = portal_url.rsplit("/", 2)[0]
            pdf_url = base + href.lstrip("..")
        elif href and not href.startswith("http"):
            pdf_url = portal_url.rsplit("/", 1)[0] + "/" + href
        else:
            pdf_url = href

        resp = await page.request.get(pdf_url)
        content = await resp.body()

        with open(pdf_path, "wb") as f:
            f.write(content)

        if pdf_path.stat().st_size < 1000:
            return {"status": "error", "error": "PDF too small", "ticker": ticker, "source": source}

        # Parse and store
        session = SessionLocal()
        try:
            result = parse_and_store(str(pdf_path), source, session, ticker_hint=ticker)
            return {
                "status": result.get("status", "error"),
                "ticker": ticker,
                "source": source,
                "pdf_path": str(pdf_path),
                "report_date": result.get("report_date"),
                "records": result.get("records_saved"),
                "error": result.get("error"),
            }
        finally:
            session.close()

    except Exception as e:
        return {"status": "error", "error": str(e)[:200], "ticker": ticker, "source": source}


def filter_by_since(targets: list, since_date: date) -> list:
    """Filter targets: only include those whose DB report_date < since_date (or missing)."""
    db_dates = get_db_latest_dates()
    filtered = []
    for ticker, source in targets:
        db_date = db_dates.get((ticker, source))
        if db_date is None or db_date < since_date:
            filtered.append((ticker, source))
    return filtered


async def run(args):
    from playwright.async_api import async_playwright

    # Get tickers
    if args.tickers:
        tickers = [t.upper() for t in args.tickers]
    else:
        tickers = get_all_tickers()

    # Get sources
    sources = [args.source.upper()] if args.source else SOURCES

    # Build targets
    targets = [(t, s) for t in tickers for s in sources]

    # Filter by --since (only fetch if DB report_date < since_date)
    if args.since:
        since_date = date.fromisoformat(args.since)
        before = len(targets)
        targets = filter_by_since(targets, since_date)
        logger.info("--since %s: %d -> %d targets (skipped %d up-to-date)",
                    args.since, before, len(targets), before - len(targets))

    random.shuffle(targets)

    if args.limit > 0:
        targets = targets[:args.limit]

    logger.info("Targets: %d (%d tickers x %d sources)", len(targets), len(tickers), len(sources))

    if args.dry_run:
        for t, s in sorted(targets)[:50]:
            print(f"  {t:8s} {s}")
        if len(targets) > 50:
            print(f"  ... and {len(targets) - 50} more")
        return

    # Setup log
    log_dir = BASE / "logs"
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / f"fetch_updates_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logging.getLogger().addHandler(file_handler)

    success = 0
    skipped = 0
    failed = 0
    results = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(accept_downloads=True)
        page = await context.new_page()

        for i, (ticker, source) in enumerate(targets):
            # Human-like random delay
            if i > 0:
                r = random.random()
                if r < 0.05:
                    # 5%: long pause (coffee break)
                    delay = random.uniform(60, 120)
                elif r < 0.20:
                    # 15%: medium pause
                    delay = random.uniform(25, 50)
                else:
                    # 80%: normal browsing pace
                    delay = random.uniform(10, 25)
                # Add gaussian jitter
                delay += random.gauss(0, 2)
                delay = max(8, delay)
                await asyncio.sleep(delay)

            logger.info("[%d/%d] %s %s", i+1, len(targets), ticker, source)

            t0 = time.time()
            result = await fetch_and_parse(page, ticker, source)
            elapsed = time.time() - t0

            if result.get("status") == "success":
                success += 1
                logger.info("  OK (%.0fs) report_date=%s records=%s",
                           elapsed, result.get("report_date"), result.get("records"))
            else:
                failed += 1
                logger.warning("  FAIL (%.0fs) %s", elapsed, result.get("error", "")[:80])

            results.append(result)

            # Progress
            if (i + 1) % 10 == 0:
                logger.info("--- Progress: %d/%d (ok=%d fail=%d) ---",
                           i+1, len(targets), success, failed)

        await browser.close()

    # Summary
    logger.info("=" * 50)
    logger.info("COMPLETE: ok=%d fail=%d total=%d", success, failed, len(targets))
    logger.info("Log: %s", log_file)

    # Update inventory
    try:
        import subprocess
        subprocess.run([sys.executable, "build_pdf_inventory.py"],
                      capture_output=True, timeout=60)
        logger.info("Inventory updated")
    except Exception:
        pass


def main():
    parser = argparse.ArgumentParser(description="Fetch latest reports from Fidelity")
    parser.add_argument("--tickers", nargs="+", help="Specific tickers (default: all in DB)")
    parser.add_argument("--source", type=str, help="CFRA or ZACKS (default: both)")
    parser.add_argument("--since", type=str, help="Only fetch if DB report_date < this date (YYYY-MM-DD)")
    parser.add_argument("--limit", type=int, default=0, help="Max downloads (0=all)")
    parser.add_argument("--dry-run", action="store_true", help="Show targets without fetching")
    args = parser.parse_args()

    asyncio.run(run(args))


if __name__ == "__main__":
    main()
