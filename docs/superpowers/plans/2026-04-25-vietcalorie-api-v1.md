# VietCalorie API v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the VietCalorie v1 backend — a local-first FastAPI service that estimates nutrition from food images via GPT-4o Vision, returning structured JSON.

**Architecture:** Stateless REST API. Pure validation in `services/image.py`, OpenAI integration behind a DI seam in `services/vision.py`, FastAPI route layer in `routes/analyze.py`. AppError exception hierarchy mapped to PRD error codes by a single handler. Tests are mocked by default; opt-in `pytest -m live` hits real GPT-4o.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, pydantic-settings, Pillow, OpenAI SDK, pytest, ruff.

**Spec reference:** `docs/superpowers/specs/2026-04-25-vietcalorie-api-design.md`

**Working directory for all commands:** `/Users/hieuvo/Documents/vietcalorie-api/`

---

## File Map

**Will create:**
- `requirements.txt`, `pyproject.toml`, `.env.example`, `README.md`
- `app/__init__.py`, `app/main.py`, `app/config.py`, `app/errors.py`
- `app/routes/__init__.py`, `app/routes/analyze.py`
- `app/services/__init__.py`, `app/services/image.py`, `app/services/vision.py`
- `app/schemas/__init__.py`, `app/schemas/nutrition.py`
- `tests/__init__.py`, `tests/conftest.py`
- `tests/test_image.py`, `tests/test_vision.py`, `tests/test_analyze.py`, `tests/test_live.py`
- `tests/fixtures/.gitkeep` (placeholder; user supplies `pho.jpg` separately)

**Already exists (committed):**
- `.gitignore`, `docs/superpowers/specs/2026-04-25-vietcalorie-api-design.md`

---

## Task 1: Project Scaffolding

**Files:**
- Create: `requirements.txt`
- Create: `pyproject.toml`
- Create: `.env.example`
- Create: `app/__init__.py`, `app/routes/__init__.py`, `app/services/__init__.py`, `app/schemas/__init__.py`
- Create: `tests/__init__.py`, `tests/fixtures/.gitkeep`

- [ ] **Step 1: Create `requirements.txt`**

```
fastapi>=0.110.0
uvicorn[standard]>=0.27.0
python-multipart>=0.0.9
pydantic>=2.6.0
pydantic-settings>=2.2.0
Pillow>=10.2.0
openai>=1.30.0
python-dotenv>=1.0.0

# dev
pytest>=8.0.0
httpx>=0.26.0
ruff>=0.3.0
```

- [ ] **Step 2: Create `pyproject.toml`**

```toml
[tool.pytest.ini_options]
markers = [
    "live: tests that hit real OpenAI API (skipped by default; opt in with -m live)"
]
addopts = "-m 'not live'"
testpaths = ["tests"]

[tool.ruff]
line-length = 100
target-version = "py312"
```

- [ ] **Step 3: Create `.env.example`**

```
OPENAI_API_KEY=sk-replace-me
OPENAI_MODEL=gpt-4o
```

- [ ] **Step 4: Create empty package init files**

Create each of these as empty files:
- `app/__init__.py`
- `app/routes/__init__.py`
- `app/services/__init__.py`
- `app/schemas/__init__.py`
- `tests/__init__.py`

Create `tests/fixtures/.gitkeep` as an empty file (placeholder so the directory exists in git).

- [ ] **Step 5: Set up venv and install dependencies**

Run:
```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
```
Expected: clean install, no errors. The venv goes in `.venv/` which `.gitignore` already excludes.

- [ ] **Step 6: Verify pytest discovery works**

