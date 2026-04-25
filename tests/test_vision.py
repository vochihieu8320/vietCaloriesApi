import json
import os
from unittest.mock import MagicMock

import httpx
import pytest
from openai import OpenAIError, RateLimitError

# ensure config import doesn't fail
os.environ.setdefault("OPENAI_API_KEY", "test-key-not-real")

from app.errors import LLMError, NoFoodDetectedError, RateLimitedError
from app.services.vision import OpenAIVisionClient


HAPPY_JSON = json.dumps({
    "dish_name": "Phở bò",
    "confidence": "high",
    "nutrition": {"calories_kcal": 480, "protein_g": 28, "carbs_g": 62, "fat_g": 10},
    "notes": "Standard bowl",
})


def _mock_response(content: str) -> MagicMock:
    response = MagicMock()
    response.choices = [MagicMock()]
    response.choices[0].message.content = content
    return response


def _make_rate_limit_error() -> RateLimitError:
    request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    response = httpx.Response(429, request=request)
    return RateLimitError("rate limited", response=response, body={"error": "rate limited"})


@pytest.fixture
def fake_openai():
    return MagicMock()


@pytest.fixture
def vision(fake_openai) -> OpenAIVisionClient:
    return OpenAIVisionClient(client=fake_openai, model="gpt-4o")


def test_happy_path_parses_response(vision, fake_openai):
    fake_openai.chat.completions.create.return_value = _mock_response(HAPPY_JSON)
    result = vision.analyze_food(b"fake-image-bytes", "image/jpeg")
    assert result.dish_name == "Phở bò"
    assert result.nutrition.calories_kcal == 480
    assert result.confidence == "high"


def test_strips_markdown_fences(vision, fake_openai):
    fenced = f"```json\n{HAPPY_JSON}\n```"
    fake_openai.chat.completions.create.return_value = _mock_response(fenced)
    result = vision.analyze_food(b"x", "image/jpeg")
    assert result.dish_name == "Phở bò"


def test_no_food_detected_raises(vision, fake_openai):
    fake_openai.chat.completions.create.return_value = _mock_response(
        json.dumps({"error": "NO_FOOD_DETECTED"})
    )
    with pytest.raises(NoFoodDetectedError):
        vision.analyze_food(b"x", "image/jpeg")


def test_rate_limit_translated(vision, fake_openai):
    fake_openai.chat.completions.create.side_effect = _make_rate_limit_error()
    with pytest.raises(RateLimitedError):
        vision.analyze_food(b"x", "image/jpeg")


def test_generic_openai_error_translated(vision, fake_openai):
    fake_openai.chat.completions.create.side_effect = OpenAIError("boom")
    with pytest.raises(LLMError):
        vision.analyze_food(b"x", "image/jpeg")


def test_unparseable_json_raises_llm_error(vision, fake_openai):
    fake_openai.chat.completions.create.return_value = _mock_response("not json at all")
    with pytest.raises(LLMError):
        vision.analyze_food(b"x", "image/jpeg")


def test_schema_mismatch_raises_llm_error(vision, fake_openai):
    fake_openai.chat.completions.create.return_value = _mock_response(
        json.dumps({"dish_name": "Phở", "confidence": "high"})  # missing nutrition
    )
    with pytest.raises(LLMError):
        vision.analyze_food(b"x", "image/jpeg")


def test_sends_data_url_with_correct_media_type(vision, fake_openai):
    fake_openai.chat.completions.create.return_value = _mock_response(HAPPY_JSON)
    vision.analyze_food(b"hello-bytes", "image/jpeg")
    call_kwargs = fake_openai.chat.completions.create.call_args.kwargs
    user_content = call_kwargs["messages"][1]["content"]
    image_url = next(c for c in user_content if c["type"] == "image_url")["image_url"]["url"]
    assert image_url.startswith("data:image/jpeg;base64,")


def test_empty_choices_raises_llm_error(vision, fake_openai):
    response = MagicMock()
    response.choices = []
    fake_openai.chat.completions.create.return_value = response
    with pytest.raises(LLMError):
        vision.analyze_food(b"x", "image/jpeg")
