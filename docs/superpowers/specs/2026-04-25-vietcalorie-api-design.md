# VietCalorie API — Design Spec

**Date:** 2026-04-25
**Status:** Approved (brainstorming complete; ready for implementation plan)
**Source PRD:** `VietCalorie_PRD.docx` (v1.0, April 2026, DRAFT)

## 1. Purpose

A backend REST API that accepts a food image and returns an estimated nutritional breakdown (calories, carbs, fat, protein) using GPT-4o Vision. Optimized for Vietnamese cuisine but supports general food. Stateless, no auth, no DB — v1 ships fast to validate the core experience.

## 2. Scope

### In scope (v1)
- Single endpoint: `POST /api/v1/analyze` accepting multipart upload OR base64 JSON
- Image validation (format, size, resolution)
- GPT-4o Vision call with a prompt tuned for Vietnamese food
- Structured JSON response with the five PRD fields
- All five PRD error codes (`INVALID_IMAGE`, `UNSUPPORTED_FORMAT`, `NO_FOOD_DETECTED`, `LLM_ERROR`, `RATE_LIMITED`)
- Mocked unit tests + opt-in live test marker (`pytest -m live`)
- Local-first runnable with `uvicorn` and a README

### Out of scope (v1)
- Authentication / API keys for clients (PRD v2)
- Image storage, meal history, user accounts (PRD v2)
- External nutrition database lookup (PRD v2)
- Deployment artifacts — no Dockerfile, no Render/Railway configs, no CI (deferred per user; will set up after local validation)

## 3. Tech Stack

| Layer | Choice | Notes |
|---|---|---|
| Language | Python 3.13 | |
| API framework | FastAPI | Async, auto OpenAPI docs at `/docs` |
| ASGI server | Uvicorn | Run with `--reload` in dev |
| AI vision | OpenAI Python SDK → GPT-4o (`gpt-4o`) | |
| Image handling | Pillow + python-multipart | |
| Config | pydantic-settings (loads `.env`) | |
| Validation | Pydantic v2 | |
| Tests | pytest + httpx TestClient | Custom `live` marker for real-API tests |
| Lint/format | ruff | Configured in `pyproject.toml` |

## 4. Project Structure

```
vietcalorie-api/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app, CORS, exception handlers, router include
│   ├── config.py            # Settings(BaseSettings) — OPENAI_API_KEY, model name, limits
│   ├── errors.py            # AppError hierarchy + handler mapping → ErrorResponse
│   ├── routes/
│   │   ├── __init__.py
│   │   └── analyze.py       # POST /api/v1/analyze
│   ├── services/
│   │   ├── __init__.py
│   │   ├── image.py         # validate_and_normalize(bytes, media_type) -> bytes
│   │   └── vision.py        # OpenAIVisionClient + analyze_food()
│   └── schemas/
│       ├── __init__.py
│       └── nutrition.py     # AnalyzeResponse, NutritionData, ErrorResponse
├── tests/
│   ├── __init__.py
│   ├── conftest.py          # client, mock_vision, sample image fixtures
│   ├── fixtures/
│   │   └── pho.jpg          # small sample image for live test
│   ├── test_image.py        # validation rules
│   ├── test_analyze.py      # endpoint w/ mocked vision (happy + each error)
│   └── test_live.py         # @pytest.mark.live — real OpenAI call
├── docs/
│   └── superpowers/specs/2026-04-25-vietcalorie-api-design.md
├── .env.example
├── .gitignore
├── pyproject.toml           # ruff config, pytest markers, addopts="-m 'not live'"
├── requirements.txt
└── README.md
```

## 5. API Specification

### 5.1 Endpoint
- `POST /api/v1/analyze`
- Accepts EITHER `multipart/form-data` with field `image` (file) OR `application/json` with `{ "image_base64": "...", "media_type": "image/jpeg" }`
- No auth in v1

### 5.2 Success Response (HTTP 200)
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

### 5.3 Error Response (HTTP 4xx/5xx)
```json
{
  "success": false,
  "error": "Could not detect food in the provided image.",
  "error_code": "NO_FOOD_DETECTED"
}
```

### 5.4 Error Code → HTTP Mapping

