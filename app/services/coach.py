"""Coach: a single-turn 'ask Cal Pal' prompt → LLM → typed response.

Stateless on the server side — the mobile app sends today's state with each
question. We don't persist conversation history yet; that can be added later
if users want multi-turn follow-ups across sessions.
"""

import json
import re
from typing import Any

from openai import OpenAI, OpenAIError, RateLimitError
from pydantic import ValidationError

from ..config import Settings, get_settings
from ..errors import InsufficientQuotaError, LLMError, RateLimitedError
from ..schemas.coach import CoachAskRequest, CoachAskResponse


SYSTEM_PROMPT = """You are Cal Pal, a friendly, plain-spoken nutrition and food coach
who knows Vietnamese cuisine and habits well. You help the user reach their daily
nutrition goals through small, realistic suggestions — never lectures.

Rules:
- Reply in the same language the user wrote in (Vietnamese or English).
- Keep answers short: 1–3 sentences, ideally one paragraph.
- Be specific: name dishes, quantities, or grams when relevant.
- Never invent meals the user hasn't logged. Use only the data given.
- If the user is asking medical advice, decline kindly and suggest a professional.
- Always return ONLY a valid JSON object — no preamble, no markdown fences."""


USER_TEMPLATE = """User question: {question}

Today's state:
- Calories: {today_calories} / {target_calories} kcal
- Protein:  {today_protein:.0f} / {target_protein} g
- Carbs:    {today_carbs:.0f} / {target_carbs} g
- Fat:      {today_fat:.0f} / {target_fat} g
- Water:    {today_water} / {target_water} ml

Today's logged meals:
{recent_meals}

Return a JSON object with exactly these fields:
{{
  "answer": "<your reply, 1–3 sentences>",
  "suggestions": ["<follow-up question 1>", "<follow-up question 2>", "<follow-up question 3>"]
}}

The "suggestions" are short follow-up questions the user could tap next (max 3, max 60 chars each, in the user's language). They MUST be questions the user might ask, NOT statements."""


_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.MULTILINE)


def _strip_fences(text: str) -> str:
    return _FENCE_RE.sub("", text).strip()


def _format_meals(meals: list) -> str:
    if not meals:
        return "(none logged yet)"
    lines = []
    for m in meals:
        lines.append(
            f"- {m.meal_type}: {m.dish_name} · {m.calories_kcal} kcal · "
            f"P{m.protein_g:.0f}g C{m.carbs_g:.0f}g F{m.fat_g:.0f}g"
        )
    return "\n".join(lines)


def _is_quota_exhausted(exc: RateLimitError) -> bool:
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        err = body.get("error")
        if isinstance(err, dict) and err.get("code") == "insufficient_quota":
            return True
    return "insufficient_quota" in str(exc)


class CoachClient:
    """Wraps a chat-completion call to ask the coach a single question."""

    def __init__(self, client: OpenAI, model: str) -> None:
        self._client = client
        self._model = model

    def ask(self, req: CoachAskRequest) -> CoachAskResponse:
        prompt = USER_TEMPLATE.format(
            question=req.question,
            today_calories=req.today_calories,
            target_calories=req.target_calories or "—",
            today_protein=req.today_protein_g,
            target_protein=req.target_protein_g or "—",
            today_carbs=req.today_carbs_g,
            target_carbs=req.target_carbs_g or "—",
            today_fat=req.today_fat_g,
            target_fat=req.target_fat_g or "—",
            today_water=req.today_water_ml,
            target_water=req.target_water_ml or "—",
            recent_meals=_format_meals(req.recent_meals),
        )

        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
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

        try:
            return CoachAskResponse(**parsed)
        except (ValidationError, TypeError) as exc:
            raise LLMError(f"Model output failed schema validation: {exc}") from exc


def get_coach_client(settings: Settings | None = None) -> CoachClient:
    if settings is None:
        settings = get_settings()
    return CoachClient(
        client=OpenAI(api_key=settings.openai_api_key, timeout=30.0),
        model=settings.openai_model,
    )
