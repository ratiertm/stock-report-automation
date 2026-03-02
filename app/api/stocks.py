"""Stock API router — 8 endpoints."""

import os
import shutil
import tempfile

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session

from app.database import get_db
from app.crud.stock import (
    get_all_profiles, get_profile_by_ticker, get_latest_reports, get_financials,
)
from app.services.parser_service import parse_and_store
from app.schemas.stock import (
    ProfileSummary, ProfileWithReports, ReportDetail, FinancialOut,
    AnalystNoteOut, CompareOut, SourceReport, KeyStatOut, PeerOut,
    BundleOut, ParseResponse,
)

router = APIRouter(prefix="/api")


# --- 1.3  GET /api/stocks ---

@router.get("/stocks", response_model=list[ProfileSummary])
def list_stocks(db: Session = Depends(get_db)):
    return get_all_profiles(db)


# --- 1.4  GET /api/stocks/{ticker} ---

@router.get("/stocks/{ticker}", response_model=ProfileWithReports)
def get_stock(ticker: str, db: Session = Depends(get_db)):
    profile = get_profile_by_ticker(db, ticker)
    if not profile:
        raise HTTPException(404, f"Stock not found: {ticker}")
    reports = get_latest_reports(db, profile.id)
    return ProfileWithReports(
        **ProfileSummary.model_validate(profile).model_dump(),
        gics_sub_industry=profile.gics_sub_industry,
        employees=profile.employees,
        website=profile.website,
        description=profile.description,
        latest_reports=[ReportDetail.model_validate(r) for r in reports],
    )


# --- 1.5  GET /api/stocks/{ticker}/financials ---

@router.get("/stocks/{ticker}/financials", response_model=list[FinancialOut])
def get_stock_financials(
    ticker: str,
    period: str = "all",  # "annual", "quarterly", "all"
    db: Session = Depends(get_db),
):
    profile = get_profile_by_ticker(db, ticker)
    if not profile:
        raise HTTPException(404, f"Stock not found: {ticker}")
    fins = get_financials(db, profile.id)
    if period == "annual":
        fins = [f for f in fins if f.period_type == "annual"]
    elif period == "quarterly":
        fins = [f for f in fins if f.period_type == "quarterly"]
    return fins


# --- 1.6  GET /api/stocks/{ticker}/compare ---

@router.get("/stocks/{ticker}/compare", response_model=CompareOut)
def compare_sources(ticker: str, db: Session = Depends(get_db)):
    profile = get_profile_by_ticker(db, ticker)
    if not profile:
        raise HTTPException(404, f"Stock not found: {ticker}")
    reports = get_latest_reports(db, profile.id)
    if not reports:
        raise HTTPException(404, f"No reports for: {ticker}")

    sources = {}
    for r in reports:
        ks = KeyStatOut.model_validate(r.key_stats) if r.key_stats else None
        peers = [PeerOut.model_validate(p) for p in r.peers] if r.peers else []
        sources[r.source] = SourceReport(
            source=r.source,
            report_date=r.report_date,
            recommendation=r.recommendation,
            stars_rating=r.stars_rating,
            zacks_rank=r.zacks_rank,
            zacks_rank_label=r.zacks_rank_label,
            target_price=r.target_price,
            current_price=r.current_price,
            risk_assessment=r.risk_assessment,
            style_scores=r.style_scores,
            key_stats=ks,
            peers=peers,
        )

    return CompareOut(
        ticker=profile.ticker,
        company_name=profile.company_name,
        sources=sources,
    )


# --- 1.7  POST /api/parse ---

@router.post("/parse", response_model=ParseResponse)
def parse_pdf(
    file: UploadFile = File(...),
    source: str = Form(...),
    db: Session = Depends(get_db),
):
    source = source.upper()
    if source not in ("CFRA", "ZACKS"):
        raise HTTPException(400, f"Invalid source: {source}. Use CFRA or ZACKS.")

    # Save uploaded file to temp
    suffix = os.path.splitext(file.filename or "report.pdf")[1] or ".pdf"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    try:
        result = parse_and_store(tmp_path, source, db)
        if "error" in result:
            raise HTTPException(422, result["error"])
        return result
    finally:
        os.unlink(tmp_path)


# --- 1.8  GET /api/stocks/{ticker}/bundle ---

@router.get("/stocks/{ticker}/bundle", response_model=BundleOut)
def get_bundle(ticker: str, db: Session = Depends(get_db)):
    profile = get_profile_by_ticker(db, ticker)
    if not profile:
        raise HTTPException(404, f"Stock not found: {ticker}")

    reports = get_latest_reports(db, profile.id)
    if not reports:
        raise HTTPException(404, f"No reports for: {ticker}")

    # Pick first report (most recent) for primary data
    r = reports[0]
    ks = r.key_stats

    upside = None
    if r.target_price and r.current_price and r.current_price > 0:
        upside = round(float((r.target_price - r.current_price) / r.current_price * 100), 1)

    return BundleOut(
        ticker=profile.ticker,
        company_name=profile.company_name,
        exchange=profile.exchange,
        gics_sector=profile.gics_sector,
        recommendation=r.recommendation,
        target_price=r.target_price,
        current_price=r.current_price,
        upside_pct=upside,
        stars_rating=r.stars_rating,
        zacks_rank=r.zacks_rank,
        highlights=r.highlights,
        investment_rationale=r.investment_rationale,
        reasons_to_buy=r.reasons_to_buy,
        reasons_to_sell=r.reasons_to_sell,
        market_cap_b=ks.market_cap_b if ks else None,
        trailing_12m_pe=ks.trailing_12m_pe if ks else None,
        beta=ks.beta if ks else None,
    )


# --- Extra: GET /api/stocks/{ticker}/notes ---

@router.get("/stocks/{ticker}/notes", response_model=list[AnalystNoteOut])
def get_notes(ticker: str, db: Session = Depends(get_db)):
    profile = get_profile_by_ticker(db, ticker)
    if not profile:
        raise HTTPException(404, f"Stock not found: {ticker}")
    return profile.analyst_notes
