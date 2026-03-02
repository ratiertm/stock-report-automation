"""Pydantic response schemas for stock API."""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict


# --------------- Key Stats ---------------

class KeyStatOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    trailing_12m_pe: Optional[Decimal] = None
    pe_forward_12m: Optional[Decimal] = None
    peg_ratio: Optional[Decimal] = None
    beta: Optional[Decimal] = None
    market_cap_b: Optional[Decimal] = None
    shares_outstanding_m: Optional[Decimal] = None
    trailing_12m_eps: Optional[Decimal] = None
    week_52_high: Optional[Decimal] = None
    week_52_low: Optional[Decimal] = None
    dividend_yield_pct: Optional[Decimal] = None
    dividend_rate: Optional[Decimal] = None
    price_to_book: Optional[Decimal] = None
    price_to_sales: Optional[Decimal] = None
    ev_ebitda: Optional[Decimal] = None
    debt_equity: Optional[Decimal] = None
    institutional_ownership_pct: Optional[Decimal] = None
    quality_ranking: Optional[str] = None


# --------------- Peer ---------------

class PeerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    peer_ticker: Optional[str] = None
    peer_name: Optional[str] = None
    recommendation: Optional[str] = None
    rank: Optional[int] = None


# --------------- Report ---------------

class ReportSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source: str
    report_date: date
    recommendation: Optional[str] = None
    stars_rating: Optional[int] = None
    zacks_rank: Optional[int] = None
    zacks_rank_label: Optional[str] = None
    target_price: Optional[Decimal] = None
    current_price: Optional[Decimal] = None
    analyst_name: Optional[str] = None
    risk_assessment: Optional[str] = None


class ReportDetail(ReportSummary):
    style_scores: Optional[dict] = None
    fair_value: Optional[Decimal] = None
    volatility: Optional[str] = None
    technical_eval: Optional[str] = None
    insider_activity: Optional[str] = None
    investment_style: Optional[str] = None
    industry_rank: Optional[str] = None
    highlights: Optional[str] = None
    reasons_to_buy: Optional[str] = None
    reasons_to_sell: Optional[str] = None
    investment_rationale: Optional[str] = None
    business_summary: Optional[str] = None
    sub_industry_outlook: Optional[str] = None
    last_earnings_summary: Optional[str] = None
    outlook: Optional[str] = None
    key_stats: Optional[KeyStatOut] = None
    peers: list[PeerOut] = []


# --------------- Profile ---------------

class ProfileSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ticker: str
    company_name: Optional[str] = None
    exchange: Optional[str] = None
    gics_sector: Optional[str] = None
    industry: Optional[str] = None


class ProfileDetail(ProfileSummary):
    gics_sub_industry: Optional[str] = None
    employees: Optional[int] = None
    website: Optional[str] = None
    description: Optional[str] = None


class ProfileWithReports(ProfileDetail):
    latest_reports: list[ReportSummary] = []


# --------------- Financial ---------------

class FinancialOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    fiscal_year: int
    fiscal_quarter: Optional[int] = None
    period_type: str
    is_estimate: bool = False
    revenue: Optional[Decimal] = None
    eps: Optional[Decimal] = None
    operating_income: Optional[Decimal] = None
    net_income: Optional[Decimal] = None
    gross_margin_pct: Optional[Decimal] = None
    operating_margin_pct: Optional[Decimal] = None


# --------------- Analyst Note ---------------

class AnalystNoteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    source: Optional[str] = None
    published_at: Optional[datetime] = None
    analyst_name: Optional[str] = None
    action: Optional[str] = None
    stock_price_at_note: Optional[Decimal] = None
    target_price: Optional[Decimal] = None
    content: Optional[str] = None


# --------------- Compare ---------------

class SourceReport(BaseModel):
    source: str
    report_date: date
    recommendation: Optional[str] = None
    stars_rating: Optional[int] = None
    zacks_rank: Optional[int] = None
    zacks_rank_label: Optional[str] = None
    target_price: Optional[Decimal] = None
    current_price: Optional[Decimal] = None
    risk_assessment: Optional[str] = None
    style_scores: Optional[dict] = None
    key_stats: Optional[KeyStatOut] = None
    peers: list[PeerOut] = []


class CompareOut(BaseModel):
    ticker: str
    company_name: Optional[str] = None
    sources: dict[str, SourceReport] = {}


# --------------- Bundle (Content Vars) ---------------

class BundleOut(BaseModel):
    ticker: str
    company_name: Optional[str] = None
    exchange: Optional[str] = None
    gics_sector: Optional[str] = None
    recommendation: Optional[str] = None
    target_price: Optional[Decimal] = None
    current_price: Optional[Decimal] = None
    upside_pct: Optional[float] = None
    stars_rating: Optional[int] = None
    zacks_rank: Optional[int] = None
    highlights: Optional[str] = None
    investment_rationale: Optional[str] = None
    reasons_to_buy: Optional[str] = None
    reasons_to_sell: Optional[str] = None
    market_cap_b: Optional[Decimal] = None
    trailing_12m_pe: Optional[Decimal] = None
    beta: Optional[Decimal] = None


# --------------- Parse Response ---------------

class ParseResponse(BaseModel):
    status: str
    ticker: Optional[str] = None
    source: Optional[str] = None
    report_date: Optional[str] = None
    records_saved: Optional[dict] = None
    errors: list[str] = []
    warnings: list[str] = []
