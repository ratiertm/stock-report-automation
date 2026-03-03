"""Admin API key management endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.api.deps import require_admin
from app.crud.api_key import create_api_key, list_api_keys, revoke_api_key
from app.schemas.auth import ApiKeyCreate, ApiKeyOut, ApiKeyCreated

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.post(
    "/keys",
    response_model=ApiKeyCreated,
    dependencies=[Depends(require_admin)],
)
def create_key(body: ApiKeyCreate, db: Session = Depends(get_db)):
    """Issue a new User API key (Admin only)."""
    db_key, raw_key = create_api_key(db, body.name, body.organization_id)
    return ApiKeyCreated(
        id=db_key.id,
        key=raw_key,
        key_prefix=db_key.key_prefix,
        name=db_key.name,
    )


@router.get(
    "/keys",
    response_model=list[ApiKeyOut],
    dependencies=[Depends(require_admin)],
)
def list_keys(db: Session = Depends(get_db)):
    """List all API keys (Admin only)."""
    return list_api_keys(db)


@router.delete(
    "/keys/{key_id}",
    response_model=ApiKeyOut,
    dependencies=[Depends(require_admin)],
)
def delete_key(key_id: int, db: Session = Depends(get_db)):
    """Revoke an API key (Admin only)."""
    db_key = revoke_api_key(db, key_id)
    if db_key is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"API key {key_id} not found",
        )
    return db_key
