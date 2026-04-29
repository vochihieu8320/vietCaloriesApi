from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class UserRead(BaseModel):
    """Response shape for /me endpoints."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    display_name: str | None
    avatar_url: str | None
    created_at: datetime


class UserUpdate(BaseModel):
    """Request body for PATCH /me. All fields optional; unset fields are not modified."""

    display_name: str | None = None
    avatar_url: str | None = None
