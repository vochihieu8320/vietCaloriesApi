import pytest
from pydantic import ValidationError

from app.schemas.nutrition import (
    AnalyzeRequestBase64,
    AnalyzeResponse,
    ErrorResponse,
    NutritionData,
)


def test_nutrition_data_accepts_valid():
    n = NutritionData(calories_kcal=480, protein_g=28, carbs_g=62, fat_g=10)
    assert n.calories_kcal == 480


def test_nutrition_data_rejects_negative():
    with pytest.raises(ValidationError):
        NutritionData(calories_kcal=-1, protein_g=0, carbs_g=0, fat_g=0)


def test_analyze_response_defaults_success_true():
    r = AnalyzeResponse(
        dish_name="Phở bò",
        confidence="high",
        nutrition=NutritionData(calories_kcal=480, protein_g=28, carbs_g=62, fat_g=10),
    )
    assert r.success is True
    assert r.notes is None


def test_analyze_response_rejects_bad_confidence():
    with pytest.raises(ValidationError):
        AnalyzeResponse(
            dish_name="x",
            confidence="very-high",  # not in allowed literal
            nutrition=NutritionData(calories_kcal=1, protein_g=0, carbs_g=0, fat_g=0),
        )


def test_error_response_defaults_success_false():
    e = ErrorResponse(error="bad", error_code="INVALID_IMAGE")
    assert e.success is False


def test_analyze_request_base64_requires_both_fields():
    with pytest.raises(ValidationError):
        AnalyzeRequestBase64(image_base64="abc")  # missing media_type
