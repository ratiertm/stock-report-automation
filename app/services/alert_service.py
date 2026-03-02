"""Alert Service: creates alerts from detected changes and sends notifications."""

import logging
import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional

from sqlalchemy.orm import Session

from app.models.alert import Alert
from app.services.content_service import detect_changes_batch
from app.config import settings

logger = logging.getLogger(__name__)


def check_and_alert(session: Session, tickers: list[str]) -> list[dict]:
    """Check for changes in given tickers and create alert records.

    Returns list of new alerts created.
    """
    changed = detect_changes_batch(session, tickers)
    new_alerts = []

    for item in changed:
        for change in item["changes"]:
            alert = Alert(
                ticker=item["ticker"],
                source=change["source"],
                alert_type=f"{change['field']}_change",
                field=change["field"],
                old_value=change["old_value"],
                new_value=change["new_value"],
                message=_build_message(item, change),
            )
            session.add(alert)
            new_alerts.append({
                "ticker": item["ticker"],
                "source": change["source"],
                "type": alert.alert_type,
                "message": alert.message,
            })

    if new_alerts:
        session.commit()
        logger.info(f"Created {len(new_alerts)} alerts")

    return new_alerts


def get_pending_alerts(session: Session, limit: int = 50) -> list[Alert]:
    """Get alerts not yet notified."""
    return list(
        session.query(Alert)
        .filter(Alert.notified == False)
        .order_by(Alert.created_at.desc())
        .limit(limit)
        .all()
    )


def mark_notified(session: Session, alert_ids: list[int]):
    """Mark alerts as notified."""
    session.query(Alert).filter(Alert.id.in_(alert_ids)).update(
        {"notified": True, "notified_at": datetime.utcnow()},
        synchronize_session=False,
    )
    session.commit()


def send_email_alerts(session: Session) -> dict:
    """Send pending alerts via email.

    Requires settings: alert_email_to, alert_smtp_host, alert_smtp_port,
    alert_smtp_user, alert_smtp_pass
    """
    if not getattr(settings, "alert_email_to", None):
        return {"status": "skipped", "reason": "alert_email_to not configured"}

    pending = get_pending_alerts(session)
    if not pending:
        return {"status": "ok", "sent": 0}

    body = _build_email_body(pending)

    try:
        msg = MIMEMultipart()
        msg["Subject"] = f"Stock Report Alert: {len(pending)} changes detected"
        msg["From"] = getattr(settings, "alert_smtp_user", "alerts@stockhub.local")
        msg["To"] = settings.alert_email_to
        msg.attach(MIMEText(body, "plain"))

        smtp_host = getattr(settings, "alert_smtp_host", "localhost")
        smtp_port = getattr(settings, "alert_smtp_port", 587)

        with smtplib.SMTP(smtp_host, smtp_port) as server:
            smtp_user = getattr(settings, "alert_smtp_user", None)
            smtp_pass = getattr(settings, "alert_smtp_pass", None)
            if smtp_user and smtp_pass:
                server.starttls()
                server.login(smtp_user, smtp_pass)
            server.send_message(msg)

        alert_ids = [a.id for a in pending]
        mark_notified(session, alert_ids)
        logger.info(f"Sent email with {len(pending)} alerts to {settings.alert_email_to}")
        return {"status": "ok", "sent": len(pending)}

    except Exception as e:
        logger.error(f"Email send error: {e}")
        return {"status": "error", "error": str(e)}


def _build_message(item: dict, change: dict) -> str:
    return (
        f"{item['ticker']} ({item.get('company_name', '')}): "
        f"{change['label']} changed from {change['old_value']} to {change['new_value']} "
        f"({change['source']}, {change['new_date']})"
    )


def _build_email_body(alerts: list[Alert]) -> str:
    lines = ["Stock Report Hub - Change Alerts", "=" * 40, ""]
    for a in alerts:
        lines.append(f"[{a.ticker}] {a.message}")
        lines.append(f"  Created: {a.created_at}")
        lines.append("")
    lines.append(f"Total: {len(alerts)} alerts")
    return "\n".join(lines)
