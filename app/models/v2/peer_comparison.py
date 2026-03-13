from sqlalchemy import (
    Column, BigInteger, SmallInteger, String, DateTime,
    ForeignKey, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class PeerComparison(Base):
    __tablename__ = "peer_comparisons"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    report_id = Column(BigInteger, ForeignKey("reports.id", ondelete="CASCADE"), nullable=False)
    peer_ticker = Column(String(10), nullable=False)
    peer_name = Column(String(200))

    # Common metrics
    recommendation = Column(String(20))
    rank = Column(SmallInteger)

    # Source-specific detailed metrics as JSONB
    metrics = Column(JSONB)

    # Meta
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("report_id", "peer_ticker", name="uq_peer_comparisons_report_ticker"),
    )

    # Relationships
    report = relationship("Report", back_populates="peer_comparisons")
