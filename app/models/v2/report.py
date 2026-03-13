from sqlalchemy import (
    Column, BigInteger, String, Date, Numeric, DateTime,
    ForeignKey, UniqueConstraint, CheckConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class Report(Base):
    __tablename__ = "reports"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    company_id = Column(BigInteger, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    source = Column(String(10), nullable=False)
    report_date = Column(Date, nullable=False)

    # Price snapshot
    current_price = Column(Numeric(12, 4))
    price_date = Column(Date)
    target_price = Column(Numeric(12, 4))

    # Analyst
    analyst_name = Column(String(100))

    # PDF
    raw_pdf_path = Column(String(500))

    # Meta
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("company_id", "source", "report_date", name="uq_reports_company_source_date"),
        CheckConstraint("source IN ('CFRA', 'Zacks')", name="chk_reports_source"),
    )

    # Relationships
    company = relationship("Company", back_populates="reports")
    rating = relationship("ReportRating", back_populates="report", uselist=False, cascade="all, delete-orphan", lazy="selectin")
    key_stats = relationship("ReportKeyStat", back_populates="report", uselist=False, cascade="all, delete-orphan", lazy="selectin")
    text_sections = relationship("ReportTextSection", back_populates="report", cascade="all, delete-orphan", lazy="selectin")
    peer_comparisons = relationship("PeerComparison", back_populates="report", cascade="all, delete-orphan", lazy="selectin")