| HTTP | error_code | Trigger |
|---|---|---|
| 400 | `INVALID_IMAGE` | Pillow decode fails, file > 10 MB, dimensions < 100×100, or empty/missing image bytes after content-type parsing |
| 400 | `NO_FOOD_DETECTED` | GPT-4o returns `{"error": "NO_FOOD_DETECTED"}` |
| 422 | `UNSUPPORTED_FORMAT` | MIME type not in {JPEG, PNG, WEBP} (e.g., GIF, BMP) |
| 429 | `RATE_LIMITED` | OpenAI SDK raises `RateLimitError` |
| 500 | `LLM_ERROR` | Any other OpenAI failure or unparseable JSON from the model |

## 6. Components

### 6.1 `services/image.py` (pure, no I/O beyond Pillow)
- `validate_and_normalize(image_bytes: bytes, media_type: str) -> tuple[bytes, str]`
  - Reject if `media_type` not in `{image/jpeg, image/png, image/webp}` → `UnsupportedFormatError`
  - Reject if `len(image_bytes) > 10 * 1024 * 1024` → `InvalidImageError`
  - Open with Pillow; reject if open fails or width/height < 100 → `InvalidImageError`
  - If max(width, height) > 4096, resize down preserving aspect ratio
  - Re-encode to JPEG bytes for transport to OpenAI; return `(bytes, "image/jpeg")`

### 6.2 `services/vision.py` (DI-friendly)
- `class OpenAIVisionClient` — wraps the OpenAI SDK client, takes API key + model name from config
- `def analyze_food(self, image_bytes: bytes, media_type: str) -> AnalyzeResponse`
  - Builds messages with system prompt + user prompt (per PRD §5)
  - Sends image as base64 data URL
  - Reads response, strips any markdown fences (`` ```json ... ``` ``), parses JSON
  - If parsed dict has `{"error": "NO_FOOD_DETECTED"}` → raise `NoFoodDetectedError`
  - Otherwise validate against `AnalyzeResponse` Pydantic model and return
  - Catches `openai.RateLimitError` → `RateLimitedError`; any other `openai.OpenAIError` → `LLMError`; `json.JSONDecodeError` / Pydantic `ValidationError` → `LLMError`
- Provided to routes via FastAPI `Depends(get_vision_client)`. Tests override the dependency.

### 6.3 `routes/analyze.py`
- One endpoint with two content-type branches
- Multipart branch: read `UploadFile`, get bytes + content_type
- Base64 branch: parse `AnalyzeRequestBase64` schema, b64-decode
- Calls `image.validate_and_normalize` then `vision.analyze_food` (injected)
- Returns `AnalyzeResponse` directly; FastAPI serializes

### 6.4 `errors.py`
- `class AppError(Exception)` with `error_code: str`, `message: str`, `http_status: int`
- Subclasses: `InvalidImageError`, `UnsupportedFormatError`, `NoFoodDetectedError`, `LLMError`, `RateLimitedError` — each sets the right defaults
- `register_handlers(app)` adds:
  - a handler for `AppError` → `ErrorResponse` JSON with the matching HTTP status
  - a handler for FastAPI's `RequestValidationError` → `ErrorResponse` with `error_code = "INVALID_IMAGE"` and HTTP 400, so malformed multipart/JSON requests share the same response shape as the rest of the API

### 6.5 `schemas/nutrition.py`
- `NutritionData` — calories_kcal: int, protein_g, carbs_g, fat_g: float (≥ 0)
- `AnalyzeResponse` — success: bool = True, dish_name: str, confidence: Literal["high","medium","low"], nutrition: NutritionData, notes: str | None
- `ErrorResponse` — success: bool = False, error: str, error_code: str
- `AnalyzeRequestBase64` — image_base64: str, media_type: str

### 6.6 `config.py`
- `class Settings(BaseSettings)` with: `openai_api_key: str`, `openai_model: str = "gpt-4o"`, `max_image_bytes: int = 10*1024*1024`, `cors_origins: list[str] = ["*"]`
- Loads from `.env`; `model_config = SettingsConfigDict(env_file=".env")`
- Cached `get_settings()` for DI

### 6.7 `main.py`
- Constructs FastAPI app with title/description
- Registers CORS middleware (open `*` in dev — comment notes to lock down for prod)
- Calls `errors.register_handlers(app)`
- Includes `routes.analyze.router`
- Health check: `GET /healthz` returning `{"status": "ok"}`

## 7. Data Flow

