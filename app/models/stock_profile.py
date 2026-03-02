from sqlalchemy import (
    Column, BigInteger, String, Integer, Text, DateTime, ARRAY, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class StockProfile(Base):
    __tablename__ = "stock_profiles"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    ticker = Column(String(10), nullable=False, index=True)
    company_name = Column(String(255))
    exchange = Column(String(50))
    currency = Column(String(10), default="USD")
    gics_sector = Column(String(100))
    gics_sub_industry = Column(String(100))
    industry = Column(String(100))
    domicile = Column(String(100))
    founded_year = Column(Integer)
    employees = Column(Integer)
    website = Column(String(255))
    description = Column(Text)
    segments = Column(JSONB)
    geo_breakdown = Column(JSONB)
    officers = Column(JSONB)
    board_members = Column(JSONB)
    index_memberships = Column(ARRAY(String))
    organization_id = Column(BigInteger)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("ticker", "exchange", name="uq_profile_ticker_exchange"),
    )

    reports = relationship("StockReport", back_populates="profile", lazy="selectin")
    financials = relationship("StockFinancial", back_populates="profile", lazy="selectin")
    balance_sheets = relationship("StockBalanceSheet", back_populates="profile", lazy="selectin")
    analyst_notes = relationship("StockAnalystNote", back_populates="profile", lazy="selectin")
