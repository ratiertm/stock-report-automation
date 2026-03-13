from sqlalchemy import (
    Column, BigInteger, String, SmallInteger, Integer, Text, DateTime,
    UniqueConstraint, CheckConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class Company(Base):
    __tablename__ = "companies"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    ticker = Column(String(10), nullable=False, unique=True)
    company_name = Column(String(200))
    exchange = Column(String(20))
    currency = Column(String(3), default="USD")

    # GICS classification (CFRA)
    gics_sector = Column(String(100))
    gics_sub_industry = Column(String(100))

    # Zacks classification
    zacks_industry = Column(String(100))
    zacks_industry_rank = Column(String(100))

    # Company info
    investment_style = Column(String(30))
    website = Column(String(200))
    description = Column(Text)
    domicile = Column(String(50))
    founded_year = Column(SmallInteger)
    employees = Column(Integer)

    # Structured data
    officers = Column(JSONB)
    board_members = Column(JSONB)
    segments = Column(JSONB)
    index_memberships = Column(ARRAY(String(50)))

    # Meta
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    # Relationships
    reports = relationship("Report", back_populates="company", cascade="all, delete-orphan", lazy="selectin")
    financials = relationship("Financial", back_populates="company", cascade="all, delete-orphan", lazy="selectin")
    balance_sheets = relationship("BalanceSheet", back_populates="company", cascade="all, delete-orphan", lazy="selectin")
    income_statements = relationship("IncomeStatement", back_populates="company", cascade="all, delete-orphan", lazy="selectin")
    per_share_data = relationship("PerShareDatum", back_populates="company", cascade="all, delete-orphan", lazy="selectin")
    consensus_estimates = relationship("ConsensusEstimate", back_populates="company", cascade="all, delete-orphan", lazy="selectin")
    analyst_notes_v2 = relationship("AnalystNote", back_populates="company", cascade="all, delete-orphan", lazy="selectin")
    company_events = relationship("CompanyEvent", back_populates="company", cascade="all, delete-orphan", lazy="selectin")
