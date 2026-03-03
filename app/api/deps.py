"""FastAPI authentication dependencies."""

import secrets

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.crud.api_key import hash_key, get_key_by_hash, update_last_used

api_key_header = APIKeyHeader(name="X-API-Key")


def verify_api_key(
    key: str = Security(api_key_header),
    db: Session = Depends(get_db),
) -> str:
    """Verify API key: accept Admin key (.env) or User key (DB).

    Returns "admin" or "user" indicating the key level.
    """
    # Check admin key first (timing-safe comparison)
    if settings.admin_api_key and secrets.compare_digest(key, settings.admin_api_key):
        return "admin"

    # Check user key in DB
    db_key = get_key_by_hash(db, hash_key(key))
    if db_key is not None:
        update_last_used(db, db_key)
        return "user"

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing API key",
    )


def require_admin(
    key: str = Security(api_key_header),
) -> str:
    """Require Admin key (.env) only. Used for /api/admin/* endpoints."""
    if not settings.admin_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin API key not configured on server",
        )
    if secrets.compare_digest(key, settings.admin_api_key):
        return "admin"

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Admin access required",
    )
