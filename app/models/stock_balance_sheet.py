from sqlalchemy import (
    Column, BigInteger, Integer, Numeric, DateTime, ForeignKey, UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class StockBalanceSheet(Base):
    __tablename__ = "stock_balance_sheets"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    stock_profile_id = Column(BigInteger, ForeignKey("stock_profiles.id"), nullable=False)
    fiscal_year = Column(Integer, nullable=False)
    cash = Column(Numeric(15, 2))
    current_assets = Column(Numeric(15, 2))
    total_assets = Column(Numeric(15, 2))
    current_liabilities = Column(Numeric(15, 2))
    long_term_debt = Column(Numeric(15, 2))
    total_capital = Column(Numeric(15, 2))
    capital_expenditures = Column(Numeric(15, 2))
    cash_from_operations = Column(Numeric(15, 2))
    current_ratio = Column(Numeric(10, 2))
    ltd_to_cap_pct = Column(Numeric(10, 2))
    net_income_to_revenue_pct = Column(Numeric(10, 2))
    return_on_assets_pct = Column(Numeric(10, 2))
    return_on_equity_pct = Column(Numeric(10, 2))
    organization_id = Column(BigInteger)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("stock_profile_id", "fiscal_year",
                         name="uq_balance_sheet_profile_year"),
    )

    profile = relationship("StockProfile", back_populates="balance_sheets")
