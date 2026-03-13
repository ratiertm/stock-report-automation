"""CRUD operations with UPSERT for stock report data."""

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Optional

from sqlalchemy import select, and_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models import (
    StockProfile, StockReport, StockFinancial, StockBalanceSheet,
    StockKeyStat, StockPeer, StockAnalystNote,
)


def _to_decimal(val) -> Optional[Decimal]:
    if val is None:
        return None
    try:
        return Decimal(str(val))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _to_date(val) -> Optional[date]:
    if val is None:
        return None
    if isinstance(val, date):
        return val
    for fmt in ("%B %d, %Y", "%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(str(val).strip(), fmt).date()
        except ValueError:
            continue
    return None


def _to_datetime(val) -> Optional[datetime]:
    if val is None:
        return None
    if isinstance(val, datetime):
        return val
    # Strip timezone suffixes (e.g. "ET", "EST", "EDT") before parsing
    s = re.sub(r'\s+(?:ET|EST|EDT|UTC|GMT)$', '', str(val).strip())
    for fmt in ("%Y-%m-%d %H:%M:%S", "%m/%d/%Y %H:%M", "%B %d, %Y %I:%M %p",
                "%b %d, %Y %I:%M %p", "%m/%d/%Y %I:%M %p", "%m/%d/%Y"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


# --------------- StockProfile ---------------

def upsert_profile(session: Session, data: dict) -> StockProfile:
    ticker = data.get("ticker")
    exchange = data.get("exchange") or "UNKNOWN"

    # If exchange is UNKNOWN, try to find existing profile by ticker
    # to avoid duplicate profiles (e.g. CFRA has exchange, Zacks doesn't)
    if exchange == "UNKNOWN":
        existing = session.execute(
            select(StockProfile).where(StockProfile.ticker == ticker)
            .order_by(StockProfile.id.asc()).limit(1)
        ).scalar_one_or_none()
        if existing:
            exchange = existing.exchange

    values = {
        "ticker": ticker,
        "company_name": data.get("company_name"),
        "exchange": exchange,
        "gics_sector": data.get("gics_sector"),
        "gics_sub_industry": data.get("gics_sub_industry"),
        "industry": data.get("industry"),
    }
    # Remove None keys for update (don't overwrite existing with None)
    update_vals = {k: v for k, v in values.items() if v is not None and k not in ("ticker", "exchange")}

    stmt = insert(StockProfile).values(**values)
    stmt = stmt.on_conflict_do_update(
        index_elements=["ticker", "exchange"],
        set_=update_vals,
    )
    session.execute(stmt)
    session.flush()

    return session.execute(
        select(StockProfile).where(
            and_(StockProfile.ticker == ticker, StockProfile.exchange == exchange)
        )
    ).scalar_one()


# --------------- StockReport ---------------

def upsert_report(session: Session, profile_id: int, data: dict, pdf_path: str = None) -> StockReport:
    report_date = _to_date(data.get("report_date"))
    if not report_date:
        report_date = date.today()

    values = {
        "stock_profile_id": profile_id,
        "source": data.get("source", "UNKNOWN"),
        "report_date": report_date,
        "analyst_name": data.get("analyst_name"),
        "recommendation": data.get("recommendation"),
        "prior_recommendation": data.get("prior_recommendation"),
        "stars_rating": data.get("stars_rating"),
        "zacks_rank": data.get("zacks_rank"),
        "zacks_rank_label": data.get("zacks_rank_label"),
        "style_scores": data.get("style_scores"),
        "target_price": _to_decimal(data.get("target_price")),
        "current_price": _to_decimal(data.get("current_price")),
        "price_date": _to_date(data.get("price_date")),
        "risk_assessment": data.get("risk_assessment"),
        "fair_value": _to_decimal(data.get("fair_value")),
        "fair_value_rank": data.get("fair_value_rank"),
        "volatility": data.get("volatility"),
        "technical_eval": data.get("technical_eval"),
        "insider_activity": data.get("insider_activity"),
        "investment_style": data.get("investment_style"),
        "industry_rank": data.get("industry_rank"),
        "highlights": data.get("highlights"),
        "reasons_to_buy": data.get("reasons_to_buy"),
        "reasons_to_sell": data.get("reasons_to_sell"),
        "investment_rationale": data.get("investment_rationale"),
        "business_summary": data.get("business_summary"),
        "sub_industry_outlook": data.get("sub_industry_outlook"),
        "last_earnings_summary": data.get("last_earnings_summary"),
        "outlook": data.get("outlook"),
        "recent_news": data.get("recent_news"),
        "raw_pdf_path": pdf_path,
    }

    update_vals = {k: v for k, v in values.items()
                   if k not in ("stock_profile_id", "source", "report_date")}

    stmt = insert(StockReport).values(**values)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_report_profile_source_date",
        set_=update_vals,
    )
    session.execute(stmt)
    session.flush()

    return session.execute(
        select(StockReport).where(
            and_(
                StockReport.stock_profile_id == profile_id,
                StockReport.source == data["source"],
                StockReport.report_date == report_date,
            )
        )
    ).scalar_one()


# --------------- StockFinancial ---------------

def upsert_financial(session: Session, profile_id: int, data: dict):
    # Use 0 instead of None for annual records (NULL != NULL in PG unique constraints)
    fiscal_quarter = data.get("fiscal_quarter") or 0
    is_estimate = data.get("is_estimate", False)

    values = {
        "stock_profile_id": profile_id,
        "fiscal_year": data.get("fiscal_year", 0),
        "fiscal_quarter": fiscal_quarter,
        "period_type": data.get("period_type", "annual"),
        "is_estimate": is_estimate,
        "revenue": _to_decimal(data.get("revenue")),
        "eps": _to_decimal(data.get("eps")),
        "operating_income": _to_decimal(data.get("operating_income")),
        "pretax_income": _to_decimal(data.get("pretax_income")),
        "net_income": _to_decimal(data.get("net_income")),
        "eps_normalized": _to_decimal(data.get("eps_normalized")),
        "gross_margin_pct": _to_decimal(data.get("gross_margin_pct")),
        "operating_margin_pct": _to_decimal(data.get("operating_margin_pct")),
        "eps_surprise_pct": _to_decimal(data.get("eps_surprise_pct")),
        "sales_surprise_pct": _to_decimal(data.get("sales_surprise_pct")),
    }

    # Only update non-None values to avoid overwriting existing data
    # (Zacks produces separate revenue and EPS rows for same period)
    update_vals = {k: v for k, v in values.items()
                   if k not in ("stock_profile_id", "fiscal_year", "fiscal_quarter", "is_estimate")
                   and v is not None}

    stmt = insert(StockFinancial).values(**values)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_financial_profile_year_quarter_estimate",
        set_=update_vals if update_vals else {"period_type": values["period_type"]},
    )
    session.execute(stmt)


