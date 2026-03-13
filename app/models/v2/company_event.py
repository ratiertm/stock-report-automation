from sqlalchemy import (
    Column, BigInteger, String, Date, Text, DateTime,
    ForeignKey, UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class CompanyEvent(Base):
    __tablename__ = "company_events"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    company_id = Column(BigInteger, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    source = Column(String(10), nullable=False, default="Zacks")
    event_date = Column(Date)
    headline = Column(Text, nullable=False)
    content = Column(Text)

    # Meta
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("company_id", "source", "event_date", "headline",
                         name="uq_company_events_company_source_date_headline"),
    )

    # Relationships
    company = relationship("Company", back_populates="company_events")
