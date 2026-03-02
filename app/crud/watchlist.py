"""CRUD operations for Watchlist."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Watchlist, WatchlistItem, StockProfile


def get_or_create_default(session: Session) -> Watchlist:
    wl = session.execute(
        select(Watchlist).where(Watchlist.is_default == True)
    ).scalar_one_or_none()
    if not wl:
        wl = Watchlist(name="Default", is_default=True)
        session.add(wl)
        session.flush()
    return wl


def add_ticker(session: Session, watchlist_id: int, ticker: str, sources: str = "CFRA,ZACKS") -> dict:
    profile = session.execute(
        select(StockProfile).where(StockProfile.ticker == ticker.upper())
    ).scalar_one_or_none()
    if not profile:
        # Create stub profile
        profile = StockProfile(ticker=ticker.upper(), exchange="UNKNOWN")
        session.add(profile)
        session.flush()

    existing = session.execute(
        select(WatchlistItem).where(
            WatchlistItem.watchlist_id == watchlist_id,
            WatchlistItem.stock_profile_id == profile.id,
        )
    ).scalar_one_or_none()
    if existing:
        return {"status": "already_exists", "ticker": ticker.upper()}

    item = WatchlistItem(
        watchlist_id=watchlist_id,
        stock_profile_id=profile.id,
        sources=sources,
    )
    session.add(item)
    session.commit()
    return {"status": "added", "ticker": ticker.upper()}


def remove_ticker(session: Session, watchlist_id: int, ticker: str) -> dict:
    profile = session.execute(
        select(StockProfile).where(StockProfile.ticker == ticker.upper())
    ).scalar_one_or_none()
    if not profile:
        return {"status": "not_found", "ticker": ticker.upper()}

    deleted = session.query(WatchlistItem).filter(
        WatchlistItem.watchlist_id == watchlist_id,
        WatchlistItem.stock_profile_id == profile.id,
    ).delete()
    session.commit()
    return {"status": "removed" if deleted else "not_found", "ticker": ticker.upper()}


def list_tickers(session: Session, watchlist_id: int) -> list[dict]:
    items = session.execute(
        select(WatchlistItem, StockProfile)
        .join(StockProfile, WatchlistItem.stock_profile_id == StockProfile.id)
        .where(WatchlistItem.watchlist_id == watchlist_id)
        .order_by(StockProfile.ticker)
    ).all()
    return [
        {"ticker": p.ticker, "company_name": p.company_name, "sources": wi.sources}
        for wi, p in items
    ]


def get_fetch_targets(session: Session, watchlist_id: int) -> list[dict]:
    """Get (ticker, source) pairs for batch fetching."""
    items = list_tickers(session, watchlist_id)
    targets = []
    for item in items:
        for source in (item["sources"] or "CFRA,ZACKS").split(","):
            targets.append({"ticker": item["ticker"], "source": source.strip()})
    return targets
