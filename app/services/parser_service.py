"""Parser Service: orchestrates PDF parsing → DB storage."""

import os
from dataclasses import asdict

from sqlalchemy.orm import Session

from app.parsers import CFRAParser, ZacksParser
from app.crud.stock import (
    upsert_profile, upsert_report, upsert_financial, upsert_balance_sheet,
    upsert_key_stats, save_peers, save_analyst_notes,
)


def parse_and_store(pdf_path: str, source: str, session: Session) -> dict:
    """Parse a PDF and store all extracted data in the database.

    Args:
        pdf_path: Path to the PDF file
        source: "CFRA" or "Zacks"
        session: SQLAlchemy session

    Returns:
        dict with ticker, source, counts, errors, warnings
    """
    source = source.upper()

    # 1. Parse
    if source == "CFRA":
        parser = CFRAParser()
        result = parser.parse(pdf_path)
        data = {
            "profile": asdict(result.profile),
            "report": asdict(result.report),
            "key_stats": asdict(result.key_stats),
            "financials": [asdict(f) for f in result.financials],
            "analyst_notes": [asdict(n) for n in result.analyst_notes],
            "balance_sheets": [asdict(b) for b in result.balance_sheets],
            "peers": [],
        }
        errors = result.errors
        warnings = result.warnings
    elif source == "ZACKS":
        parser = ZacksParser()
        result = parser.parse(pdf_path)
        data = {
            "profile": asdict(result.profile),
            "report": asdict(result.report),
            "key_stats": asdict(result.key_stats),
            "financials": [asdict(f) for f in result.financials],
            "peers": [asdict(p) for p in result.peers],
            "analyst_notes": [],
            "balance_sheets": [],
        }
        errors = result.errors
        warnings = result.warnings
    else:
        return {"error": f"Unknown source: {source}"}

    if errors:
        return {"error": errors[0], "errors": errors, "warnings": warnings}

    ticker = data["profile"].get("ticker", "UNKNOWN")

    # 2. Upsert profile
    profile = upsert_profile(session, data["profile"])

    # 3. Upsert report
    report_data = data["report"]
    report_data["source"] = source
    report = upsert_report(session, profile.id, report_data, pdf_path=pdf_path)

    # 4. Upsert key_stats
    stats_count = 0
    if data.get("key_stats"):
        non_none = {k: v for k, v in data["key_stats"].items() if v is not None}
        if non_none:
            upsert_key_stats(session, report.id, data["key_stats"])
            stats_count = 1

    # 5. Upsert financials
    fin_count = 0
    for fin in data.get("financials", []):
        if fin.get("fiscal_year"):
            upsert_financial(session, profile.id, fin)
            fin_count += 1

    # 6. Upsert balance sheets (CFRA)
    bs_count = 0
    for bs in data.get("balance_sheets", []):
        if bs.get("fiscal_year"):
            upsert_balance_sheet(session, profile.id, bs)
            bs_count += 1

    # 7. Save peers (Zacks)
    peer_count = 0
    if data.get("peers"):
        save_peers(session, report.id, data["peers"])
        peer_count = len(data["peers"])

    # 8. Save analyst notes (CFRA)
    notes_count = 0
    if data.get("analyst_notes"):
        save_analyst_notes(session, profile.id, source, data["analyst_notes"])
        notes_count = len(data["analyst_notes"])

    session.commit()

    return {
        "status": "success",
        "ticker": ticker,
        "source": source,
        "report_date": str(report.report_date),
        "records_saved": {
            "profile": 1,
            "report": 1,
            "financials": fin_count,
            "balance_sheets": bs_count,
            "key_stats": stats_count,
            "peers": peer_count,
            "analyst_notes": notes_count,
        },
        "errors": errors,
        "warnings": warnings,
    }
