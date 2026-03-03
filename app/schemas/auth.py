"""Pydantic schemas for API key authentication."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ApiKeyCreate(BaseModel):
    name: str
    organization_id: Optional[int] = None


class ApiKeyOut(BaseModel):
    id: int
    key_prefix: str
    name: str
    is_active: bool
    created_at: Optional[datetime] = None
    last_used_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ApiKeyCreated(BaseModel):
    id: int
    key: str
    key_prefix: str
    name: str
    message: str = "Store this key securely. It will not be shown again."
