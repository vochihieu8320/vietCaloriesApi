from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class WaterLogCreate(BaseModel):
    """Body for POST /api/v1/water — record one drink."""

    amount_ml: int = Field(ge=1, le=5000)
    consumed_at: datetime | None = None  # defaults to now() server-side


class WaterLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    amount_ml: int
    consumed_at: datetime
    created_at: datetime


class WaterTotal(BaseModel):
    """Aggregated total for a date range — used by GET /api/v1/water/today."""

    total_ml: int
    log_count: int
