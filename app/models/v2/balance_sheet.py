from sqlalchemy import (
    Column, BigInteger, SmallInteger, String, Numeric, DateTime,
    ForeignKey, UniqueConstraint, CheckConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class BalanceSheet(Base):
    __tablename__ = "balance_sheets"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    company_id = Column(BigInteger, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    source = Column(String(10), nullable=False, default="CFRA")
    fiscal_year = Column(SmallInteger, nullable=False)

    # Assets
    cash = Column(Numeric(15, 2))
    current_assets = Column(Numeric(15, 2))
    total_assets = Column(Numeric(15, 2))

    # Liabilities
    current_liabilities = Column(Numeric(15, 2))
    long_term_debt = Column(Numeric(15, 2))
    total_capital = Column(Numeric(15, 2))

    # Cash flow
    capital_expenditures = Column(Numeric(15, 2))
    cash_from_operations = Column(Numeric(15, 2))

    # Ratios
    current_ratio = Column(Numeric(8, 3))
    ltd_to_cap_pct = Column(Numeric(6, 2))
    net_income_to_revenue_pct = Column(Numeric(6, 2))
    return_on_assets_pct = Column(Numeric(8, 2))
    return_on_equity_pct = Column(Numeric(8, 2))

    # Meta
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("company_id", "source", "fiscal_year", name="uq_balance_sheets_company_source_year"),
        CheckConstraint("source IN ('CFRA', 'Zacks')", name="chk_balance_sheets_source"),
    )

    # Relationships
    company = relationship("Company", back_populates="balance_sheets")
