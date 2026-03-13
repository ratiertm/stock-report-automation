from sqlalchemy import (
    Column, BigInteger, String, SmallInteger, Numeric, DateTime,
    ForeignKey, CheckConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class ReportRating(Base):
    __tablename__ = "report_ratings"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    report_id = Column(BigInteger, ForeignKey("reports.id", ondelete="CASCADE"), nullable=False, unique=True)

    # CFRA fields
    recommendation = Column(String(20))
    stars_rating = Column(SmallInteger)
    risk_assessment = Column(String(10))
    fair_value = Column(Numeric(12, 4))
    fair_value_rank = Column(SmallInteger)
    volatility = Column(String(10))
    technical_eval = Column(String(10))
    insider_activity = Column(String(15))
    investment_style = Column(String(30))
    quality_ranking = Column(String(5))

    # Zacks fields
    zacks_rank = Column(SmallInteger)
    zacks_rank_label = Column(String(20))
    prior_recommendation = Column(String(20))
    style_scores = Column(JSONB)

    # Meta
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        CheckConstraint("stars_rating BETWEEN 1 AND 5", name="chk_report_ratings_stars"),
        CheckConstraint("zacks_rank BETWEEN 1 AND 5", name="chk_report_ratings_zacks_rank"),
        CheckConstraint("fair_value_rank BETWEEN 1 AND 5", name="chk_report_ratings_fv_rank"),
    )

    # Relationships
    report = relationship("Report", back_populates="rating")
