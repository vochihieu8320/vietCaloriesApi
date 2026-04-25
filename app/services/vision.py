import base64
import json
import re
from typing import Any

from openai import OpenAI, OpenAIError, RateLimitError
from pydantic import ValidationError

from ..config import Settings, get_settings
from ..errors import InsufficientQuotaError, LLMError, NoFoodDetectedError, RateLimitedError
from ..schemas.nutrition import AnalyzeResponse


SYSTEM_PROMPT = """You are a professional Vietnamese and Asian food nutritionist with deep expertise in Vietnamese cuisine.

You will be given an image of food. Your task is to:
- Identify the dish — use its Vietnamese name if it is a Vietnamese dish
- Estimate the nutrition for the visible portion size
- Return ONLY a valid JSON object — no preamble, no markdown fences"""


USER_PROMPT = """Analyze this food image and return a JSON object with exactly these fields:
{
  "dish_name": "<Vietnamese or English name>",
  "confidence": "<high | medium | low>",
  "nutrition": {
    "calories_kcal": <integer>,
    "protein_g": <number>,
    "carbs_g": <number>,
    "fat_g": <number>
  },
  "notes": "<optional short note about portion or assumptions>"
}

If you cannot identify food in the image, return:
{ "error": "NO_FOOD_DETECTED" }"""


_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.MULTILINE)


def _strip_fences(text: str) -> str:
    return _FENCE_RE.sub("", text).strip()


def _is_quota_exhausted(exc: RateLimitError) -> bool:
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        err = body.get("error")
        if isinstance(err, dict) and err.get("code") == "insufficient_quota":
            return True
    return "insufficient_quota" in str(exc)


class OpenAIVisionClient:
    def __init__(self, client: OpenAI, model: str):
        self._client = client
        self._model = model

    def analyze_food(self, image_bytes: bytes, media_type: str) -> AnalyzeResponse:
        b64 = base64.b64encode(image_bytes).decode("ascii")
        data_url = f"data:{media_type};base64,{b64}"

        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": USER_PROMPT},
                            {"type": "image_url", "image_url": {"url": data_url}},
                        ],
                    },
                ],
            )
        except RateLimitError as exc:
            if _is_quota_exhausted(exc):
                raise InsufficientQuotaError() from exc
            raise RateLimitedError(str(exc)) from exc
        except OpenAIError as exc:
            raise LLMError(f"OpenAI call failed: {exc}") from exc

        if not response.choices:
            raise LLMError("OpenAI returned no choices in response.")
        raw = response.choices[0].message.content or ""
        cleaned = _strip_fences(raw)

        try:
            parsed: Any = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise LLMError(f"Could not parse model output as JSON: {exc}") from exc

        if isinstance(parsed, dict) and parsed.get("error") == "NO_FOOD_DETECTED":
            raise NoFoodDetectedError()

        try:
            return AnalyzeResponse(**parsed)
        except (ValidationError, TypeError) as exc:
            raise LLMError(f"Model output failed schema validation: {exc}") from exc


def get_vision_client(settings: Settings | None = None) -> OpenAIVisionClient:
    if settings is None:
        settings = get_settings()
    return OpenAIVisionClient(
        client=OpenAI(api_key=settings.openai_api_key, timeout=30.0),
        model=settings.openai_model,
    )
