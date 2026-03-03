"""CRUD operations for API key management."""

import hashlib
import secrets
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.api_key import ApiKey


def generate_api_key() -> tuple[str, str]:
    """Generate a new API key and its SHA-256 hash.

    Returns (raw_key, key_hash).
    """
    raw = "sk_live_" + secrets.token_urlsafe(32)
    return raw, hash_key(raw)


def hash_key(raw: str) -> str:
    """SHA-256 hash of an API key."""
    return hashlib.sha256(raw.encode()).hexdigest()


def create_api_key(
    session: Session, name: str, organization_id: Optional[int] = None
) -> tuple[ApiKey, str]:
    """Create a new API key record. Returns (db_record, raw_key)."""
    raw_key, key_hash = generate_api_key()
    key_prefix = raw_key[:12]
    db_key = ApiKey(
        key_hash=key_hash,
        key_prefix=key_prefix,
        name=name,
        organization_id=organization_id,
    )
    session.add(db_key)
    session.commit()
    session.refresh(db_key)
    return db_key, raw_key


def get_key_by_hash(session: Session, key_hash: str) -> Optional[ApiKey]:
    """Look up an active API key by its hash."""
    stmt = select(ApiKey).where(ApiKey.key_hash == key_hash, ApiKey.is_active.is_(True))
    return session.scalars(stmt).first()


def list_api_keys(session: Session) -> list[ApiKey]:
    """List all API keys (active and revoked)."""
    stmt = select(ApiKey).order_by(ApiKey.created_at.desc())
    return list(session.scalars(stmt).all())


def revoke_api_key(session: Session, key_id: int) -> Optional[ApiKey]:
    """Revoke an API key by ID. Returns None if not found."""
    db_key = session.get(ApiKey, key_id)
    if db_key is None:
        return None
    db_key.is_active = False
    db_key.revoked_at = datetime.utcnow()
    session.commit()
    session.refresh(db_key)
    return db_key


def update_last_used(session: Session, db_key: ApiKey) -> None:
    """Update the last_used_at timestamp."""
    db_key.last_used_at = datetime.utcnow()
    session.commit()
