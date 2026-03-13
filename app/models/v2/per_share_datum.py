from sqlalchemy import (
    Column, BigInteger, SmallInteger, String, Numeric, DateTime,
    ForeignKey, UniqueConstraint, CheckConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class PerShareDatum(Base):
    __tablename__ = "per_share_data"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    company_id = Column(BigInteger, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    source = Column(String(10), nullable=False, default="CFRA")
    fiscal_year = Column(SmallInteger, nullable=False)

    tangible_book_value = Column(Numeric(10, 4))
    free_cash_flow = Column(Numeric(10, 4))
    earnings = Column(Numeric(10, 4))
    earnings_normalized = Column(Numeric(10, 4))
    dividends = Column(Numeric(10, 4))
    payout_ratio_pct = Column(Numeric(6, 2))
    price_high = Column(Numeric(12, 4))
    price_low = Column(Numeric(12, 4))
    pe_high = Column(Numeric(8, 2))
    pe_low = Column(Numeric(8, 2))

    # Meta
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("company_id", "source", "fiscal_year", name="uq_per_share_data_company_source_year"),
        CheckConstraint("source IN ('CFRA', 'Zacks')", name="chk_per_share_data_source"),
    )

    # Relationships
    company = relationship("Company", back_populates="per_share_data")
