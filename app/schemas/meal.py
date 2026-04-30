from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


MealType = Literal["breakfast", "lunch", "snack", "dinner"]
Confidence = Literal["high", "medium", "low"]


class MealCreate(BaseModel):
    """Request body for POST /api/v1/meals."""

    meal_type: MealType
    dish_name: str = Field(min_length=1, max_length=200)
    confidence: Confidence = "medium"
    calories_kcal: int = Field(ge=0)
    protein_g: float = Field(ge=0)
    carbs_g: float = Field(ge=0)
    fat_g: float = Field(ge=0)
    notes: str | None = None
    consumed_at: datetime | None = None  # defaults to now() server-side


class MealUpdate(BaseModel):
    """PATCH body — all fields optional; unset fields are not modified."""

    meal_type: MealType | None = None
    dish_name: str | None = Field(default=None, min_length=1, max_length=200)
    confidence: Confidence | None = None
    calories_kcal: int | None = Field(default=None, ge=0)
    protein_g: float | None = Field(default=None, ge=0)
    carbs_g: float | None = Field(default=None, ge=0)
    fat_g: float | None = Field(default=None, ge=0)
    notes: str | None = None
    consumed_at: datetime | None = None


class MealRead(BaseModel):
    """Response shape for /meals endpoints."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    consumed_at: datetime
    meal_type: str
    dish_name: str
    confidence: str
    calories_kcal: int
    protein_g: float
    carbs_g: float
    fat_g: float
    notes: str | None
    created_at: datetime
