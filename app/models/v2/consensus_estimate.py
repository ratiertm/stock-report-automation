from sqlalchemy import (
    Column, BigInteger, SmallInteger, Date, Numeric, DateTime,
    ForeignKey, UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class ConsensusEstimate(Base):
    __tablename__ = "consensus_estimates"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    company_id = Column(BigInteger, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    report_id = Column(BigInteger, ForeignKey("reports.id", ondelete="SET NULL"), nullable=True)
    snapshot_date = Column(Date, nullable=False)

    # Analyst Recommendations Distribution
    buy_count = Column(SmallInteger)
    buy_hold_count = Column(SmallInteger)
    hold_count = Column(SmallInteger)
    weak_hold_count = Column(SmallInteger)
    sell_count = Column(SmallInteger)
    no_opinion_count = Column(SmallInteger)
    total_analysts = Column(SmallInteger)

    # EPS Consensus
    fiscal_year = Column(SmallInteger, nullable=False)
    eps_avg = Column(Numeric(10, 4))
    eps_high = Column(Numeric(10, 4))
    eps_low = Column(Numeric(10, 4))
    eps_est_count = Column(SmallInteger)
    estimated_pe = Column(Numeric(10, 2))

    # Meta
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("company_id", "snapshot_date", "fiscal_year",
                         name="uq_consensus_estimates_company_date_year"),
    )

    # Relationships
    company = relationship("Company", back_populates="consensus_estimates")
