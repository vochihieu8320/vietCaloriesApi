from typing import Literal

from pydantic import BaseModel, Field


class CoachMealContext(BaseModel):
    """A single recent meal — keeps the prompt size bounded."""

    meal_type: Literal["breakfast", "lunch", "snack", "dinner"]
    dish_name: str
    calories_kcal: int
    protein_g: float
    carbs_g: float
    fat_g: float


class CoachAskRequest(BaseModel):
    """User question + the day's nutrition state. Mobile sends this; the
    backend uses it to build a single-turn prompt to the LLM."""

    question: str = Field(min_length=1, max_length=500)
    # Today's totals so far, computed client-side from logged meals.
    today_calories: int = Field(ge=0)
    today_protein_g: float = Field(ge=0)
    today_carbs_g: float = Field(ge=0)
    today_fat_g: float = Field(ge=0)
    today_water_ml: int = Field(ge=0)
    # Daily targets (nullable — new users may not have onboarded).
    target_calories: int | None = Field(default=None, ge=0)
    target_protein_g: int | None = Field(default=None, ge=0)
    target_carbs_g: int | None = Field(default=None, ge=0)
    target_fat_g: int | None = Field(default=None, ge=0)
    target_water_ml: int | None = Field(default=None, ge=0)
    # Up to ~5 most-recent meals from today, for context.
    recent_meals: list[CoachMealContext] = Field(default_factory=list, max_length=10)


class CoachAskResponse(BaseModel):
    """Single answer + a few canned follow-up question chips the UI can show
    so the user can keep the conversation going without typing."""

    answer: str
    suggestions: list[str] = Field(default_factory=list, max_length=3)
