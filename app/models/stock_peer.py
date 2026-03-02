from sqlalchemy import (
    Column, BigInteger, String, Integer, Numeric, DateTime, ForeignKey,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class StockPeer(Base):
    __tablename__ = "stock_peers"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    stock_report_id = Column(BigInteger, ForeignKey("stock_reports.id"), nullable=False)
    peer_ticker = Column(String(10))
    peer_name = Column(String(255))
    exchange = Column(String(50))
    recent_price = Column(Numeric(12, 2))
    market_cap_m = Column(Numeric(15, 2))
    price_chg_30d_pct = Column(Numeric(6, 2))
    price_chg_1yr_pct = Column(Numeric(6, 2))
    pe_ratio = Column(Numeric(10, 2))
    fair_value_calc = Column(Numeric(12, 2))
    yield_pct = Column(Numeric(6, 2))
    roe_pct = Column(Numeric(6, 2))
    ltd_to_cap_pct = Column(Numeric(6, 2))
    recommendation = Column(String(20))
    rank = Column(Integer)
    detailed_comparison = Column(JSONB)
    organization_id = Column(BigInteger)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    report = relationship("StockReport", back_populates="peers")
