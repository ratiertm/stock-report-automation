from sqlalchemy import (
    Column, BigInteger, String, Integer, Date, Text, Numeric, DateTime,
    ForeignKey, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class StockReport(Base):
    __tablename__ = "stock_reports"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    stock_profile_id = Column(BigInteger, ForeignKey("stock_profiles.id"), nullable=False)
    source = Column(String(50), nullable=False)
    report_date = Column(Date, nullable=False)
    analyst_name = Column(String(100))
    recommendation = Column(String(20))
    prior_recommendation = Column(String(20))
    stars_rating = Column(Integer)
    zacks_rank = Column(Integer)
    zacks_rank_label = Column(String(20))
    style_scores = Column(JSONB)
    target_price = Column(Numeric(12, 2))
    current_price = Column(Numeric(12, 2))
    price_date = Column(Date)
    risk_assessment = Column(String(20))
    fair_value = Column(Numeric(12, 2))
    fair_value_rank = Column(Integer)
    volatility = Column(String(20))
    technical_eval = Column(String(20))
    insider_activity = Column(String(20))
    investment_style = Column(String(50))
    industry_rank = Column(String(100))
    highlights = Column(Text)
    reasons_to_buy = Column(Text)
    reasons_to_sell = Column(Text)
    investment_rationale = Column(Text)
    business_summary = Column(Text)
    sub_industry_outlook = Column(Text)
    last_earnings_summary = Column(Text)
    outlook = Column(Text)
    recent_news = Column(JSONB)
    raw_pdf_path = Column(String(500))
    organization_id = Column(BigInteger)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("stock_profile_id", "source", "report_date",
                         name="uq_report_profile_source_date"),
    )

    profile = relationship("StockProfile", back_populates="reports")
    key_stats = relationship("StockKeyStat", back_populates="report", uselist=False, lazy="selectin")
    peers = relationship("StockPeer", back_populates="report", lazy="selectin")
