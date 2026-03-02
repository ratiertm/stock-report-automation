from sqlalchemy import (
    Column, BigInteger, String, Numeric, DateTime, ForeignKey,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class StockKeyStat(Base):
    __tablename__ = "stock_key_stats"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    stock_report_id = Column(BigInteger, ForeignKey("stock_reports.id"), nullable=False, unique=True)
    week_52_high = Column(Numeric(12, 2))
    week_52_low = Column(Numeric(12, 2))
    trailing_12m_eps = Column(Numeric(8, 4))
    trailing_12m_pe = Column(Numeric(10, 2))
    market_cap_b = Column(Numeric(12, 2))
    shares_outstanding_m = Column(Numeric(12, 2))
    beta = Column(Numeric(6, 2))
    eps_cagr_3yr_pct = Column(Numeric(6, 2))
    institutional_ownership_pct = Column(Numeric(6, 2))
    dividend_yield_pct = Column(Numeric(6, 2))
    dividend_rate = Column(Numeric(8, 2))
    price_to_sales = Column(Numeric(10, 2))
    price_to_ebitda = Column(Numeric(10, 2))
    price_to_pretax = Column(Numeric(10, 2))
    net_margin_1yr_pct = Column(Numeric(6, 2))
    net_margin_3yr_pct = Column(Numeric(6, 2))
    sales_growth_1yr_pct = Column(Numeric(6, 2))
    sales_growth_3yr_pct = Column(Numeric(6, 2))
    pe_forward_12m = Column(Numeric(10, 2))
    ps_forward_12m = Column(Numeric(10, 2))
    ev_ebitda = Column(Numeric(10, 2))
    peg_ratio = Column(Numeric(10, 2))
    price_to_book = Column(Numeric(10, 2))
    price_to_cashflow = Column(Numeric(10, 2))
    debt_equity = Column(Numeric(10, 2))
    cash_per_share = Column(Numeric(10, 2))
    earnings_yield_pct = Column(Numeric(6, 2))
    valuation_multiples = Column(JSONB)
    # CFRA-specific fields
    quality_ranking = Column(String(20))
    oper_eps_current_e = Column(Numeric(8, 4))
    oper_eps_next_e = Column(Numeric(8, 4))
    pe_on_oper_eps_current = Column(Numeric(10, 2))
    organization_id = Column(BigInteger)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    report = relationship("StockReport", back_populates="key_stats")
