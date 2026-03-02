"""Content Service: generates template variables and detects report changes."""

from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy import select, and_
from sqlalchemy.orm import Session

from app.models import StockProfile, StockReport, StockFinancial, StockKeyStat


def to_content_vars(session: Session, ticker: str) -> Optional[dict]:
    """Build a complete content variable map for blog/newsletter templates.

    Returns None if ticker not found, otherwise a dict with all template vars.
    """
    profile = session.execute(
        select(StockProfile).where(StockProfile.ticker == ticker.upper())
    ).scalar_one_or_none()
    if not profile:
        return None

    reports = list(session.execute(
        select(StockReport)
        .where(StockReport.stock_profile_id == profile.id)
        .order_by(StockReport.report_date.desc())
    ).scalars().all())

    if not reports:
        return {"ticker": profile.ticker, "company_name": profile.company_name, "has_reports": False}

    # Group by source
    by_source = {}
    for r in reports:
        if r.source not in by_source:
            by_source[r.source] = r

    primary = reports[0]
    ks = primary.key_stats

    # Upside calculation
    upside = None
    if primary.target_price and primary.current_price and primary.current_price > 0:
        upside = round(float((primary.target_price - primary.current_price) / primary.current_price * 100), 1)

    # Revenue trend (annual, last 3 years)
    fins = list(session.execute(
        select(StockFinancial)
        .where(
            and_(
                StockFinancial.stock_profile_id == profile.id,
                StockFinancial.period_type == "annual",
                StockFinancial.is_estimate == False,
            )
        )
        .order_by(StockFinancial.fiscal_year.desc())
        .limit(5)
    ).scalars().all())

    revenue_trend = [
        {"year": f.fiscal_year, "revenue": float(f.revenue) if f.revenue else None, "eps": float(f.eps) if f.eps else None}
        for f in reversed(fins)
    ]

    # Revenue growth YoY
    revenue_growth = None
    if len(fins) >= 2 and fins[1].revenue and fins[0].revenue and fins[1].revenue > 0:
        revenue_growth = round(float((fins[0].revenue - fins[1].revenue) / fins[1].revenue * 100), 1)

    # Multi-source consensus
    sources_summary = {}
    for src, r in by_source.items():
        sources_summary[src] = {
            "recommendation": r.recommendation,
            "target_price": float(r.target_price) if r.target_price else None,
            "report_date": r.report_date.isoformat(),
            "stars_rating": r.stars_rating,
            "zacks_rank": r.zacks_rank,
            "zacks_rank_label": r.zacks_rank_label,
        }

    # Target price consensus (avg of all sources)
    target_prices = [float(r.target_price) for r in by_source.values() if r.target_price]
    avg_target = round(sum(target_prices) / len(target_prices), 2) if target_prices else None

    return {
        "ticker": profile.ticker,
        "company_name": profile.company_name,
        "exchange": profile.exchange,
        "gics_sector": profile.gics_sector,
        "gics_sub_industry": profile.gics_sub_industry,
        "industry": profile.industry,
        "has_reports": True,
        "report_date": primary.report_date.isoformat(),
        "source": primary.source,
        # Ratings
        "recommendation": primary.recommendation,
        "stars_rating": primary.stars_rating,
        "zacks_rank": primary.zacks_rank,
        "zacks_rank_label": primary.zacks_rank_label,
        "style_scores": primary.style_scores,
        # Pricing
        "target_price": float(primary.target_price) if primary.target_price else None,
        "current_price": float(primary.current_price) if primary.current_price else None,
        "upside_pct": upside,
        "avg_target_price": avg_target,
        # Key stats
        "market_cap_b": float(ks.market_cap_b) if ks and ks.market_cap_b else None,
        "trailing_pe": float(ks.trailing_12m_pe) if ks and ks.trailing_12m_pe else None,
        "forward_pe": float(ks.pe_forward_12m) if ks and ks.pe_forward_12m else None,
        "peg_ratio": float(ks.peg_ratio) if ks and ks.peg_ratio else None,
        "beta": float(ks.beta) if ks and ks.beta else None,
        "dividend_yield_pct": float(ks.dividend_yield_pct) if ks and ks.dividend_yield_pct else None,
        "week_52_high": float(ks.week_52_high) if ks and ks.week_52_high else None,
        "week_52_low": float(ks.week_52_low) if ks and ks.week_52_low else None,
        # Text sections
        "highlights": primary.highlights,
        "investment_rationale": primary.investment_rationale,
        "business_summary": primary.business_summary,
        "reasons_to_buy": primary.reasons_to_buy,
        "reasons_to_sell": primary.reasons_to_sell,
        "outlook": primary.outlook,
        "sub_industry_outlook": primary.sub_industry_outlook,
        # Trend data
        "revenue_trend": revenue_trend,
        "revenue_growth_yoy_pct": revenue_growth,
        # Multi-source
        "sources": sources_summary,
        "source_count": len(by_source),
    }


def detect_changes(session: Session, ticker: str) -> Optional[dict]:
    """Compare latest vs previous report for the same source to detect rating/price changes.

    Returns None if ticker not found or no reports, otherwise:
    {
        "ticker": ...,
        "has_changes": bool,
        "changes": [
            {"source": "CFRA", "field": "recommendation", "old": "Hold", "new": "Buy", ...},
            ...
        ]
    }
    """
    profile = session.execute(
        select(StockProfile).where(StockProfile.ticker == ticker.upper())
    ).scalar_one_or_none()
    if not profile:
        return None

    reports = list(session.execute(
        select(StockReport)
        .where(StockReport.stock_profile_id == profile.id)
        .order_by(StockReport.report_date.desc())
    ).scalars().all())

    if not reports:
        return {"ticker": ticker.upper(), "has_changes": False, "changes": []}

    # Group by source, take latest 2 per source
    by_source: dict[str, list[StockReport]] = {}
    for r in reports:
        by_source.setdefault(r.source, []).append(r)

    WATCH_FIELDS = [
        ("recommendation", "Recommendation"),
        ("target_price", "Target Price"),
        ("stars_rating", "STARS Rating"),
        ("zacks_rank", "Zacks Rank"),
        ("risk_assessment", "Risk Assessment"),
    ]

    changes = []
    for source, source_reports in by_source.items():
        if len(source_reports) < 2:
            continue
        latest, previous = source_reports[0], source_reports[1]

        for field, label in WATCH_FIELDS:
            new_val = getattr(latest, field)
            old_val = getattr(previous, field)
            if new_val is None and old_val is None:
                continue
            if new_val != old_val:
                changes.append({
                    "source": source,
                    "field": field,
                    "label": label,
                    "old_value": _format_val(old_val),
                    "new_value": _format_val(new_val),
                    "old_date": previous.report_date.isoformat(),
                    "new_date": latest.report_date.isoformat(),
                })

    return {
        "ticker": ticker.upper(),
        "company_name": profile.company_name,
        "has_changes": len(changes) > 0,
        "changes": changes,
        "report_count": len(reports),
    }


def detect_changes_batch(session: Session, tickers: list[str]) -> list[dict]:
    """Detect changes for multiple tickers."""
    results = []
    for ticker in tickers:
        result = detect_changes(session, ticker)
        if result and result["has_changes"]:
            results.append(result)
    return results


def _format_val(val) -> str:
    if val is None:
        return "N/A"
    if isinstance(val, Decimal):
        return str(float(val))
    return str(val)
