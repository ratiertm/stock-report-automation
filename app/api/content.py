"""Content + Alert API router."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.content_service import to_content_vars, detect_changes
from app.services.alert_service import check_and_alert, get_pending_alerts, send_email_alerts
from app.crud.watchlist import get_or_create_default, list_tickers

router = APIRouter(prefix="/api")


# --- GET /api/content/{ticker} ---

@router.get("/content/{ticker}")
def get_content_vars(ticker: str, db: Session = Depends(get_db)):
    """Get complete content variable map for blog/newsletter templates."""
    result = to_content_vars(db, ticker)
    if result is None:
        raise HTTPException(404, f"Stock not found: {ticker}")
    return result


# --- GET /api/diff/{ticker} ---

@router.get("/diff/{ticker}")
def get_diff(ticker: str, db: Session = Depends(get_db)):
    """Detect rating/target price changes between latest and previous reports."""
    result = detect_changes(db, ticker)
    if result is None:
        raise HTTPException(404, f"Stock not found: {ticker}")
    return result


# --- POST /api/alerts/check ---

@router.post("/alerts/check")
def check_alerts(db: Session = Depends(get_db)):
    """Check watchlist tickers for changes and create alert records."""
    wl = get_or_create_default(db)
    items = list_tickers(db, wl.id)
    tickers = [item["ticker"] for item in items]
    if not tickers:
        return {"status": "empty", "message": "No tickers in watchlist"}

    new_alerts = check_and_alert(db, tickers)
    return {
        "status": "ok",
        "tickers_checked": len(tickers),
        "new_alerts": len(new_alerts),
        "alerts": new_alerts,
    }


# --- GET /api/alerts ---

@router.get("/alerts")
def list_alerts(limit: int = 50, db: Session = Depends(get_db)):
    """List pending (un-notified) alerts."""
    alerts = get_pending_alerts(db, limit)
    return {
        "count": len(alerts),
        "alerts": [
            {
                "id": a.id,
                "ticker": a.ticker,
                "source": a.source,
                "type": a.alert_type,
                "field": a.field,
                "old_value": a.old_value,
                "new_value": a.new_value,
                "message": a.message,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in alerts
        ],
    }


# --- POST /api/alerts/send ---

@router.post("/alerts/send")
def send_alerts(db: Session = Depends(get_db)):
    """Send pending alerts via email."""
    result = send_email_alerts(db)
    return result
