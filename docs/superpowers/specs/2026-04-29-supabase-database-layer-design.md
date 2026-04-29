# Supabase database layer + Auth design

**Date:** 2026-04-29
**Scope:** Add a persistent data layer to `vietcalorie-api` backed by Supabase Postgres, plus authentication using Supabase Auth (Google OAuth on mobile). Establish migrations, an async ORM, and a repository pattern. Ship a working `User` model and one protected endpoint (`/me`) end-to-end.
**Audience:** Two Claude Code sessions — this API repo (`~/Documents/vietcalorie-api`) and the mobile app repo (`~/Documents/vietcalorie`). Each implements its own half of the contract described here.

---

## 1. Goals

- Persist user profile data in Supabase Postgres.
- Authenticate API requests using Supabase-issued JWTs (Google OAuth).
- Establish reusable infrastructure (DB session, Base model, repositories, FastAPI dependencies, Alembic migrations) so future models (meals, foods, etc.) are quick to add.
- Prove the stack with a single protected resource: `GET /me`, `PATCH /me`.

## 2. Non-goals

- No `/sign_up`, `/sign_in`, `/auth/refresh`, or `/auth/google` endpoints — Supabase Auth owns all of that.
- No nutrition/meal tables yet (added later in their own spec).
- No password handling, no JWT minting on the API side.
- No Postgres triggers (profile creation handled in app code via upsert-on-first-call).

## 3. Architecture

```
┌─────────────────┐       ┌──────────────┐       ┌──────────────────┐
│ Mobile app      │──────▶│ Supabase     │       │ FastAPI          │
│ (vietcalorie)   │  1    │ Auth         │       │ (this repo)      │
│                 │◀──────│ (Google      │       │                  │
│ supabase_flutter│  2    │  OAuth)      │       │                  │
└────────┬────────┘       └──────┬───────┘       └────────┬─────────┘
         │                       │                        │
         │  3. Bearer <Supabase JWT>                       │
         └─────────────────────────────────────────────────▶
                                                          │
                                       4. verify JWT      │
                                          (HS256 w/       │
                                          SUPABASE_JWT_   │
                                          SECRET)         │
                                                          │
                                       5. read sub/email  │
                                          from claims     │
                                                          │
                                       6. find/upsert     │
                                          public.users    │
                                                          ▼
                                                  ┌──────────────┐
                                                  │ Supabase     │
                                                  │ Postgres     │
                                                  │  auth.users  │
                                                  │  public.users│
                                                  └──────────────┘
```

### Request flow

1. Mobile app calls `supabase.auth.signInWithOAuth(provider: google)`. Supabase Auth runs the OAuth dance, creates a row in `auth.users` if needed, and returns a session (access token + refresh token).
2. SDK stores tokens in secure storage and auto-refreshes the access token in background.
3. Mobile attaches `Authorization: Bearer <access_token>` to every API request.
4. FastAPI dependency `get_current_user` decodes the JWT (HS256, key = `SUPABASE_JWT_SECRET`, audience = `authenticated`).
5. Reads `sub` (Supabase user UUID) and `email` from claims.
6. Looks up `public.users` by `id`. If no row, upserts one using JWT claims (`id`, `email`) and Google profile fields (`name`, `avatar_url`) from `user_metadata` claim.

## 4. Data model

### `auth.users` (Supabase-managed — do not modify)

Already created and managed by Supabase. Contains `id uuid`, `email text`, `raw_user_meta_data jsonb`, `created_at timestamptz`, etc. Google profile data lands in `raw_user_meta_data` (`name`, `picture`).

### `public.users` (this app owns)

```sql
CREATE TABLE public.users (
    id            uuid PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email         text NOT NULL,
    display_name  text,
    avatar_url    text,
    created_at    timestamptz NOT NULL DEFAULT now(),
    updated_at    timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX users_email_idx ON public.users(email);
```

Field rationale:
- `id` — same UUID as `auth.users.id`. JWT `sub` is the lookup key. `ON DELETE CASCADE` keeps the profile in sync if the auth row is removed.
- `email` — denormalized for cheap reads. Updated when the user's email in `auth.users` changes.
- `display_name`, `avatar_url` — populated from Google profile metadata on first sign-in. Editable via `PATCH /me`.
- `created_at` / `updated_at` — standard audit columns.

