from sqlalchemy import (
    Column, BigInteger, String, Boolean, DateTime, ForeignKey, UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class Watchlist(Base):
    __tablename__ = "watchlists"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, default="Default")
    is_default = Column(Boolean, default=False)
    organization_id = Column(BigInteger)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    items = relationship("WatchlistItem", back_populates="watchlist", cascade="all, delete-orphan")


class WatchlistItem(Base):
    __tablename__ = "watchlist_items"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    watchlist_id = Column(BigInteger, ForeignKey("watchlists.id", ondelete="CASCADE"), nullable=False)
    stock_profile_id = Column(BigInteger, ForeignKey("stock_profiles.id"), nullable=False)
    sources = Column(String(100), default="CFRA,ZACKS")  # comma-separated
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("watchlist_id", "stock_profile_id", name="uq_watchlist_item"),
    )

    watchlist = relationship("Watchlist", back_populates="items")
    profile = relationship("StockProfile")