Run: `pytest --collect-only`
Expected: exits 0 (no tests yet, that's fine — just confirms config is valid).

- [ ] **Step 7: Commit**

```bash
git add requirements.txt pyproject.toml .env.example app/ tests/
git commit -m "chore: scaffold project structure and dependencies"
```

---

## Task 2: Config Module

**Files:**
- Create: `app/config.py`
- Test: (no separate test file — covered indirectly by other tests)

- [ ] **Step 1: Implement `app/config.py`**

```python
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    openai_api_key: str
    openai_model: str = "gpt-4o"
    max_image_bytes: int = 10 * 1024 * 1024
    cors_origins: list[str] = ["*"]

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 2: Smoke-test the import**

Run:
```bash
OPENAI_API_KEY=test-key python -c "from app.config import get_settings; s = get_settings(); print(s.openai_model, s.max_image_bytes)"
```
Expected output: `gpt-4o 10485760`

- [ ] **Step 3: Commit**

```bash
git add app/config.py
git commit -m "feat(config): add Settings loader for env vars"
```

---

## Task 3: Pydantic Schemas

**Files:**
- Create: `app/schemas/nutrition.py`
- Test: `tests/test_schemas.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_schemas.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_schemas.py -v`
Expected: ImportError or test failures (module doesn't exist yet).

- [ ] **Step 3: Implement `app/schemas/nutrition.py`**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_schemas.py -v`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add app/schemas/nutrition.py tests/test_schemas.py
git commit -m "feat(schemas): add Pydantic models for request/response/error"
```

---

## Task 4: Error Classes

**Files:**
- Create: `app/errors.py` (exception classes only — handler registration added in Task 7)
- Test: `tests/test_errors.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_errors.py`:

```python
import pytest

from app.errors import (
    AppError,
    InvalidImageError,
    LLMError,
    NoFoodDetectedError,
    RateLimitedError,
    UnsupportedFormatError,
)


@pytest.mark.parametrize(
    "exc_cls,expected_code,expected_status",
    [
        (InvalidImageError, "INVALID_IMAGE", 400),
        (UnsupportedFormatError, "UNSUPPORTED_FORMAT", 422),
        (NoFoodDetectedError, "NO_FOOD_DETECTED", 400),
        (LLMError, "LLM_ERROR", 500),
        (RateLimitedError, "RATE_LIMITED", 429),
    ],
)
def test_each_error_has_code_and_status(exc_cls, expected_code, expected_status):
    err = exc_cls()
    assert err.error_code == expected_code
    assert err.http_status == expected_status
    assert isinstance(err, AppError)
    assert err.message  # non-empty default message


def test_custom_message_preserved():
    err = InvalidImageError("custom reason")
    assert err.message == "custom reason"
    assert str(err) == "custom reason"


def test_default_message_used_when_none_passed():
    err = InvalidImageError()
    assert "invalid" in err.message.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_errors.py -v`
Expected: ImportError (module doesn't exist).

- [ ] **Step 3: Implement `app/errors.py` (classes only)**

```python
class AppError(Exception):
    error_code: str = "APP_ERROR"
    message: str = "An error occurred."
    http_status: int = 500

    def __init__(self, message: str | None = None):
        if message is not None:
            self.message = message
        super().__init__(self.message)


class InvalidImageError(AppError):
    error_code = "INVALID_IMAGE"
    message = "The provided image is invalid or could not be read."
    http_status = 400


class UnsupportedFormatError(AppError):
    error_code = "UNSUPPORTED_FORMAT"
    message = "Image format not supported. Use JPEG, PNG, or WEBP."
    http_status = 422


class NoFoodDetectedError(AppError):
    error_code = "NO_FOOD_DETECTED"
    message = "Could not detect food in the provided image."
    http_status = 400


class LLMError(AppError):
    error_code = "LLM_ERROR"
    message = "OpenAI call failed or returned an unparseable response."
    http_status = 500


class RateLimitedError(AppError):
    error_code = "RATE_LIMITED"
    message = "Too many requests. Please retry after a short delay."
    http_status = 429
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_errors.py -v`
Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add app/errors.py tests/test_errors.py
git commit -m "feat(errors): add AppError hierarchy mapped to PRD error codes"
```

---

## Task 5: Image Service

**Files:**
- Create: `app/services/image.py`
- Test: `tests/test_image.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_image.py`:

```python
import io
import os

import pytest
from PIL import Image

# ensure config import doesn't fail
os.environ.setdefault("OPENAI_API_KEY", "test-key-not-real")

from app.errors import InvalidImageError, UnsupportedFormatError
from app.services.image import validate_and_normalize


def _make_image_bytes(width: int, height: int, fmt: str = "JPEG") -> bytes:
    image = Image.new("RGB", (width, height), color=(255, 0, 0))
    out = io.BytesIO()
    image.save(out, format=fmt)
    return out.getvalue()


def test_rejects_unsupported_media_type():
    with pytest.raises(UnsupportedFormatError):
        validate_and_normalize(b"\x00\x01\x02", "image/gif")


def test_rejects_empty_payload():
    with pytest.raises(InvalidImageError):
        validate_and_normalize(b"", "image/jpeg")


def test_rejects_oversized_payload():
    big = _make_image_bytes(200, 200) + b"\x00" * (11 * 1024 * 1024)
    with pytest.raises(InvalidImageError):
        validate_and_normalize(big, "image/jpeg")


def test_rejects_undecodable_bytes():
    with pytest.raises(InvalidImageError):
        validate_and_normalize(b"not an image", "image/jpeg")


def test_rejects_too_small_dimensions():
    tiny = _make_image_bytes(50, 50)
    with pytest.raises(InvalidImageError):
        validate_and_normalize(tiny, "image/jpeg")


def test_resizes_when_max_dimension_exceeded():
    big = _make_image_bytes(5000, 3000)
    out_bytes, media_type = validate_and_normalize(big, "image/jpeg")
    out_image = Image.open(io.BytesIO(out_bytes))
    assert max(out_image.size) <= 4096
    assert media_type == "image/jpeg"


def test_passthrough_jpeg():
    img_bytes = _make_image_bytes(200, 200)
    out_bytes, media_type = validate_and_normalize(img_bytes, "image/jpeg")
    assert media_type == "image/jpeg"
    assert len(out_bytes) > 0


def test_passthrough_png_re_encodes_to_jpeg():
    img_bytes = _make_image_bytes(200, 200, fmt="PNG")
    out_bytes, media_type = validate_and_normalize(img_bytes, "image/png")
    out_image = Image.open(io.BytesIO(out_bytes))
    assert media_type == "image/jpeg"  # always re-encoded
    assert out_image.size == (200, 200)


def test_passthrough_webp_re_encodes_to_jpeg():
    img_bytes = _make_image_bytes(200, 200, fmt="WEBP")
    out_bytes, media_type = validate_and_normalize(img_bytes, "image/webp")
    assert media_type == "image/jpeg"
    assert len(out_bytes) > 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_image.py -v`
Expected: ImportError (module doesn't exist).

- [ ] **Step 3: Implement `app/services/image.py`**

```python
import io

from PIL import Image, UnidentifiedImageError

from ..config import get_settings
from ..errors import InvalidImageError, UnsupportedFormatError

SUPPORTED_MEDIA_TYPES = {"image/jpeg", "image/png", "image/webp"}
MIN_DIMENSION = 100
MAX_DIMENSION = 4096


def validate_and_normalize(image_bytes: bytes, media_type: str) -> tuple[bytes, str]:
    if not image_bytes:
        raise InvalidImageError("Image payload is empty.")

    if media_type not in SUPPORTED_MEDIA_TYPES:
        raise UnsupportedFormatError(
            f"Unsupported media type '{media_type}'. Use JPEG, PNG, or WEBP."
        )

    settings = get_settings()
    if len(image_bytes) > settings.max_image_bytes:
        raise InvalidImageError(
            f"Image exceeds max size of {settings.max_image_bytes} bytes."
        )

    try:
        image = Image.open(io.BytesIO(image_bytes))
        image.load()
    except (UnidentifiedImageError, OSError) as exc:
        raise InvalidImageError(f"Could not decode image: {exc}") from exc

    width, height = image.size
    if width < MIN_DIMENSION or height < MIN_DIMENSION:
        raise InvalidImageError(
            f"Image dimensions too small ({width}x{height}). Minimum {MIN_DIMENSION}x{MIN_DIMENSION}."
        )

    if max(width, height) > MAX_DIMENSION:
        image.thumbnail((MAX_DIMENSION, MAX_DIMENSION))

    if image.mode != "RGB":
        image = image.convert("RGB")

    out = io.BytesIO()
    image.save(out, format="JPEG", quality=90)
    return out.getvalue(), "image/jpeg"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_image.py -v`
Expected: 9 passed.

- [ ] **Step 5: Commit**

```bash
git add app/services/image.py tests/test_image.py
git commit -m "feat(image): add validation + normalization with size/format/dimension rules"
```

---

## Task 6: Vision Service

**Files:**
- Create: `app/services/vision.py`
- Test: `tests/test_vision.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_vision.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_vision.py -v`
Expected: ImportError (module doesn't exist).

- [ ] **Step 3: Implement `app/services/vision.py`**

```python
import base64
import json
import re
from typing import Any

from openai import OpenAI, OpenAIError, RateLimitError
from pydantic import ValidationError

from ..config import Settings, get_settings
from ..errors import LLMError, NoFoodDetectedError, RateLimitedError
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
            raise RateLimitedError(str(exc)) from exc
        except OpenAIError as exc:
            raise LLMError(f"OpenAI call failed: {exc}") from exc

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
        client=OpenAI(api_key=settings.openai_api_key),
        model=settings.openai_model,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_vision.py -v`
Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add app/services/vision.py tests/test_vision.py
git commit -m "feat(vision): add OpenAIVisionClient with prompt + JSON parsing + error mapping"
```

---

## Task 7: FastAPI App + Error Handlers + Health Check

**Files:**
- Create: `app/main.py`
- Modify: `app/errors.py` (add `register_handlers` function)
- Test: `tests/conftest.py`, `tests/test_app.py`

- [ ] **Step 1: Append handler registration to `app/errors.py`**

Add to the END of `app/errors.py`:

```python
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .schemas.nutrition import ErrorResponse


def register_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.http_status,
            content=ErrorResponse(error=exc.message, error_code=exc.error_code).model_dump(),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=400,
            content=ErrorResponse(
                error="Request payload is invalid or malformed.",
                error_code="INVALID_IMAGE",
            ).model_dump(),
        )
```

- [ ] **Step 2: Create `app/main.py`**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .errors import register_handlers
from .routes import analyze


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="VietCalorie API",
        description="Estimate nutrition from food images using GPT-4o Vision.",
        version="1.0.0",
    )

    # CORS open in dev. For production, set Settings.cors_origins to your allowlist.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_handlers(app)
    app.include_router(analyze.router)

    @app.get("/healthz", tags=["meta"])
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
```

NOTE: this import will fail until Task 8 creates `app/routes/analyze.py`. To unblock testing in this task, also create a minimal stub now:

Create `app/routes/analyze.py` as a minimal stub (will be replaced in Task 8):

```python
from fastapi import APIRouter

router = APIRouter(prefix="/api/v1", tags=["analyze"])
```

- [ ] **Step 3: Create `tests/conftest.py`**

```python
import os

# Set BEFORE importing app modules so config loads cleanly
os.environ.setdefault("OPENAI_API_KEY", "test-key-not-real")

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.services.vision import OpenAIVisionClient, get_vision_client


@pytest.fixture
def mock_vision() -> MagicMock:
    return MagicMock(spec=OpenAIVisionClient)


@pytest.fixture
def app(mock_vision: MagicMock):
    application = create_app()
    application.dependency_overrides[get_vision_client] = lambda: mock_vision
    yield application
    application.dependency_overrides.clear()


@pytest.fixture
def client(app) -> TestClient:
    return TestClient(app)
```

- [ ] **Step 4: Create `tests/test_app.py`**

```python
from app.errors import InvalidImageError, RateLimitedError


def test_healthz(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_app_error_handler_shape(client, mock_vision):
    # We can't call the route yet (Task 8) but we can verify the handler exists
    # by checking the OpenAPI shows /healthz only this task; the real exercise
    # of error handlers happens in Task 8 tests. This test just confirms the
    # app boots and serves a route.
    response = client.get("/openapi.json")
    assert response.status_code == 200
    assert "/healthz" in response.json()["paths"]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_app.py -v`
Expected: 2 passed.

- [ ] **Step 6: Commit**

```bash
git add app/errors.py app/main.py app/routes/analyze.py tests/conftest.py tests/test_app.py
git commit -m "feat(app): add FastAPI factory, CORS, error handlers, health check"
```

---

## Task 8: Analyze Route (multipart + base64)

**Files:**
- Modify: `app/routes/analyze.py` (replace stub from Task 7 with full implementation)
- Test: `tests/test_analyze.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_analyze.py`:

```python
import base64
import io
from unittest.mock import MagicMock

from PIL import Image

from app.errors import LLMError, NoFoodDetectedError, RateLimitedError
from app.schemas.nutrition import AnalyzeResponse, NutritionData


HAPPY_RESPONSE = AnalyzeResponse(
    dish_name="Phở bò",
    confidence="high",
    nutrition=NutritionData(calories_kcal=480, protein_g=28, carbs_g=62, fat_g=10),
    notes="Standard bowl",
)


def _jpeg_bytes(width: int = 200, height: int = 200) -> bytes:
    image = Image.new("RGB", (width, height), color=(200, 100, 50))
    out = io.BytesIO()
    image.save(out, format="JPEG")
    return out.getvalue()


def test_multipart_happy_path(client, mock_vision: MagicMock):
    mock_vision.analyze_food.return_value = HAPPY_RESPONSE
    response = client.post(
        "/api/v1/analyze",
        files={"image": ("pho.jpg", _jpeg_bytes(), "image/jpeg")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["dish_name"] == "Phở bò"
    assert body["nutrition"]["calories_kcal"] == 480
    assert body["confidence"] == "high"
    assert mock_vision.analyze_food.called


def test_base64_happy_path(client, mock_vision: MagicMock):
    mock_vision.analyze_food.return_value = HAPPY_RESPONSE
    img_b64 = base64.b64encode(_jpeg_bytes()).decode("ascii")
    response = client.post(
        "/api/v1/analyze",
        json={"image_base64": img_b64, "media_type": "image/jpeg"},
    )
    assert response.status_code == 200
    assert response.json()["dish_name"] == "Phở bò"


def test_multipart_missing_image(client):
    response = client.post("/api/v1/analyze", files={})
    assert response.status_code == 400
    body = response.json()
    assert body["success"] is False
    assert body["error_code"] == "INVALID_IMAGE"


def test_multipart_unsupported_format(client):
    # GIF bytes are rejected by the media-type check before Pillow sees them
    response = client.post(
        "/api/v1/analyze",
        files={"image": ("anim.gif", b"GIF89a" + b"\x00" * 200, "image/gif")},
    )
    assert response.status_code == 422
    assert response.json()["error_code"] == "UNSUPPORTED_FORMAT"


def test_base64_invalid_encoding(client):
    response = client.post(
        "/api/v1/analyze",
        json={"image_base64": "not valid base64!!!", "media_type": "image/jpeg"},
    )
    assert response.status_code == 400
    assert response.json()["error_code"] == "INVALID_IMAGE"


def test_base64_missing_field(client):
    response = client.post(
        "/api/v1/analyze",
        json={"media_type": "image/jpeg"},  # no image_base64
    )
    assert response.status_code == 400
    assert response.json()["error_code"] == "INVALID_IMAGE"


def test_no_food_detected(client, mock_vision: MagicMock):
    mock_vision.analyze_food.side_effect = NoFoodDetectedError()
    response = client.post(
        "/api/v1/analyze",
        files={"image": ("blank.jpg", _jpeg_bytes(), "image/jpeg")},
    )
    assert response.status_code == 400
    assert response.json()["error_code"] == "NO_FOOD_DETECTED"


def test_rate_limited(client, mock_vision: MagicMock):
    mock_vision.analyze_food.side_effect = RateLimitedError()
    response = client.post(
        "/api/v1/analyze",
        files={"image": ("x.jpg", _jpeg_bytes(), "image/jpeg")},
    )
    assert response.status_code == 429
    assert response.json()["error_code"] == "RATE_LIMITED"


def test_llm_error(client, mock_vision: MagicMock):
    mock_vision.analyze_food.side_effect = LLMError()
    response = client.post(
        "/api/v1/analyze",
        files={"image": ("x.jpg", _jpeg_bytes(), "image/jpeg")},
    )
    assert response.status_code == 500
    assert response.json()["error_code"] == "LLM_ERROR"


def test_unsupported_content_type(client):
    response = client.post(
        "/api/v1/analyze",
        content=b"raw bytes",
        headers={"Content-Type": "application/octet-stream"},
    )
    assert response.status_code == 422
    assert response.json()["error_code"] == "UNSUPPORTED_FORMAT"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_analyze.py -v`
Expected: most tests fail with 404 or 405 (route is currently a stub).

- [ ] **Step 3: Replace `app/routes/analyze.py` with the full implementation**

Replace the contents of `app/routes/analyze.py` (overwrite the stub from Task 7):

```python
import base64
import binascii
from typing import Annotated

from fastapi import APIRouter, Depends, File, Request, UploadFile

from ..errors import InvalidImageError, UnsupportedFormatError
from ..schemas.nutrition import AnalyzeRequestBase64, AnalyzeResponse
from ..services.image import validate_and_normalize
from ..services.vision import OpenAIVisionClient, get_vision_client

router = APIRouter(prefix="/api/v1", tags=["analyze"])


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(
    request: Request,
    vision: Annotated[OpenAIVisionClient, Depends(get_vision_client)],
    image: UploadFile | None = File(default=None),
) -> AnalyzeResponse:
    content_type = (request.headers.get("content-type") or "").split(";")[0].strip().lower()

    if content_type.startswith("multipart/"):
        if image is None:
            raise InvalidImageError("Missing 'image' field in multipart request.")
        image_bytes = await image.read()
        media_type = image.content_type or ""
    elif content_type == "application/json":
        body = await request.json()
        if not isinstance(body, dict):
            raise InvalidImageError("Request body must be a JSON object.")
        try:
            payload = AnalyzeRequestBase64(**body)
        except Exception as exc:
            raise InvalidImageError(f"Invalid JSON body: {exc}") from exc
        try:
            image_bytes = base64.b64decode(payload.image_base64, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise InvalidImageError(f"image_base64 is not valid base64: {exc}") from exc
        media_type = payload.media_type
    else:
        raise UnsupportedFormatError(
            f"Unsupported Content-Type '{content_type}'. Use multipart/form-data or application/json."
        )

    normalized_bytes, normalized_media_type = validate_and_normalize(image_bytes, media_type)
    return vision.analyze_food(normalized_bytes, normalized_media_type)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_analyze.py -v`
Expected: 10 passed.

- [ ] **Step 5: Run the full test suite**

Run: `pytest -v`
Expected: all tests pass (schemas + errors + image + vision + app + analyze). Live tests are not yet present.

- [ ] **Step 6: Commit**

```bash
git add app/routes/analyze.py tests/test_analyze.py
git commit -m "feat(routes): implement POST /api/v1/analyze with multipart and base64 inputs"
```

---

## Task 9: Live Test (opt-in)

**Files:**
- Create: `tests/test_live.py`

- [ ] **Step 1: Create `tests/test_live.py`**

```python
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from openai import OpenAI

from app.main import create_app
from app.services.vision import OpenAIVisionClient, get_vision_client


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "pho.jpg"

pytestmark = pytest.mark.live


@pytest.fixture
def live_client():
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key or api_key.startswith("test"):
        pytest.skip("OPENAI_API_KEY not set or is the test placeholder")
    if not FIXTURE_PATH.exists():
        pytest.skip(f"Fixture image not found at {FIXTURE_PATH}")

    app = create_app()
    real_client = OpenAIVisionClient(
        client=OpenAI(api_key=api_key),
        model=os.environ.get("OPENAI_MODEL", "gpt-4o"),
    )
    app.dependency_overrides[get_vision_client] = lambda: real_client
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_live_analyze_real_image(live_client):
    with FIXTURE_PATH.open("rb") as f:
        response = live_client.post(
            "/api/v1/analyze",
            files={"image": ("pho.jpg", f.read(), "image/jpeg")},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert isinstance(body["dish_name"], str) and body["dish_name"]
    assert body["nutrition"]["calories_kcal"] > 0
    assert body["confidence"] in {"high", "medium", "low"}
```

- [ ] **Step 2: Verify live test is skipped by default**

Run: `pytest -v`
Expected: all previous tests still pass; `test_live_analyze_real_image` is **NOT** collected (because of `addopts = "-m 'not live'"`).

- [ ] **Step 3: Verify live test skips cleanly when explicitly requested without setup**

Run: `pytest -m live -v`
Expected: 1 skipped (with reason "OPENAI_API_KEY not set or is the test placeholder"). No errors.

- [ ] **Step 4: Commit**

```bash
git add tests/test_live.py
git commit -m "test(live): add opt-in real GPT-4o smoke test"
```

---

## Task 10: README

**Files:**
- Create: `README.md`

- [ ] **Step 1: Create `README.md`**

````markdown
# VietCalorie API

Local-first FastAPI backend that estimates nutrition (calories, carbs, fat, protein) from a food image using GPT-4o Vision. Optimized for Vietnamese cuisine, supports general food.

- **Spec:** `docs/superpowers/specs/2026-04-25-vietcalorie-api-design.md`
- **Endpoint:** `POST /api/v1/analyze`
- **Auth:** none in v1

## Requirements

- Python 3.12
- An OpenAI API key with access to `gpt-4o`

## Setup

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# edit .env and set OPENAI_API_KEY=sk-...
```

## Run

```bash
uvicorn app.main:app --reload
# OpenAPI / Swagger docs: http://localhost:8000/docs
# Health check:           http://localhost:8000/healthz
```

## Example requests

Multipart upload:
```bash
curl -X POST http://localhost:8000/api/v1/analyze \
  -F "image=@/path/to/pho.jpg"
```

Base64 JSON:
```bash
curl -X POST http://localhost:8000/api/v1/analyze \
  -H "Content-Type: application/json" \
  -d "{\"image_base64\":\"$(base64 -i /path/to/pho.jpg)\",\"media_type\":\"image/jpeg\"}"
```

Successful response:
```json
{
  "success": true,
  "dish_name": "Phở bò",
  "confidence": "high",
  "nutrition": {
    "calories_kcal": 480,
    "protein_g": 28,
    "carbs_g": 62,
    "fat_g": 10
  },
  "notes": "Estimated for a standard restaurant serving (~500ml bowl)"
}
```

Error response:
```json
{
  "success": false,
  "error": "Could not detect food in the provided image.",
  "error_code": "NO_FOOD_DETECTED"
}
```

| HTTP | error_code | When |
|---|---|---|
| 400 | `INVALID_IMAGE` | Decode fails, file > 10 MB, dimensions < 100×100, malformed payload |
| 422 | `UNSUPPORTED_FORMAT` | MIME type not JPEG/PNG/WEBP |
| 400 | `NO_FOOD_DETECTED` | GPT-4o couldn't identify food |
| 429 | `RATE_LIMITED` | OpenAI rate limit hit |
| 500 | `LLM_ERROR` | OpenAI failure or unparseable response |

## Tests

```bash
pytest                  # mocked tests (default, fast, no API calls)
pytest -m live          # real GPT-4o smoke test (opt-in)
```

The live test additionally requires:
- `OPENAI_API_KEY` set in your environment (must NOT start with `test`)
- An image at `tests/fixtures/pho.jpg` — supply any small JPEG of a real dish

If either is missing, the live test skips cleanly with a reason.

## Project layout

```
app/
  main.py             FastAPI factory, CORS, exception handlers, health check
  config.py           Settings loaded from .env
  errors.py           AppError hierarchy + handler registration
  routes/analyze.py   POST /api/v1/analyze
  services/image.py   Image validation + normalization
  services/vision.py  OpenAI GPT-4o Vision client
  schemas/nutrition.py Request and response Pydantic models
tests/                Mocked unit tests + opt-in live test
docs/superpowers/     Spec and implementation plan
```

## v2 (future)

Auth, image storage, meal history, external nutrition DB lookup, ingredient-level breakdown, deployment artifacts (Dockerfile, Render/Railway). See spec §12.
````

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add README with setup, run, test, and API examples"
```

---

## Final Verification

- [ ] **Step 1: Run the full default test suite**

Run: `pytest -v`
Expected: all tests in `tests/test_schemas.py`, `tests/test_errors.py`, `tests/test_image.py`, `tests/test_vision.py`, `tests/test_app.py`, `tests/test_analyze.py` pass. Total ~42 tests. Live test is not collected.

- [ ] **Step 2: Boot the server and confirm OpenAPI docs**

Run in one terminal:
```bash
OPENAI_API_KEY=test-key uvicorn app.main:app --port 8000
```
In another terminal:
```bash
curl -s http://localhost:8000/healthz
curl -s http://localhost:8000/openapi.json | python -m json.tool | grep -A1 '"/api/v1/analyze"'
```
Expected: `{"status":"ok"}` and the OpenAPI shows `/api/v1/analyze` as a POST. Then Ctrl+C the uvicorn process.

- [ ] **Step 3: Run ruff to confirm clean lint**

Run: `ruff check app tests`
Expected: no issues. If there are minor style fixes, run `ruff check --fix app tests` and commit any changes with `style: ruff fixes`.

- [ ] **Step 4: Confirm git log is clean**

Run: `git log --oneline`
Expected: a tidy series of commits, one per task plus the original spec commit. No WIP commits, no merge artifacts.

---

## Spec Coverage Check

| Spec section | Implemented in |
|---|---|
| §3 Tech stack | Task 1 (`requirements.txt`, `pyproject.toml`) |
| §4 Project structure | Tasks 1, 2, 3, 4, 5, 6, 7, 8 |
| §5.1 Endpoint | Task 8 |
| §5.2 Success response shape | Task 3 (`AnalyzeResponse`) + Task 8 |
| §5.3 Error response shape | Task 3 (`ErrorResponse`) + Task 7 |
| §5.4 Error code → HTTP mapping | Task 4 (classes) + Task 7 (handler) + Task 8 (route paths) |
| §6.1 Image service | Task 5 |
| §6.2 Vision service + DI | Task 6 |
| §6.3 Analyze route | Task 8 |
| §6.4 Error classes + handlers (incl. RequestValidationError) | Task 4 + Task 7 |
| §6.5 Schemas | Task 3 |
| §6.6 Config | Task 2 |
| §6.7 Main app + CORS + healthz | Task 7 |
| §8 Prompt design | Task 6 (`SYSTEM_PROMPT`, `USER_PROMPT`) |
| §9.1 Default test suite | Tasks 3, 4, 5, 6, 7, 8 |
| §9.2 Live suite | Task 9 |
| §10 Local run docs | Task 10 |
| §13 Acceptance criteria | Final Verification steps |