# --------------- StockKeyStat ---------------

def upsert_key_stats(session: Session, report_id: int, data: dict):
    values = {
        "stock_report_id": report_id,
        "week_52_high": _to_decimal(data.get("week_52_high")),
        "week_52_low": _to_decimal(data.get("week_52_low")),
        "trailing_12m_eps": _to_decimal(data.get("trailing_12m_eps")),
        "trailing_12m_pe": _to_decimal(data.get("trailing_12m_pe")),
        "market_cap_b": _to_decimal(data.get("market_cap_b")),
        "shares_outstanding_m": _to_decimal(data.get("shares_outstanding_m")),
        "beta": _to_decimal(data.get("beta")),
        "eps_cagr_3yr_pct": _to_decimal(data.get("eps_cagr_3yr_pct")),
        "institutional_ownership_pct": _to_decimal(data.get("institutional_ownership_pct")),
        "dividend_yield_pct": _to_decimal(data.get("dividend_yield_pct")),
        "dividend_rate": _to_decimal(data.get("dividend_rate")),
        "price_to_sales": _to_decimal(data.get("price_to_sales")),
        "price_to_ebitda": _to_decimal(data.get("price_to_ebitda")),
        "price_to_pretax": _to_decimal(data.get("price_to_pretax")),
        "pe_forward_12m": _to_decimal(data.get("pe_forward_12m")),
        "ps_forward_12m": _to_decimal(data.get("ps_forward_12m")),
        "ev_ebitda": _to_decimal(data.get("ev_ebitda")),
        "peg_ratio": _to_decimal(data.get("peg_ratio")),
        "price_to_book": _to_decimal(data.get("price_to_book")),
        "price_to_cashflow": _to_decimal(data.get("price_to_cashflow")),
        "debt_equity": _to_decimal(data.get("debt_equity")),
        "cash_per_share": _to_decimal(data.get("cash_per_share")),
        "earnings_yield_pct": _to_decimal(data.get("earnings_yield_pct")),
        "valuation_multiples": data.get("valuation_multiples"),
        # CFRA-specific fields
        "quality_ranking": data.get("quality_ranking"),
        "oper_eps_current_e": _to_decimal(data.get("oper_eps_current_e")),
        "oper_eps_next_e": _to_decimal(data.get("oper_eps_next_e")),
        "pe_on_oper_eps_current": _to_decimal(data.get("pe_on_oper_eps_current")),
    }

    stmt = insert(StockKeyStat).values(**values)
    stmt = stmt.on_conflict_do_update(
        index_elements=["stock_report_id"],
        set_={k: v for k, v in values.items() if k != "stock_report_id"},
    )
    session.execute(stmt)


