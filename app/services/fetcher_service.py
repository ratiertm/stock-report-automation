"""Fetcher Service: downloads PDF reports from Fidelity Research portal via Playwright."""

import logging
import asyncio
from datetime import date
from pathlib import Path

logger = logging.getLogger(__name__)

# Firm names in the portal dropdown
SOURCE_FIRMS = {
    "CFRA": "CFRA",
    "ZACKS": "Zacks",
}

PORTAL_URL = "https://public.fidelityresearch.com/NationalFinancialNet/MurielSiebert/PageContent"


async def fetch_pdf(ticker: str, source: str, storage_path: str = "./storage/pdfs") -> dict:
    """Download a PDF report from Fidelity Research portal.

    Args:
        ticker: Stock ticker (e.g., "PLTR")
        source: "CFRA" or "ZACKS"
        storage_path: Directory to save PDFs

    Returns:
        {"status": "success", "pdf_path": "...", "ticker": ..., "source": ...}
        or {"status": "error", "error": "...", ...}
    """
    source = source.upper()
    ticker = ticker.upper()
    firm = SOURCE_FIRMS.get(source)
    if not firm:
        return {"status": "error", "error": f"Unknown source: {source}", "ticker": ticker}

    # Ensure storage directory exists
    today = date.today().isoformat()
    save_dir = Path(storage_path) / today
    save_dir.mkdir(parents=True, exist_ok=True)
    pdf_filename = f"{ticker}_{source}.pdf"
    pdf_path = save_dir / pdf_filename

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return {"status": "error", "error": "playwright not installed. Run: pip install playwright && playwright install chromium", "ticker": ticker}

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(accept_downloads=True)
            page = await context.new_page()

            # Step 1: Navigate to portal
            logger.info(f"Navigating to portal for {ticker} {source}")
            await page.goto(PORTAL_URL, wait_until="networkidle", timeout=30000)

            # Step 2: Select Firm from dropdown
            await page.select_option("#selectFirm", label=firm)
            await page.wait_for_timeout(1000)

            # Step 3: Type ticker in search box
            search_input = page.locator("#symbolLookupInput")
            await search_input.fill("")
            await search_input.type(ticker, delay=150)
            await page.wait_for_timeout(3000)

            # Step 4: Select from autocomplete (company match text)
            try:
                match = page.locator(f"text=/{ticker}/i").first
                await match.click(timeout=5000)
                logger.info(f"Clicked autocomplete match for {ticker}")
            except Exception:
                await search_input.press("Enter")
                logger.info(f"No autocomplete match, pressed Enter for {ticker}")
            await page.wait_for_timeout(1000)

            # Step 5: Click Search button
            await page.click("span.searchButton")
            await page.wait_for_timeout(3000)

            # Step 6: Find the report link in results
            report_link = page.locator(".searchReportsResults a.itemReport").first
            try:
                await report_link.wait_for(timeout=10000)
            except Exception:
                await browser.close()
                return {"status": "error", "error": f"No report found for {ticker} {source}", "ticker": ticker, "source": source}

            # Step 7: Get PDF URL and download directly
            href = await report_link.get_attribute("href")
            if href and href.startswith(".."):
                base = PORTAL_URL.rsplit("/", 2)[0]
                pdf_url = base + href.lstrip("..")
            elif href and not href.startswith("http"):
                pdf_url = PORTAL_URL.rsplit("/", 1)[0] + "/" + href
            else:
                pdf_url = href

            logger.info(f"Downloading PDF from {pdf_url}")
            resp = await page.request.get(pdf_url)
            content = await resp.body()

            with open(pdf_path, "wb") as f:
                f.write(content)

            await browser.close()

            if pdf_path.stat().st_size < 1000:
                return {"status": "error", "error": f"PDF too small ({pdf_path.stat().st_size} bytes), likely not a valid report", "ticker": ticker, "source": source}

            logger.info(f"Downloaded {pdf_path} ({pdf_path.stat().st_size} bytes)")
            return {"status": "success", "pdf_path": str(pdf_path), "ticker": ticker, "source": source}

    except Exception as e:
        logger.error(f"Fetch error for {ticker} {source}: {e}")
        return {"status": "error", "error": str(e), "ticker": ticker, "source": source}


async def batch_fetch(targets: list[dict], storage_path: str = "./storage/pdfs", delay: float = 5.0) -> list[dict]:
    """Fetch multiple PDFs sequentially with delay between requests.

    Args:
        targets: list of {"ticker": ..., "source": ...}
        storage_path: PDF storage directory
        delay: seconds between requests (rate limiting)

    Returns:
        list of fetch results
    """
    results = []
    for i, target in enumerate(targets):
        logger.info(f"Fetching {i+1}/{len(targets)}: {target['ticker']} {target['source']}")
        result = await fetch_pdf(target["ticker"], target["source"], storage_path)
        results.append(result)

        # Parse immediately if download succeeded
        if result["status"] == "success":
            try:
                from app.database import SessionLocal
                from app.services.parser_service import parse_and_store
                session = SessionLocal()
                parse_result = parse_and_store(result["pdf_path"], target["source"], session)
                result["parse_status"] = parse_result.get("status")
                result["records_saved"] = parse_result.get("records_saved")
                session.close()
            except Exception as e:
                result["parse_error"] = str(e)

        if i < len(targets) - 1:
            await asyncio.sleep(delay)

    success = sum(1 for r in results if r["status"] == "success")
    logger.info(f"Batch complete: {success}/{len(targets)} successful")
    return results


def fetch_pdf_sync(ticker: str, source: str, storage_path: str = "./storage/pdfs") -> dict:
    """Synchronous wrapper for fetch_pdf."""
    return asyncio.run(fetch_pdf(ticker, source, storage_path))


def batch_fetch_sync(targets: list[dict], storage_path: str = "./storage/pdfs") -> list[dict]:
    """Synchronous wrapper for batch_fetch."""
    return asyncio.run(batch_fetch(targets, storage_path))
