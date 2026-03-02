"""Watchlist + Fetch API router."""

import asyncio

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.crud.watchlist import get_or_create_default, add_ticker, remove_ticker, list_tickers, get_fetch_targets
from app.services.fetcher_service import fetch_pdf, batch_fetch
from app.services.parser_service import parse_and_store
from app.config import settings, BASE_DIR

router = APIRouter(prefix="/api")


class TickerRequest(BaseModel):
    ticker: str
    sources: str = "CFRA,ZACKS"


# --- GET /api/watchlist ---

@router.get("/watchlist")
def get_watchlist(db: Session = Depends(get_db)):
    wl = get_or_create_default(db)
    items = list_tickers(db, wl.id)
    return {"watchlist_id": wl.id, "name": wl.name, "items": items, "count": len(items)}


# --- POST /api/watchlist/add ---

@router.post("/watchlist/add")
def watchlist_add(req: TickerRequest, db: Session = Depends(get_db)):
    wl = get_or_create_default(db)
    return add_ticker(db, wl.id, req.ticker, req.sources)


# --- POST /api/watchlist/remove ---

@router.post("/watchlist/remove")
def watchlist_remove(req: TickerRequest, db: Session = Depends(get_db)):
    wl = get_or_create_default(db)
    return remove_ticker(db, wl.id, req.ticker)


# --- POST /api/fetch/{ticker} ---

@router.post("/fetch/{ticker}")
async def fetch_single(ticker: str, source: str = "CFRA"):
    result = await fetch_pdf(ticker, source.upper(), settings.pdf_storage_path)
    if result["status"] == "error":
        raise HTTPException(422, result["error"])
    return result


# --- POST /api/fetch-watchlist ---

@router.post("/fetch-watchlist")
async def fetch_watchlist(db: Session = Depends(get_db)):
    wl = get_or_create_default(db)
    targets = get_fetch_targets(db, wl.id)
    if not targets:
        return {"status": "empty", "message": "No tickers in watchlist"}

    results = await batch_fetch(targets, settings.pdf_storage_path)
    success = sum(1 for r in results if r["status"] == "success")
    return {
        "status": "complete",
        "total": len(targets),
        "success": success,
        "failed": len(targets) - success,
        "results": results,
    }


# --- POST /api/parse-local/{ticker} ---

@router.post("/parse-local/{ticker}")
def parse_local(ticker: str, source: str = "CFRA", db: Session = Depends(get_db)):
    """Parse an already-downloaded PDF from storage."""
    import os
    from datetime import date
    from pathlib import Path

    today = date.today().isoformat()
    t = ticker.upper()
    s = source.upper()
    storage = Path(settings.pdf_storage_path)
    if not storage.is_absolute():
        storage = BASE_DIR / storage
    candidates = [
        storage / today / f"{t}_{s}.pdf",
        storage / f"{t}_{s}.pdf",
        BASE_DIR / f"{t}-{s}.pdf",              # MSFT-CFRA.pdf
        BASE_DIR / f"{t}_{s}.pdf",              # MSFT_CFRA.pdf
        BASE_DIR / f"{t.lower()}.pdf",          # pltr.pdf
        BASE_DIR / f"{t}.pdf",                  # DHR.pdf
        BASE_DIR / f"{t}-{s.capitalize()}.pdf", # AAPL-Zacks.pdf
    ]
    pdf_path = None
    for p in candidates:
        if p.exists():
            pdf_path = p
            break
    if not pdf_path:
        raise HTTPException(404, f"PDF not found for {t} {s}")

    result = parse_and_store(str(pdf_path), source.upper(), db)
    if "error" in result:
        raise HTTPException(422, result["error"])
    return result
