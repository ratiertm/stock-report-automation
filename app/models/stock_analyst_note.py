from sqlalchemy import (
    Column, BigInteger, String, Text, Numeric, DateTime, ForeignKey,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class StockAnalystNote(Base):
    __tablename__ = "stock_analyst_notes"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    stock_profile_id = Column(BigInteger, ForeignKey("stock_profiles.id"), nullable=False)
    source = Column(String(50))
    published_at = Column(DateTime)
    analyst_name = Column(String(100))
    title = Column(String(500))
    stock_price_at_note = Column(Numeric(12, 2))
    action = Column(String(50))
    target_price = Column(Numeric(12, 2))
    content = Column(Text)
    organization_id = Column(BigInteger)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    profile = relationship("StockProfile", back_populates="analyst_notes")
