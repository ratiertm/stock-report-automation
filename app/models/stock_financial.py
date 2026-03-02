from sqlalchemy import (
    Column, BigInteger, String, Integer, Boolean, Numeric, DateTime,
    ForeignKey, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class StockFinancial(Base):
    __tablename__ = "stock_financials"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    stock_profile_id = Column(BigInteger, ForeignKey("stock_profiles.id"), nullable=False)
    fiscal_year = Column(Integer, nullable=False)
    fiscal_quarter = Column(Integer)
    period_type = Column(String(10), nullable=False)
    is_estimate = Column(Boolean, default=False)
    revenue = Column(Numeric(15, 2))
    operating_income = Column(Numeric(15, 2))
    pretax_income = Column(Numeric(15, 2))
    net_income = Column(Numeric(15, 2))
    eps = Column(Numeric(8, 4))
    eps_normalized = Column(Numeric(8, 4))
    free_cash_flow_ps = Column(Numeric(8, 4))
    tangible_book_value_ps = Column(Numeric(8, 4))
    depreciation = Column(Numeric(12, 2))
    effective_tax_rate = Column(Numeric(6, 2))
    gross_margin_pct = Column(Numeric(6, 2))
    operating_margin_pct = Column(Numeric(6, 2))
    segment_revenues = Column(JSONB)
    eps_surprise_pct = Column(Numeric(6, 2))
    sales_surprise_pct = Column(Numeric(6, 2))
    organization_id = Column(BigInteger)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("stock_profile_id", "fiscal_year", "fiscal_quarter", "is_estimate",
                         name="uq_financial_profile_year_quarter_estimate"),
    )

    profile = relationship("StockProfile", back_populates="financials")
