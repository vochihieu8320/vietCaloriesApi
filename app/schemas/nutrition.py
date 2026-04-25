from typing import Literal

from pydantic import BaseModel, Field


class NutritionData(BaseModel):
    calories_kcal: int = Field(ge=0)
    protein_g: float = Field(ge=0)
    carbs_g: float = Field(ge=0)
    fat_g: float = Field(ge=0)


class AnalyzeResponse(BaseModel):
    success: bool = True
    dish_name: str
    confidence: Literal["high", "medium", "low"]
    nutrition: NutritionData
    notes: str | None = None


class ErrorResponse(BaseModel):
    success: bool = False
    error: str
    error_code: str


class AnalyzeRequestBase64(BaseModel):
    image_base64: str
    media_type: str