```
Client
  │ POST /api/v1/analyze (multipart OR base64 JSON)
  ▼
routes.analyze
  │ extract bytes + media_type
  ▼
services.image.validate_and_normalize  ── on failure → AppError ──┐
  │ returns normalized JPEG bytes                                 │
  ▼                                                               │
services.vision.analyze_food                                      │
  │ build prompt → OpenAI GPT-4o Vision call                      │
  │ parse JSON, validate via Pydantic                             │
  │ on NO_FOOD_DETECTED / OpenAI failure → AppError ──────────────┤
  │ returns AnalyzeResponse                                       │
  ▼                                                               ▼
HTTP 200 + AnalyzeResponse                              errors handler
                                                        → ErrorResponse + status
```

## 8. Prompt Design (per PRD §5)

**System prompt** (verbatim from PRD): instructs the model to act as a Vietnamese/Asian food nutritionist, identify the dish (Vietnamese name when applicable), estimate nutrition for the visible portion, and return ONLY valid JSON — no preamble, no markdown fences.

**User prompt template**: provides the exact JSON schema the model must fill (`dish_name`, `confidence` ∈ {high, medium, low}, `nutrition.{calories_kcal, protein_g, carbs_g, fat_g}`, optional `notes`), plus the fallback `{"error": "NO_FOOD_DETECTED"}` when no food is identifiable.

The image is sent as a base64 `data:` URL alongside the user prompt in the same `user` message (per OpenAI vision messages format).

Even though the system prompt forbids markdown fences, the parser still strips them defensively.

## 9. Testing Strategy

### 9.1 Default suite (`pytest`)
- `test_image.py`
  - rejects oversized payload → `InvalidImageError`
  - rejects unsupported MIME → `UnsupportedFormatError`
  - rejects too-small dimensions
  - resizes down when max dimension > 4096
  - happy-path passthrough on valid JPEG/PNG/WEBP
- `test_analyze.py` (vision dependency overridden with a mock)
  - happy path: mock returns valid `AnalyzeResponse` → 200 with expected body
  - multipart and base64 input both work
  - mock raises each `AppError` subclass → endpoint returns the right HTTP status + `error_code`
  - unparseable JSON from mock → `LLM_ERROR` / 500
  - missing image / empty payload → `INVALID_IMAGE` / 400

### 9.2 Live suite (`pytest -m live`)
- `test_live.py` — single test, marked `@pytest.mark.live`
- Skipped by default via `addopts = "-m 'not live'"` in `pyproject.toml`
- Skips with a clear reason if either:
  - `OPENAI_API_KEY` env var is missing, OR
  - `tests/fixtures/pho.jpg` is not present (the user supplies this image; the README documents the requirement and recommends any small JPEG of a real dish)
- When both are present, it loads the fixture, calls the real endpoint, and asserts:
  - 200 status
  - `dish_name` is a non-empty string
  - `nutrition.calories_kcal > 0`
  - `confidence` ∈ {high, medium, low}
- Costs ~1¢ per run; intended for pre-push smoke checks

## 10. Local Run

```bash
cd vietcalorie-api
cp .env.example .env       # then add OPENAI_API_KEY=sk-...
pip install -r requirements.txt
uvicorn app.main:app --reload
# OpenAPI docs: http://localhost:8000/docs

pytest                     # mocked tests (default)
pytest -m live             # real GPT-4o call (requires OPENAI_API_KEY)
```

## 11. Assumptions & Constraints (from PRD §10)

- Accuracy is intentionally approximate in v1 — GPT-4o estimates, not lab measurements
- Stateless — no data stored between requests
- Vietnamese dish recognition accuracy ~70–90% for common dishes
- Calorie estimates may vary ±15–25%
- OpenAI API costs are pay-per-use; no caching in v1
- `gpt-4o` is the model identifier targeted; if OpenAI deprecates or renames, update `Settings.openai_model`

## 12. Out of Scope / v2 Items (tracked, not built)

Per PRD §9: external nutrition DB (viendinhduong.vn), ingredient-level decomposition, user accounts + meal history, portion-size calibration, confidence-based user prompts, feedback loop for prompt improvement, deployment artifacts (Dockerfile, Render/Railway configs, CI).

## 13. Acceptance Criteria

The v1 build is done when all of the following hold:
1. `pip install -r requirements.txt && uvicorn app.main:app --reload` starts the server cleanly.
2. `/docs` shows the `POST /api/v1/analyze` endpoint with both content-type variants documented.
3. `pytest` runs green with all default (mocked) tests passing.
4. `pytest -m live` (with a real `OPENAI_API_KEY` and the fixture image) returns 200 with a plausible `dish_name` and positive `calories_kcal`.
5. Each of the five PRD error codes is covered by at least one mocked test asserting the correct HTTP status and `error_code`.
6. `README.md` documents local run, env setup, and both test modes.
