from sqlalchemy import (
    Column, BigInteger, String, Text, Numeric, DateTime,
    ForeignKey,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class AnalystNote(Base):
    __tablename__ = "analyst_notes"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    company_id = Column(BigInteger, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    source = Column(String(10), nullable=False, default="CFRA")
    published_at = Column(DateTime(timezone=True))
    analyst_name = Column(String(100))
    title = Column(String(500))
    stock_price_at_note = Column(Numeric(12, 4))
    action = Column(String(20))
    target_price = Column(Numeric(12, 4))
    content = Column(Text)

    # Meta
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    # Relationships
    company = relationship("Company", back_populates="analyst_notes_v2")
