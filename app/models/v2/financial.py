from sqlalchemy import (
    Column, BigInteger, SmallInteger, String, Boolean, Numeric, DateTime,
    ForeignKey, UniqueConstraint, CheckConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class Financial(Base):
    __tablename__ = "financials"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    company_id = Column(BigInteger, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    source = Column(String(10), nullable=False)
    fiscal_year = Column(SmallInteger, nullable=False)
    fiscal_quarter = Column(SmallInteger)
    period_type = Column(String(10), nullable=False)
    is_estimate = Column(Boolean, nullable=False, default=False)

    # P&L
    revenue = Column(Numeric(15, 2))
    operating_income = Column(Numeric(15, 2))
    pretax_income = Column(Numeric(15, 2))
    net_income = Column(Numeric(15, 2))
    depreciation = Column(Numeric(15, 2))
    interest_expense = Column(Numeric(15, 2))
    effective_tax_rate = Column(Numeric(6, 3))

    # Per Share
    eps = Column(Numeric(10, 4))
    eps_normalized = Column(Numeric(10, 4))

    # Margins
    gross_margin_pct = Column(Numeric(6, 2))
    operating_margin_pct = Column(Numeric(6, 2))

    # Segments
    segment_revenues = Column(JSONB)

    # Surprise (Zacks)
    eps_surprise_pct = Column(Numeric(8, 4))
    sales_surprise_pct = Column(Numeric(8, 4))

    # Meta
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("company_id", "source", "fiscal_year", "fiscal_quarter", "is_estimate",
                         name="uq_financials_company_source_year_quarter_estimate"),
        CheckConstraint("source IN ('CFRA', 'Zacks')", name="chk_financials_source"),
        CheckConstraint("period_type IN ('annual', 'quarterly')", name="chk_financials_period_type"),
        CheckConstraint("fiscal_quarter BETWEEN 1 AND 4", name="chk_financials_quarter"),
    )

    # Relationships
    company = relationship("Company", back_populates="financials")
