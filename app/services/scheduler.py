"""APScheduler: scheduled report fetching from watchlist."""

import logging
from apscheduler.schedulers.background import BackgroundScheduler

from app.config import settings

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()


def daily_fetch_job():
    """Fetch all reports for the default watchlist."""
    from app.database import SessionLocal
    from app.crud.watchlist import get_or_create_default, get_fetch_targets
    from app.services.fetcher_service import batch_fetch_sync

    logger.info("Starting daily fetch job")
    session = SessionLocal()
    try:
        wl = get_or_create_default(session)
        targets = get_fetch_targets(session, wl.id)
        if not targets:
            logger.info("No tickers in watchlist, skipping")
            return

        logger.info(f"Fetching {len(targets)} reports")
        results = batch_fetch_sync(targets, settings.pdf_storage_path)
        success = sum(1 for r in results if r["status"] == "success")
        logger.info(f"Daily fetch complete: {success}/{len(targets)} successful")
    except Exception as e:
        logger.error(f"Daily fetch error: {e}")
    finally:
        session.close()


def start_scheduler():
    """Start the scheduler if enabled in settings."""
    if not settings.scheduler_enabled:
        logger.info("Scheduler disabled")
        return

    scheduler.add_job(
        daily_fetch_job,
        "cron",
        hour=settings.scheduler_cron_hour,
        minute=0,
        id="daily_fetch",
        replace_existing=True,
    )
    scheduler.start()
    logger.info(f"Scheduler started: daily fetch at {settings.scheduler_cron_hour}:00")


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")
