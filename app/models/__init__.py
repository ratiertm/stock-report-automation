from app.database import Base
from app.models.stock_profile import StockProfile
from app.models.stock_report import StockReport
from app.models.stock_financial import StockFinancial
from app.models.stock_balance_sheet import StockBalanceSheet
from app.models.stock_key_stat import StockKeyStat
from app.models.stock_peer import StockPeer
from app.models.stock_analyst_note import StockAnalystNote
from app.models.watchlist import Watchlist, WatchlistItem
from app.models.alert import Alert
from app.models.api_key import ApiKey

# v2 schema models
from app.models.v2 import (
    Company, Report, ReportRating, ReportKeyStat, ReportTextSection,
    Financial, BalanceSheet, IncomeStatement, PerShareDatum,
    ConsensusEstimate, AnalystNote, PeerComparison, CompanyEvent,
)

__all__ = [
    "Base",
    # v1 models
    "StockProfile",
    "StockReport",
    "StockFinancial",
    "StockBalanceSheet",
    "StockKeyStat",
    "StockPeer",
    "StockAnalystNote",
    "Watchlist",
    "WatchlistItem",
    "Alert",
    "ApiKey",
    # v2 models
    "Company",
    "Report",
    "ReportRating",
    "ReportKeyStat",
    "ReportTextSection",
    "Financial",
    "BalanceSheet",
    "IncomeStatement",
    "PerShareDatum",
    "ConsensusEstimate",
    "AnalystNote",
    "PeerComparison",
    "CompanyEvent",
]
