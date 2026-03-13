from sqlalchemy import (
    Column, BigInteger, Date, Numeric, DateTime, ForeignKey,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class ReportKeyStat(Base):
    __tablename__ = "report_key_stats"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    report_id = Column(BigInteger, ForeignKey("reports.id", ondelete="CASCADE"), nullable=False, unique=True)

    # Price related
    week_52_high = Column(Numeric(12, 4))
    week_52_low = Column(Numeric(12, 4))
    beta = Column(Numeric(6, 3))
    avg_volume_20d = Column(BigInteger)
    ytd_price_change_pct = Column(Numeric(8, 4))

    # Earnings related
    trailing_12m_eps = Column(Numeric(12, 4))
    trailing_12m_pe = Column(Numeric(10, 2))
    oper_eps_current_e = Column(Numeric(12, 4))
    oper_eps_next_e = Column(Numeric(12, 4))
    pe_on_oper_eps = Column(Numeric(10, 2))
    pe_forward_12m = Column(Numeric(10, 2))

    # Market cap / shares
    market_cap_b = Column(Numeric(12, 4))
    shares_outstanding_m = Column(Numeric(12, 2))
    institutional_ownership_pct = Column(Numeric(6, 2))

    # Dividends
    dividend_yield_pct = Column(Numeric(6, 3))
    dividend_rate = Column(Numeric(8, 4))

    # Growth
    eps_cagr_3yr_pct = Column(Numeric(8, 2))

    # Valuation multiples
    price_to_sales = Column(Numeric(10, 2))
    price_to_ebitda = Column(Numeric(10, 2))
    price_to_pretax = Column(Numeric(10, 2))
    price_to_book = Column(Numeric(10, 2))
    price_to_cashflow = Column(Numeric(10, 2))
    ev_ebitda = Column(Numeric(10, 2))
    peg_ratio = Column(Numeric(8, 3))

    # Financial health
    debt_equity = Column(Numeric(10, 4))
    cash_per_share = Column(Numeric(12, 4))
    earnings_yield_pct = Column(Numeric(8, 4))

    # Margins / returns
    net_margin_1yr_pct = Column(Numeric(8, 2))
    net_margin_3yr_pct = Column(Numeric(8, 2))
    sales_growth_1yr_pct = Column(Numeric(8, 2))
    sales_growth_3yr_pct = Column(Numeric(8, 2))

    # Zacks: ESP & surprise
    earnings_esp_pct = Column(Numeric(8, 4))
    last_eps_surprise_pct = Column(Numeric(8, 4))
    last_sales_surprise_pct = Column(Numeric(8, 4))
    expected_report_date = Column(Date)

    # Meta
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    # Relationships
    report = relationship("Report", back_populates="key_stats")
