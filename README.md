# VietCalorie API

Local-first FastAPI backend that estimates nutrition (calories, carbs, fat, protein) from a food image using GPT-4o Vision. Optimized for Vietnamese cuisine, supports general food.

- **Spec:** `docs/superpowers/specs/2026-04-25-vietcalorie-api-design.md`
- **Endpoint:** `POST /api/v1/analyze`
- **Auth:** none in v1

## Requirements

- Python 3.13
- An OpenAI API key with access to `gpt-4o`

## Setup

```bash
python3.13 -m venv .venv
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
