from sqlalchemy import (
    Column, BigInteger, String, Text, DateTime,
    ForeignKey, UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class ReportTextSection(Base):
    __tablename__ = "report_text_sections"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    report_id = Column(BigInteger, ForeignKey("reports.id", ondelete="CASCADE"), nullable=False)
    section_type = Column(String(30), nullable=False)
    content = Column(Text, nullable=False)

    # Meta
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("report_id", "section_type", name="uq_report_text_sections_report_type"),
    )

    # Relationships
    report = relationship("Report", back_populates="text_sections")
