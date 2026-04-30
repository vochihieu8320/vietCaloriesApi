from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


Gender = Literal["male", "female", "other"]
ActivityLevel = Literal["sedentary", "light", "moderate", "very", "extreme"]
Goal = Literal["lose", "maintain", "gain"]
Pace = Literal["slowly", "steadily", "aggressively"]


class UserRead(BaseModel):
    """Response shape for /me endpoints."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    display_name: str | None
    avatar_url: str | None
    onboarding_step: str | None
    onboarding_completed_at: datetime | None

    gender: Gender | None
    dob: date | None
    height_cm: float | None
    weight_kg: float | None
    target_weight_kg: float | None
    activity_level: ActivityLevel | None
    goal: Goal | None
    pace: Pace | None

    target_calories_kcal: int | None
    target_protein_g: int | None
    target_carbs_g: int | None
    target_fat_g: int | None
    target_water_ml: int | None

    created_at: datetime


class UserUpdate(BaseModel):
    """Request body for PATCH /me. All fields optional; unset fields are not modified."""

    display_name: str | None = None
    avatar_url: str | None = None
    onboarding_step: str | None = None
    onboarding_completed_at: datetime | None = None

    gender: Gender | None = None
    dob: date | None = None
    height_cm: float | None = Field(default=None, gt=0, le=300)
    weight_kg: float | None = Field(default=None, gt=0, le=500)
    target_weight_kg: float | None = Field(default=None, gt=0, le=500)
    activity_level: ActivityLevel | None = None
    goal: Goal | None = None
    pace: Pace | None = None

    target_calories_kcal: int | None = Field(default=None, ge=0, le=20000)
    target_protein_g: int | None = Field(default=None, ge=0, le=1000)
    target_carbs_g: int | None = Field(default=None, ge=0, le=2000)
    target_fat_g: int | None = Field(default=None, ge=0, le=1000)
    target_water_ml: int | None = Field(default=None, ge=0, le=20000)
