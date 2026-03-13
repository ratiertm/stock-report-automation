from sqlalchemy import (
    Column, BigInteger, SmallInteger, String, Numeric, DateTime,
    ForeignKey, UniqueConstraint, CheckConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class IncomeStatement(Base):
    __tablename__ = "income_statements"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    company_id = Column(BigInteger, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    source = Column(String(10), nullable=False, default="CFRA")
    fiscal_year = Column(SmallInteger, nullable=False)

    revenue = Column(Numeric(15, 2))
    operating_income = Column(Numeric(15, 2))
    depreciation = Column(Numeric(15, 2))
    interest_expense = Column(Numeric(15, 2))
    pretax_income = Column(Numeric(15, 2))
    effective_tax_rate = Column(Numeric(6, 3))
    net_income = Column(Numeric(15, 2))
    sp_core_eps = Column(Numeric(10, 4))

    # Meta
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("company_id", "source", "fiscal_year", name="uq_income_statements_company_source_year"),
        CheckConstraint("source IN ('CFRA', 'Zacks')", name="chk_income_statements_source"),
    )

    # Relationships
    company = relationship("Company", back_populates="income_statements")
