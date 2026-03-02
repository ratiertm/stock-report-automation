"""Alert model for tracking report change notifications."""

from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, JSON
from sqlalchemy.sql import func

from app.database import Base


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True)
    ticker = Column(String(20), nullable=False, index=True)
    source = Column(String(50))
    alert_type = Column(String(50), nullable=False)  # "rating_change", "target_price_change", etc.
    field = Column(String(50))
    old_value = Column(String(200))
    new_value = Column(String(200))
    message = Column(Text)
    notified = Column(Boolean, default=False)
    notified_at = Column(DateTime)
    created_at = Column(DateTime, server_default=func.now())
    metadata_ = Column("metadata", JSON)