# --------------- StockBalanceSheet ---------------

def upsert_balance_sheet(session: Session, profile_id: int, data: dict):
    values = {
        "stock_profile_id": profile_id,
        "fiscal_year": data.get("fiscal_year", 0),
        "cash": _to_decimal(data.get("cash")),
        "current_assets": _to_decimal(data.get("current_assets")),
        "total_assets": _to_decimal(data.get("total_assets")),
        "current_liabilities": _to_decimal(data.get("current_liabilities")),
        "long_term_debt": _to_decimal(data.get("long_term_debt")),
        "total_capital": _to_decimal(data.get("total_capital")),
        "capital_expenditures": _to_decimal(data.get("capital_expenditures")),
        "cash_from_operations": _to_decimal(data.get("cash_from_operations")),
        "current_ratio": _to_decimal(data.get("current_ratio")),
        "ltd_to_cap_pct": _to_decimal(data.get("ltd_to_cap_pct")),
        "net_income_to_revenue_pct": _to_decimal(data.get("net_income_to_revenue_pct")),
        "return_on_assets_pct": _to_decimal(data.get("return_on_assets_pct")),
        "return_on_equity_pct": _to_decimal(data.get("return_on_equity_pct")),
    }

    stmt = insert(StockBalanceSheet).values(**values)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_balance_sheet_profile_year",
        set_={k: v for k, v in values.items()
              if k not in ("stock_profile_id", "fiscal_year")},
    )
    session.execute(stmt)


# --------------- StockPeer ---------------

def save_peers(session: Session, report_id: int, peers_list: list[dict]):
    # Delete existing peers for this report, then insert new ones
    session.query(StockPeer).filter(StockPeer.stock_report_id == report_id).delete()
    for p in peers_list:
        peer = StockPeer(
            stock_report_id=report_id,
            peer_ticker=p.get("peer_ticker"),
            peer_name=p.get("peer_name"),
            recommendation=p.get("recommendation"),
            rank=p.get("rank"),
            detailed_comparison=p.get("detailed_comparison"),
        )
        session.add(peer)
    session.flush()


# --------------- StockAnalystNote ---------------

def save_analyst_notes(session: Session, profile_id: int, source: str, notes: list[dict]):
    # Delete existing notes for this profile+source, then re-insert
    session.query(StockAnalystNote).filter(
        StockAnalystNote.stock_profile_id == profile_id,
        StockAnalystNote.source == source,
    ).delete()
    for n in notes:
        published = _to_datetime(n.get("published_at"))
        note = StockAnalystNote(
            stock_profile_id=profile_id,
            source=source,
            published_at=published,
            analyst_name=n.get("analyst_name"),
            title=n.get("title"),
            action=n.get("action"),
            stock_price_at_note=_to_decimal(n.get("stock_price_at_note")),
            target_price=_to_decimal(n.get("target_price")),
            content=n.get("content"),
        )
        session.add(note)
    session.flush()


# --------------- Query helpers ---------------

def get_profile_by_ticker(session: Session, ticker: str) -> Optional[StockProfile]:
    return session.execute(
        select(StockProfile).where(StockProfile.ticker == ticker.upper())
        .order_by(StockProfile.id.desc())
        .limit(1)
    ).scalar_one_or_none()


def get_latest_reports(session: Session, profile_id: int) -> list[StockReport]:
    return list(session.execute(
        select(StockReport)
        .where(StockReport.stock_profile_id == profile_id)
        .order_by(StockReport.report_date.desc())
    ).scalars().all())


def get_financials(session: Session, profile_id: int) -> list[StockFinancial]:
    return list(session.execute(
        select(StockFinancial)
        .where(StockFinancial.stock_profile_id == profile_id)
        .order_by(StockFinancial.fiscal_year.desc(), StockFinancial.fiscal_quarter.desc())
    ).scalars().all())


def get_all_profiles(session: Session) -> list[StockProfile]:
    return list(session.execute(
        select(StockProfile).order_by(StockProfile.ticker)
    ).scalars().all())