**Profile creation policy:** Lazy upsert by `get_current_user`. The first time an authenticated mobile request hits the API after sign-up, the profile row is created. No trigger required.

## 5. Code layout

```
app/
  config.py            # extended: db urls, jwt secret/audience
  errors.py            # extended: UnauthorizedError, DatabaseError
  main.py              # extended: include `me` router
  deps.py              # NEW: get_db_session, get_current_user
  db/
    __init__.py
    base.py            # SQLAlchemy DeclarativeBase
    session.py         # async engine, async_session_factory
  models/
    __init__.py
    user.py            # User SQLAlchemy model
  repositories/
    __init__.py
    user.py            # UserRepository
  schemas/
    user.py            # UserRead, UserUpdate
  services/
    auth.py            # verify_supabase_jwt
    image.py           # (existing)
    vision.py          # (existing)
  routes/
    me.py              # GET /me, PATCH /me
    analyze.py         # (existing)

alembic/
  env.py
  script.py.mako
  versions/
    0001_create_users.py
alembic.ini

tests/
  test_auth_dep.py
  test_me_routes.py
  test_user_repository.py
```

### Layering rule

```
routes ──▶ services + repositories
services ──▶ (no app deps; pure logic)
repositories ──▶ models + session
models ──▶ db.base
```

Routes never call `session.execute` directly. All SQL lives in repositories.

### Sample wiring (informative, not normative)

```python
# app/deps.py
async def get_db_session() -> AsyncIterator[AsyncSession]:
    async with async_session_factory() as session:
        yield session

async def get_current_user(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> User:
    token = _extract_bearer(request.headers.get("authorization"))
    claims = verify_supabase_jwt(token)
    repo = UserRepository(session)
    user = await repo.upsert_from_jwt(claims)
    await session.commit()
    return user
```

## 6. Configuration

### `Settings` additions (`app/config.py`)

```python
class Settings(BaseSettings):
    # existing
    openai_api_key: str
    openai_model: str = "gpt-4o"
    max_image_bytes: int = 10 * 1024 * 1024
    cors_origins: list[str] = ["*"]

    # new
    database_url: str            # asyncpg URL via Supabase pooler (port 6543)
    database_url_direct: str     # asyncpg URL via direct Supabase host (port 5432) — Alembic only
    supabase_jwt_secret: str
    supabase_jwt_audience: str = "authenticated"
```

### `.env` additions

```
DATABASE_URL=postgresql+asyncpg://postgres.<ref>:<pwd>@aws-0-<region>.pooler.supabase.com:6543/postgres
DATABASE_URL_DIRECT=postgresql+asyncpg://postgres:<pwd>@db.<ref>.supabase.co:5432/postgres
SUPABASE_JWT_SECRET=<Supabase dashboard → Settings → API → JWT secret>
SUPABASE_JWT_AUDIENCE=authenticated
```

### asyncpg + PgBouncer (transaction mode)

When connecting through the pooler, the async engine must disable prepared-statement caching:

```python
engine = create_async_engine(
    settings.database_url,
    connect_args={
        "statement_cache_size": 0,
        "prepared_statement_cache_size": 0,
    },
    pool_pre_ping=True,
)
```

The direct URL (Alembic) does not need these flags.

## 7. Migrations (Alembic)

- `alembic init alembic`
- `alembic/env.py` imports `Base.metadata` from `app.db.base` and uses `Settings.database_url_direct` (Alembic uses sync semantics; convert URL prefix from `postgresql+asyncpg://` to `postgresql://` at runtime, or use Alembic's async support via `run_async`).
- All models must be imported in `alembic/env.py` (or via `app/models/__init__.py`) so autogenerate sees them.
- `0001_create_users.py` autogenerated, reviewed, committed.

Commands:
```
alembic revision --autogenerate -m "create users"
alembic upgrade head
```

## 8. Error handling

### New error classes (extend `app/errors.py`)

```python
class UnauthorizedError(AppError):
    error_code = "UNAUTHORIZED"
    message = "Missing or invalid Authorization token."
    http_status = 401

class DatabaseError(AppError):
    error_code = "DATABASE_ERROR"
    message = "Database operation failed."
    http_status = 500
```

### JWT verification mapping

`verify_supabase_jwt` raises `UnauthorizedError` with a specific message in each case (the `error_code` stays `UNAUTHORIZED`):
- Missing `Authorization` header → `"Missing Authorization header."`
- Header not `Bearer <token>` → `"Malformed Authorization header."`
- Expired → `"Token has expired."`
- Invalid signature → `"Invalid token signature."`
- Audience mismatch → `"Token audience mismatch."`
- Other decode errors → `"Invalid token."`

### Repository errors

`UserRepository` wraps `SQLAlchemyError` and re-raises as `DatabaseError` so callers see consistent error shape.

## 9. API endpoints (this milestone)

Both endpoints require `Authorization: Bearer <Supabase JWT>`.

### `GET /me`

Returns the current user's profile.

**Response 200:**
```json
{
  "id": "uuid",
  "email": "user@example.com",
  "display_name": "Hieu",
  "avatar_url": "https://lh3.googleusercontent.com/...",
  "created_at": "2026-04-29T10:00:00Z"
}
```

**Errors:** 401 `UNAUTHORIZED`, 500 `DATABASE_ERROR`.

### `PATCH /me`

Update editable profile fields.

**Request body:**
```json
{
  "display_name": "Hieu Vo",
  "avatar_url": "https://..."
}
```

Both fields optional. Unset fields are not modified.

**Response 200:** same shape as `GET /me`.

**Errors:** 400 `VALIDATION_ERROR`, 401 `UNAUTHORIZED`, 500 `DATABASE_ERROR`.

## 10. Testing strategy

- **`services/auth.py` (unit):** mint local JWTs with `pyjwt` using a test secret; assert verify accepts valid tokens and rejects expired / wrong-audience / wrong-signature tokens.
- **`repositories/user.py` (integration):** local Postgres via Docker (`TEST_DATABASE_URL`). Each test runs in a transaction that rolls back. Cover `get_by_id`, `upsert_from_jwt` (insert path + idempotent path), `update_profile`.
- **`routes/me.py` (route):** FastAPI `TestClient`. Override `get_current_user` to inject a fixture `User` — avoids minting real JWTs in route tests.

## 11. Mobile-side contract (for the `vietcalorie` session)

This section is normative for the mobile app — it spells out exactly what the mobile session must implement so the API contract is satisfied.

### Sign-in (Flutter example)

```dart
final supabase = Supabase.instance.client;
await supabase.auth.signInWithOAuth(OAuthProvider.google);
final session = supabase.auth.currentSession;
final accessToken = session?.accessToken;  // attach this to API calls
```

### Sending requests to the API

```
GET /api/v1/me HTTP/1.1
Host: <api host>
Authorization: Bearer <session.accessToken>
```

All API endpoints live under `/api/v1`. Earlier section 9 of this document uses the prefix; the example here is updated to match.

The Supabase SDK automatically refreshes `session.accessToken` before expiry. The mobile app should always read the current token off `supabase.auth.currentSession` per request, not cache it manually.

### Sign-out

`supabase.auth.signOut()`. The API does not need a sign-out endpoint — discarding the JWT on the client is sufficient.

### What the mobile app must NOT do

- Do not call any `/sign_up`, `/sign_in`, `/auth/google`, or `/auth/refresh` endpoint on this API. Those don't exist by design.
- Do not include the Supabase `apikey` header to the API. The API only needs the user's JWT.

## 12. Open questions / future work

- **Email update flow:** when a Supabase user changes their email in `auth.users`, the denormalized `public.users.email` won't auto-update. Either (a) a background sync job, (b) refresh `email` on every `get_current_user` call (simplest, small extra write), or (c) a Postgres trigger. Decide later — first cut just sets `email` on insert.
- **RLS (Row Level Security):** Supabase recommends RLS on all `public.*` tables. Since this API uses the service role / direct Postgres connection (not via PostgREST), RLS isn't enforced for our queries. Document this clearly when nutrition tables are added.
- **Test database:** decide between `pytest-postgresql` and a Docker-Compose Postgres for CI. Out of scope for this spec.
