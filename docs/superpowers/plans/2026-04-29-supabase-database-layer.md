# Supabase Database Layer + Auth Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a persistent data layer to `vietcalorie-api` backed by Supabase Postgres, plus authentication via Supabase Auth (Google OAuth). Ship a `User` model, a repository pattern, Alembic migrations, a Supabase JWT verification dependency, and a working `/me` endpoint to prove the stack end-to-end.

**Architecture:** FastAPI verifies a Supabase-issued JWT (HS256, `SUPABASE_JWT_SECRET`) on every request. A `public.users` profile table sits next to Supabase's managed `auth.users` table, linked 1:1 by UUID. Profile rows are lazily upserted from JWT claims on the user's first authenticated API call. SQLAlchemy 2.x async + asyncpg for ORM, Alembic for migrations, pyjwt for token verification, repository pattern for all SQL access.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy 2.x (async), asyncpg, Alembic, pyjwt, Pydantic v2, pytest, pytest-asyncio, Docker Compose (test DB), Supabase (Postgres + Auth).

**Spec:** See `docs/superpowers/specs/2026-04-29-supabase-database-layer-design.md`.

---

## File Structure

### New files

| Path | Responsibility |
|---|---|
| `app/db/__init__.py` | Package marker |
| `app/db/base.py` | `class Base(DeclarativeBase)` — single declarative base for all models |
| `app/db/session.py` | Async engine + `async_session_factory`, with PgBouncer-safe `connect_args` |
| `app/models/__init__.py` | Imports every model so Alembic and `Base.metadata` see them |
| `app/models/user.py` | `User` SQLAlchemy model for `public.users` |
| `app/repositories/__init__.py` | Package marker |
| `app/repositories/user.py` | `UserRepository` — only place SQL/ORM queries for users live |
| `app/schemas/user.py` | Pydantic `UserRead`, `UserUpdate` |
| `app/services/auth.py` | `verify_supabase_jwt(token) -> SupabaseClaims` |
| `app/deps.py` | `get_db_session`, `get_current_user` FastAPI dependencies |
| `app/routes/me.py` | `GET /me`, `PATCH /me` |
| `alembic.ini` | Alembic config |
| `alembic/env.py` | Async Alembic env; reads `DATABASE_URL_DIRECT` |
| `alembic/script.py.mako` | Default Alembic template |
| `alembic/versions/0001_create_users.py` | First migration — `public.users` table + index |
| `docker-compose.yml` | Local test Postgres on port 5433 |
| `.env.example` | Documented env vars (no secrets) |
| `tests/db_conftest.py` | DB-related pytest fixtures (test engine, session, auth user stub) |
| `tests/test_user_repository.py` | Integration tests for `UserRepository` |
| `tests/test_auth_service.py` | Unit tests for `verify_supabase_jwt` |
| `tests/test_auth_dep.py` | Tests for `get_current_user` dependency |
| `tests/test_me_routes.py` | Route tests for `/me` |

### Modified files

| Path | Change |
|---|---|
| `requirements.txt` | Add `sqlalchemy[asyncio]`, `asyncpg`, `alembic`, `pyjwt`, `pytest-asyncio` |
| `app/config.py` | Add `database_url`, `database_url_direct`, `supabase_jwt_secret`, `supabase_jwt_audience` |
| `app/errors.py` | Add `UnauthorizedError`, `DatabaseError` |
| `app/main.py` | Include `me` router |
| `tests/conftest.py` | Set `SUPABASE_JWT_SECRET` env var so `Settings` loads in tests |

---

## Task 1: Dependencies, settings, and .env.example

**Files:**
- Modify: `requirements.txt`
- Modify: `app/config.py`
- Create: `.env.example`

- [ ] **Step 1: Add new dependencies to `requirements.txt`**

Replace the contents of `requirements.txt` with:

```
fastapi>=0.110.0
uvicorn[standard]>=0.27.0
python-multipart>=0.0.9
pydantic>=2.6.0
pydantic-settings>=2.2.0
Pillow>=10.2.0
openai>=1.30.0
python-dotenv>=1.0.0

# data layer
sqlalchemy[asyncio]>=2.0.30
asyncpg>=0.29.0
alembic>=1.13.0
pyjwt>=2.8.0

# dev
pytest>=8.0.0
pytest-asyncio>=0.23.0
httpx>=0.26.0
ruff>=0.3.0
```

- [ ] **Step 2: Install dependencies**

Run: `pip install -r requirements.txt`
Expected: installs `sqlalchemy`, `asyncpg`, `alembic`, `pyjwt`, `pytest-asyncio` (and existing deps already present).

- [ ] **Step 3: Extend `Settings` in `app/config.py`**

Replace `app/config.py` with:

```python
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    openai_api_key: str
    openai_model: str = "gpt-4o"
    max_image_bytes: int = 10 * 1024 * 1024
    cors_origins: list[str] = ["*"]

    # Database (Supabase Postgres)
    database_url: str  # asyncpg URL via Supabase pooler (port 6543)
    database_url_direct: str  # asyncpg URL via direct host (port 5432) — Alembic only

    # Supabase Auth
    supabase_jwt_secret: str
    supabase_jwt_audience: str = "authenticated"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 4: Create `.env.example`**

Create `.env.example` with:

```
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o

# Supabase Postgres
DATABASE_URL=postgresql+asyncpg://postgres.<ref>:<pwd>@aws-0-<region>.pooler.supabase.com:6543/postgres
DATABASE_URL_DIRECT=postgresql+asyncpg://postgres:<pwd>@db.<ref>.supabase.co:5432/postgres

# Supabase Auth (Dashboard -> Settings -> API -> JWT secret)
SUPABASE_JWT_SECRET=replace-with-supabase-jwt-secret
SUPABASE_JWT_AUDIENCE=authenticated
```

- [ ] **Step 5: Verify config loads**

Run: `python -c "import os; os.environ.update({'OPENAI_API_KEY':'x','DATABASE_URL':'postgresql+asyncpg://x','DATABASE_URL_DIRECT':'postgresql+asyncpg://x','SUPABASE_JWT_SECRET':'x'}); from app.config import get_settings; print(get_settings())"`
Expected: prints a `Settings(...)` line including the new fields.

- [ ] **Step 6: Commit**

```bash
git add requirements.txt app/config.py .env.example
git commit -m "feat(config): add db + supabase auth settings and deps"
```

---

## Task 2: DB infrastructure (Base + async session)

**Files:**
- Create: `app/db/__init__.py`
- Create: `app/db/base.py`
- Create: `app/db/session.py`

- [ ] **Step 1: Create `app/db/__init__.py`**

Empty file:

```python
```

- [ ] **Step 2: Create `app/db/base.py`**

```python
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Shared SQLAlchemy declarative base for all ORM models."""
```

- [ ] **Step 3: Create `app/db/session.py`**

```python
from collections.abc import AsyncIterator
from functools import lru_cache

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from ..config import get_settings


@lru_cache
def get_engine() -> AsyncEngine:
    settings = get_settings()
    return create_async_engine(
        settings.database_url,
        # Required when connecting through Supabase's transaction-mode PgBouncer pooler.
        connect_args={
            "statement_cache_size": 0,
            "prepared_statement_cache_size": 0,
        },
        pool_pre_ping=True,
    )


@lru_cache
def get_session_factory() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(get_engine(), expire_on_commit=False)


async def session_scope() -> AsyncIterator[AsyncSession]:
    """Yield an AsyncSession for use as a FastAPI dependency or in test fixtures."""
    factory = get_session_factory()
    async with factory() as session:
        yield session
```

- [ ] **Step 4: Smoke-import**

Run: `python -c "import os; os.environ.update({'OPENAI_API_KEY':'x','DATABASE_URL':'postgresql+asyncpg://x:y@h/d','DATABASE_URL_DIRECT':'postgresql+asyncpg://x:y@h/d','SUPABASE_JWT_SECRET':'x'}); from app.db.session import get_engine; print(get_engine())"`
Expected: prints `Engine(postgresql+asyncpg://x:***@h/d)` without error.

- [ ] **Step 5: Commit**

```bash
git add app/db
git commit -m "feat(db): add async engine, session factory, declarative base"
```

---

## Task 3: User SQLAlchemy model

**Files:**
- Create: `app/models/__init__.py`
- Create: `app/models/user.py`

- [ ] **Step 1: Create `app/models/user.py`**

```python
from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from ..db.base import Base


class User(Base):
    """Profile row in `public.users`, 1:1 with `auth.users.id` (Supabase-managed)."""

    __tablename__ = "users"
    __table_args__ = (
        Index("users_email_idx", "email"),
        {"schema": "public"},
    )

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("auth.users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    email: Mapped[str] = mapped_column(String, nullable=False)
    display_name: Mapped[str | None] = mapped_column(String, nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
```

- [ ] **Step 2: Create `app/models/__init__.py`**

```python
"""Importing every model here ensures Alembic autogenerate and Base.metadata see them."""

from .user import User

__all__ = ["User"]
```

- [ ] **Step 3: Smoke-import**

Run: `python -c "from app.models import User; print(User.__tablename__, User.__table__.schema)"`
Expected: `users public`

- [ ] **Step 4: Commit**

```bash
git add app/models
git commit -m "feat(models): add User model linked to auth.users"
```

---

## Task 4: Alembic setup + first migration

**Files:**
- Create: `alembic.ini`
- Create: `alembic/env.py`
- Create: `alembic/script.py.mako`
- Create: `alembic/versions/0001_create_users.py`

- [ ] **Step 1: Initialize Alembic with the async template**

Run: `alembic init -t async alembic`
Expected: creates `alembic.ini`, `alembic/env.py`, `alembic/script.py.mako`, `alembic/versions/`.

- [ ] **Step 2: Edit `alembic.ini`**

Find `sqlalchemy.url = ...` near the top and **delete that line entirely** (we'll inject it from `Settings` in `env.py`). Leave everything else as-is.

- [ ] **Step 3: Replace `alembic/env.py`**

Replace the whole file with:

```python
import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import async_engine_from_config
from sqlalchemy.engine import Connection
from sqlalchemy import pool

from app.config import get_settings
from app.db.base import Base
from app import models  # noqa: F401  -- ensures models register with Base.metadata

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Inject the direct (port 5432) URL from Settings — pooler URL doesn't play nice with DDL.
config.set_main_option("sqlalchemy.url", get_settings().database_url_direct)

target_metadata = Base.metadata


def _include_object(object, name, type_, reflected, compare_to):
    """Skip the Supabase-managed `auth` schema during autogenerate."""
    if type_ == "table" and getattr(object, "schema", None) == "auth":
        return False
    return True


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        include_schemas=True,
        include_object=_include_object,
        version_table_schema="public",
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_schemas=True,
        include_object=_include_object,
        version_table_schema="public",
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

- [ ] **Step 4: Create the first migration**

Create `alembic/versions/0001_create_users.py`:

```python
"""create users

Revision ID: 0001
Revises:
Create Date: 2026-04-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("display_name", sa.String(), nullable=True),
        sa.Column("avatar_url", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["id"], ["auth.users.id"], name="users_id_fkey", ondelete="CASCADE"
        ),
        schema="public",
    )
    op.create_index(
        "users_email_idx", "users", ["email"], unique=False, schema="public"
    )


def downgrade() -> None:
    op.drop_index("users_email_idx", table_name="users", schema="public")
    op.drop_table("users", schema="public")
```

- [ ] **Step 5: Verify Alembic config parses**

Run: `alembic check 2>&1 | head -5` (with `.env` populated so `Settings` loads)
Expected: command exits without traceback. (It may print "No new upgrade operations detected" or similar — that's fine.)

If `Settings` complains about missing env vars, populate `.env` from `.env.example` first with placeholder values for `DATABASE_URL_DIRECT`. We'll run the migration for real in Task 5.

- [ ] **Step 6: Commit**

```bash
git add alembic.ini alembic/
git commit -m "feat(alembic): async migrations setup + initial users table"
```

---

## Task 5: Test infrastructure (Supabase test project + savepoint fixtures)

**Files:**
- Create: `tests/db_conftest.py`
- Modify: `pyproject.toml`

> **Strategy change vs. the original plan:** Instead of a Docker Postgres, integration tests run against the real Supabase test project (whose URLs are already in `.env`). Each test runs inside an outer transaction that is **rolled back at the end**, so the schema (created by `alembic upgrade head`) and any unrelated rows are preserved. This works because SQLAlchemy's `AsyncSession(join_transaction_mode="create_savepoint")` makes the test code's `await session.commit()` calls land on a savepoint inside the outer transaction. The migration must already have been applied (it has — see Task 4 verification).

> **Pre-requisite:** `alembic upgrade head` has been run against the test project so `public.users` exists. (Already done.)

- [ ] **Step 1: Configure pytest-asyncio + markers in `pyproject.toml`**

Replace the `[tool.pytest.ini_options]` block in `pyproject.toml` with:

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
markers = [
    "live: tests that hit real OpenAI API (skipped by default; opt in with -m live)",
    "db: integration tests that need the Supabase test project DB",
]
addopts = "-m 'not live'"
testpaths = ["tests"]
```

- [ ] **Step 2: Leave `tests/conftest.py` as-is**

`Settings()` already loads from `.env`, which now has real DB + JWT values. No `os.environ.setdefault` for DB vars is needed. The existing `OPENAI_API_KEY` setdefault stays.

- [ ] **Step 3: Create `tests/db_conftest.py`**

```python
"""DB-related fixtures for tests that hit the Supabase test project.

Each test runs inside an outer transaction that is rolled back at the end,
so committed rows in public.users / auth.users disappear after the test.
The schema is NOT recreated per test — Alembic owns it.
"""

from collections.abc import AsyncIterator
from uuid import UUID, uuid4

import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine

from app.config import get_settings


@pytest_asyncio.fixture(scope="session")
async def test_engine() -> AsyncIterator[AsyncEngine]:
    """Session-wide engine pointed at the direct (port 5432) URL.

    The pooler is in transaction mode and breaks long savepoint-bearing transactions,
    so tests use the direct URL.
    """
    settings = get_settings()
    engine = create_async_engine(settings.database_url_direct)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    """Per-test session bound to an outer transaction; everything rolls back at the end.

    Uses SQLAlchemy's `join_transaction_mode="create_savepoint"`, so any
    `await session.commit()` inside test or app code becomes a SAVEPOINT release
    rather than a real commit — and the outer rollback wipes the lot.
    """
    async with test_engine.connect() as connection:
        outer_tx = await connection.begin()
        session = AsyncSession(
            bind=connection,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )
        try:
            yield session
        finally:
            await session.close()
            await outer_tx.rollback()


@pytest_asyncio.fixture
async def auth_user_id(db_session: AsyncSession) -> UUID:
    """Insert a stub auth.users row inside the test transaction; rolled back automatically.

    auth.users.id is the only NOT NULL column without a default we need to set;
    `is_sso_user` and `is_anonymous` default to false, `email` is nullable.
    """
    user_id = uuid4()
    await db_session.execute(
        text("INSERT INTO auth.users (id, email) VALUES (:id, :email)"),
        {"id": str(user_id), "email": f"{user_id}@example.com"},
    )
    await db_session.flush()
    return user_id
```

- [ ] **Step 4: Verify the fixtures connect**

Create a throwaway test at `tests/test_db_smoke.py`:

```python
import pytest
from sqlalchemy import text

pytest_plugins = ["tests.db_conftest"]
pytestmark = pytest.mark.db


async def test_engine_connects(test_engine):
    async with test_engine.connect() as conn:
        result = await conn.execute(text("SELECT 1"))
        assert result.scalar() == 1


async def test_session_rolls_back(db_session, auth_user_id):
    # Confirm the auth.users stub is visible inside the test transaction.
    found = await db_session.execute(
        text("SELECT id FROM auth.users WHERE id = :id"),
        {"id": str(auth_user_id)},
    )
    assert found.scalar() == auth_user_id
```

Run: `/Users/hieuvo/Documents/vietcalorie-api/.venv/bin/pytest tests/test_db_smoke.py -v`
Expected: 2 PASS.

After it passes, delete `tests/test_db_smoke.py` — it was a smoke test only.

Also confirm that AFTER the test, the `auth_user_id` is gone from the real DB (rollback worked). Run:

```bash
/Users/hieuvo/Documents/vietcalorie-api/.venv/bin/python -c "
import asyncio
from app.config import get_settings
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def main():
    eng = create_async_engine(get_settings().database_url_direct)
    async with eng.connect() as c:
        n = await c.scalar(text('SELECT count(*) FROM auth.users'))
        print(f'auth.users row count: {n}')
        n2 = await c.scalar(text('SELECT count(*) FROM public.users'))
        print(f'public.users row count: {n2}')
    await eng.dispose()

asyncio.run(main())
"
```

Expected: both counts are `0` (or whatever they were before the test ran — definitely no leftover rows from the test).

- [ ] **Step 5: Commit**

```bash
git add tests/db_conftest.py pyproject.toml
git commit -m "test: add savepoint-based db fixtures pointing at supabase test project"
```

---

## Task 6: Auth errors

**Files:**
- Modify: `app/errors.py`
- Create: `tests/test_auth_errors.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_auth_errors.py`:

```python
from app.errors import DatabaseError, UnauthorizedError


def test_unauthorized_error_defaults():
    exc = UnauthorizedError()
    assert exc.error_code == "UNAUTHORIZED"
    assert exc.http_status == 401
    assert "token" in exc.message.lower()


def test_unauthorized_error_custom_message():
    exc = UnauthorizedError("Token has expired.")
    assert exc.message == "Token has expired."
    assert exc.error_code == "UNAUTHORIZED"
    assert exc.http_status == 401


def test_database_error_defaults():
    exc = DatabaseError()
    assert exc.error_code == "DATABASE_ERROR"
    assert exc.http_status == 500
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_auth_errors.py -v`
Expected: FAIL with `ImportError: cannot import name 'UnauthorizedError'`.

- [ ] **Step 3: Add the new error classes to `app/errors.py`**

Add these classes after the existing `InsufficientQuotaError` class (before `def register_handlers(...)`):

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

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_auth_errors.py -v`
Expected: 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add app/errors.py tests/test_auth_errors.py
git commit -m "feat(errors): add UnauthorizedError and DatabaseError"
```

---

## Task 7: Auth service — `verify_supabase_jwt` (TDD)

**Files:**
- Create: `app/services/auth.py`
- Create: `tests/test_auth_service.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_auth_service.py`:

```python
import time
from uuid import UUID, uuid4

import jwt
import pytest

from app.config import get_settings
from app.errors import UnauthorizedError
from app.services.auth import verify_supabase_jwt


def _mint(claims: dict, secret: str | None = None) -> str:
    settings = get_settings()
    return jwt.encode(claims, secret or settings.supabase_jwt_secret, algorithm="HS256")


def _valid_claims() -> dict:
    return {
        "sub": str(uuid4()),
        "email": "user@example.com",
        "aud": "authenticated",
        "exp": int(time.time()) + 3600,
        "iat": int(time.time()),
        "user_metadata": {"name": "Test User", "avatar_url": "https://x/a.png"},
    }


def test_valid_token_returns_claims():
    claims = _valid_claims()
    token = _mint(claims)

    result = verify_supabase_jwt(token)

    assert result.sub == UUID(claims["sub"])
    assert result.email == "user@example.com"
    assert result.display_name == "Test User"
    assert result.avatar_url == "https://x/a.png"


def test_expired_token_raises():
    claims = _valid_claims()
    claims["exp"] = int(time.time()) - 1

    with pytest.raises(UnauthorizedError) as exc_info:
        verify_supabase_jwt(_mint(claims))
    assert "expired" in exc_info.value.message.lower()


def test_wrong_audience_raises():
    claims = _valid_claims()
    claims["aud"] = "anon"

    with pytest.raises(UnauthorizedError) as exc_info:
        verify_supabase_jwt(_mint(claims))
    assert "audience" in exc_info.value.message.lower()


def test_bad_signature_raises():
    token = _mint(_valid_claims(), secret="wrong-secret")

    with pytest.raises(UnauthorizedError) as exc_info:
        verify_supabase_jwt(token)
    msg = exc_info.value.message.lower()
    assert "signature" in msg or "invalid" in msg


def test_garbage_token_raises():
    with pytest.raises(UnauthorizedError):
        verify_supabase_jwt("not-a-jwt")


def test_avatar_url_falls_back_to_picture():
    claims = _valid_claims()
    claims["user_metadata"] = {"name": "X", "picture": "https://g/p.png"}

    result = verify_supabase_jwt(_mint(claims))
    assert result.avatar_url == "https://g/p.png"
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_auth_service.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.auth'`.

- [ ] **Step 3: Create `app/services/auth.py`**

```python
from typing import Any
from uuid import UUID

import jwt
from pydantic import BaseModel

from ..config import get_settings
from ..errors import UnauthorizedError


class SupabaseClaims(BaseModel):
    """The subset of Supabase JWT claims we care about, plus extracted profile fields."""

    sub: UUID
    email: str
    display_name: str | None = None
    avatar_url: str | None = None


def verify_supabase_jwt(token: str) -> SupabaseClaims:
    """Decode and validate a Supabase-issued access token. Returns extracted claims."""
    settings = get_settings()
    try:
        decoded: dict[str, Any] = jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            audience=settings.supabase_jwt_audience,
        )
    except jwt.ExpiredSignatureError as exc:
        raise UnauthorizedError("Token has expired.") from exc
    except jwt.InvalidAudienceError as exc:
        raise UnauthorizedError("Token audience mismatch.") from exc
    except jwt.InvalidSignatureError as exc:
        raise UnauthorizedError("Invalid token signature.") from exc
    except jwt.DecodeError as exc:
        raise UnauthorizedError("Invalid token.") from exc
    except jwt.InvalidTokenError as exc:
        raise UnauthorizedError("Invalid token.") from exc

    metadata = decoded.get("user_metadata") or {}
    return SupabaseClaims(
        sub=decoded["sub"],
        email=decoded.get("email", ""),
        display_name=metadata.get("name"),
        avatar_url=metadata.get("avatar_url") or metadata.get("picture"),
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_auth_service.py -v`
Expected: 6 PASS.

- [ ] **Step 5: Commit**

```bash
git add app/services/auth.py tests/test_auth_service.py
git commit -m "feat(auth): add verify_supabase_jwt service + SupabaseClaims"
```

---

## Task 8: UserRepository (TDD)

**Files:**
- Create: `app/repositories/__init__.py`
- Create: `app/repositories/user.py`
- Create: `tests/test_user_repository.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_user_repository.py`:

```python
from uuid import UUID, uuid4

import pytest

from app.errors import DatabaseError
from app.repositories.user import UserRepository
from app.services.auth import SupabaseClaims

pytest_plugins = ["tests.db_conftest"]
pytestmark = pytest.mark.db


def _claims(user_id: UUID, **overrides) -> SupabaseClaims:
    base = SupabaseClaims(
        sub=user_id,
        email=f"{user_id}@example.com",
        display_name="Test User",
        avatar_url="https://example.com/a.png",
    )
    return base.model_copy(update=overrides)


async def test_get_by_id_returns_none_when_missing(db_session):
    repo = UserRepository(db_session)
    result = await repo.get_by_id(uuid4())
    assert result is None


async def test_upsert_creates_user_on_first_call(db_session, auth_user_id):
    repo = UserRepository(db_session)
    user = await repo.upsert_from_jwt(_claims(auth_user_id))
    await db_session.commit()

    assert user.id == auth_user_id
    assert user.email == f"{auth_user_id}@example.com"
    assert user.display_name == "Test User"
    assert user.avatar_url == "https://example.com/a.png"
    assert user.created_at is not None


async def test_get_by_id_returns_user_after_upsert(db_session, auth_user_id):
    repo = UserRepository(db_session)
    await repo.upsert_from_jwt(_claims(auth_user_id))
    await db_session.commit()

    result = await repo.get_by_id(auth_user_id)
    assert result is not None
    assert result.id == auth_user_id


async def test_upsert_is_idempotent(db_session, auth_user_id):
    repo = UserRepository(db_session)
    first = await repo.upsert_from_jwt(_claims(auth_user_id))
    await db_session.commit()
    second = await repo.upsert_from_jwt(_claims(auth_user_id))
    await db_session.commit()

    assert first.id == second.id
    assert first.created_at == second.created_at


async def test_upsert_updates_email_and_name_when_changed(db_session, auth_user_id):
    repo = UserRepository(db_session)
    await repo.upsert_from_jwt(_claims(auth_user_id, email="old@example.com"))
    await db_session.commit()

    updated = await repo.upsert_from_jwt(
        _claims(auth_user_id, email="new@example.com", display_name="New Name")
    )
    await db_session.commit()

    assert updated.email == "new@example.com"
    assert updated.display_name == "New Name"


async def test_update_profile_only_changes_provided_fields(db_session, auth_user_id):
    repo = UserRepository(db_session)
    user = await repo.upsert_from_jwt(_claims(auth_user_id))
    await db_session.commit()

    updated = await repo.update_profile(user, display_name="Renamed")
    await db_session.commit()

    assert updated.display_name == "Renamed"
    assert updated.avatar_url == "https://example.com/a.png"  # untouched
    assert updated.email == f"{auth_user_id}@example.com"  # untouched


async def test_database_error_is_wrapped(db_session, auth_user_id, monkeypatch):
    from sqlalchemy.exc import SQLAlchemyError

    repo = UserRepository(db_session)

    async def boom(*_args, **_kwargs):
        raise SQLAlchemyError("kaboom")

    monkeypatch.setattr(db_session, "execute", boom)

    with pytest.raises(DatabaseError):
        await repo.get_by_id(auth_user_id)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_user_repository.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.repositories'` or similar.

- [ ] **Step 3: Create `app/repositories/__init__.py`**

Empty file:

```python
```

- [ ] **Step 4: Create `app/repositories/user.py`**

```python
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from ..errors import DatabaseError
from ..models.user import User
from ..services.auth import SupabaseClaims


class UserRepository:
    """All user-related SQL/ORM access. Routes never call session.execute directly."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, user_id: UUID) -> User | None:
        try:
            result = await self._session.execute(
                select(User).where(User.id == user_id)
            )
            return result.scalar_one_or_none()
        except SQLAlchemyError as exc:
            raise DatabaseError(f"get_by_id failed: {exc}") from exc

    async def upsert_from_jwt(self, claims: SupabaseClaims) -> User:
        """Insert a profile row on first sight, or refresh email/name/avatar on later calls."""
        try:
            existing = await self.get_by_id(claims.sub)
            if existing is None:
                user = User(
                    id=claims.sub,
                    email=claims.email,
                    display_name=claims.display_name,
                    avatar_url=claims.avatar_url,
                )
                self._session.add(user)
                await self._session.flush()
                return user

            existing.email = claims.email
            if claims.display_name is not None:
                existing.display_name = claims.display_name
            if claims.avatar_url is not None:
                existing.avatar_url = claims.avatar_url
            await self._session.flush()
            return existing
        except SQLAlchemyError as exc:
            raise DatabaseError(f"upsert_from_jwt failed: {exc}") from exc

    async def update_profile(self, user: User, **fields: object) -> User:
        try:
            for key, value in fields.items():
                if value is not None:
                    setattr(user, key, value)
            await self._session.flush()
            return user
        except SQLAlchemyError as exc:
            raise DatabaseError(f"update_profile failed: {exc}") from exc
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_user_repository.py -v`
Expected: 7 PASS.

- [ ] **Step 6: Commit**

```bash
git add app/repositories tests/test_user_repository.py
git commit -m "feat(repo): add UserRepository with upsert + update_profile"
```

---

## Task 9: Pydantic user schemas

**Files:**
- Create: `app/schemas/user.py`

- [ ] **Step 1: Create `app/schemas/user.py`**

```python
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class UserRead(BaseModel):
    """Response shape for /me endpoints."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    display_name: str | None
    avatar_url: str | None
    created_at: datetime


class UserUpdate(BaseModel):
    """Request body for PATCH /me. All fields optional; unset fields are not modified."""

    display_name: str | None = None
    avatar_url: str | None = None
```

- [ ] **Step 2: Smoke-import**

Run: `python -c "from app.schemas.user import UserRead, UserUpdate; print(UserRead.model_fields.keys())"`
Expected: `dict_keys(['id', 'email', 'display_name', 'avatar_url', 'created_at'])`

- [ ] **Step 3: Commit**

```bash
git add app/schemas/user.py
git commit -m "feat(schemas): add UserRead and UserUpdate"
```

---

## Task 10: FastAPI dependencies (`get_db_session`, `get_current_user`)

**Files:**
- Create: `app/deps.py`
- Create: `tests/test_auth_dep.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_auth_dep.py`:

```python
import time
from uuid import uuid4

import jwt
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.config import get_settings
from app.deps import get_current_user
from app.errors import register_handlers

pytest_plugins = ["tests.db_conftest"]
pytestmark = pytest.mark.db


def _mint(claims: dict) -> str:
    return jwt.encode(claims, get_settings().supabase_jwt_secret, algorithm="HS256")


def _make_app() -> FastAPI:
    app = FastAPI()
    register_handlers(app)

    @app.get("/whoami")
    async def whoami(user=Depends(get_current_user)):
        return {"id": str(user.id), "email": user.email}

    return app


def test_missing_auth_header_returns_401(test_engine):
    client = TestClient(_make_app())
    response = client.get("/whoami")
    assert response.status_code == 401
    assert response.json()["error_code"] == "UNAUTHORIZED"


def test_malformed_bearer_returns_401(test_engine):
    client = TestClient(_make_app())
    response = client.get("/whoami", headers={"Authorization": "garbage"})
    assert response.status_code == 401
    assert response.json()["error_code"] == "UNAUTHORIZED"


def test_valid_token_creates_profile_and_returns_user(test_engine, auth_user_id):
    token = _mint(
        {
            "sub": str(auth_user_id),
            "email": "auth@example.com",
            "aud": "authenticated",
            "exp": int(time.time()) + 3600,
            "user_metadata": {"name": "Hieu", "avatar_url": "https://a/v.png"},
        }
    )

    client = TestClient(_make_app())
    response = client.get("/whoami", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(auth_user_id)
    assert body["email"] == "auth@example.com"
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_auth_dep.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.deps'`.

- [ ] **Step 3: Create `app/deps.py`**

```python
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from .db.session import get_session_factory
from .errors import UnauthorizedError
from .models.user import User
from .repositories.user import UserRepository
from .services.auth import verify_supabase_jwt


async def get_db_session() -> AsyncIterator[AsyncSession]:
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
        finally:
            await session.close()


def _extract_bearer(header: str | None) -> str:
    if not header:
        raise UnauthorizedError("Missing Authorization header.")
    parts = header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise UnauthorizedError("Malformed Authorization header.")
    return parts[1]


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

- [ ] **Step 4: Override DB factory in tests so deps use the test engine**

Add this fixture to `tests/db_conftest.py` (append at the bottom):

```python
import pytest_asyncio as _pytest_asyncio


@_pytest_asyncio.fixture(autouse=True)
async def _override_session_factory(test_engine, monkeypatch):
    """Make `get_db_session` use the test engine in DB-marked tests."""
    from sqlalchemy.ext.asyncio import async_sessionmaker
    from app.db import session as session_module

    test_factory = async_sessionmaker(test_engine, expire_on_commit=False)
    monkeypatch.setattr(session_module, "get_session_factory", lambda: test_factory)
    yield
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_auth_dep.py -v`
Expected: 3 PASS.

- [ ] **Step 6: Commit**

```bash
git add app/deps.py tests/test_auth_dep.py tests/db_conftest.py
git commit -m "feat(deps): add get_db_session and get_current_user"
```

---

## Task 11: `/me` routes (TDD)

**Files:**
- Create: `app/routes/me.py`
- Create: `tests/test_me_routes.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_me_routes.py`:

```python
import time
from uuid import uuid4

import jwt
import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import create_app

pytest_plugins = ["tests.db_conftest"]
pytestmark = pytest.mark.db


def _mint(sub: str, **extra) -> str:
    payload = {
        "sub": sub,
        "email": extra.get("email", f"{sub}@example.com"),
        "aud": "authenticated",
        "exp": int(time.time()) + 3600,
        "user_metadata": extra.get("user_metadata", {"name": "Test", "avatar_url": "https://a/v.png"}),
    }
    return jwt.encode(payload, get_settings().supabase_jwt_secret, algorithm="HS256")


def test_get_me_unauthenticated_returns_401(test_engine):
    client = TestClient(create_app())
    response = client.get("/api/v1/me")
    assert response.status_code == 401
    assert response.json()["error_code"] == "UNAUTHORIZED"


def test_get_me_authenticated_returns_profile(test_engine, auth_user_id):
    token = _mint(str(auth_user_id))
    client = TestClient(create_app())
    response = client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(auth_user_id)
    assert body["email"] == f"{auth_user_id}@example.com"
    assert body["display_name"] == "Test"
    assert body["avatar_url"] == "https://a/v.png"


def test_patch_me_updates_display_name(test_engine, auth_user_id):
    token = _mint(str(auth_user_id))
    client = TestClient(create_app())

    # Establish profile.
    client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"})

    response = client.patch(
        "/api/v1/me",
        headers={"Authorization": f"Bearer {token}"},
        json={"display_name": "Renamed"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["display_name"] == "Renamed"
    assert body["avatar_url"] == "https://a/v.png"  # untouched


def test_patch_me_with_empty_body_keeps_values(test_engine, auth_user_id):
    token = _mint(str(auth_user_id))
    client = TestClient(create_app())
    client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"})

    response = client.patch(
        "/api/v1/me",
        headers={"Authorization": f"Bearer {token}"},
        json={},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["display_name"] == "Test"
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_me_routes.py -v`
Expected: FAIL — either `ModuleNotFoundError: No module named 'app.routes.me'` or 404 because the router isn't wired yet.

- [ ] **Step 3: Create `app/routes/me.py`**

```python
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..deps import get_current_user, get_db_session
from ..models.user import User
from ..repositories.user import UserRepository
from ..schemas.user import UserRead, UserUpdate

router = APIRouter(prefix="/api/v1", tags=["me"])


@router.get("/me", response_model=UserRead)
async def read_me(user: Annotated[User, Depends(get_current_user)]) -> User:
    return user


@router.patch("/me", response_model=UserRead)
async def update_me(
    body: UserUpdate,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> User:
    repo = UserRepository(session)
    updates = body.model_dump(exclude_unset=True)
    updated = await repo.update_profile(user, **updates)
    await session.commit()
    return updated
```

- [ ] **Step 4: Wire the router into `app/main.py`**

In `app/main.py`, add the import and `include_router` call. The full updated file:

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .errors import register_handlers
from .routes import analyze, me


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="VietCalorie API",
        description="Estimate nutrition from food images using GPT-4o Vision.",
        version="1.0.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_handlers(app)
    app.include_router(analyze.router)
    app.include_router(me.router)

    @app.get("/healthz", tags=["meta"])
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_me_routes.py -v`
Expected: 4 PASS.

- [ ] **Step 6: Run the full test suite**

Run: `pytest -v`
Expected: all tests pass (existing analyze/image/etc tests should still pass; new auth/repo/route tests pass).

- [ ] **Step 7: Commit**

```bash
git add app/routes/me.py app/main.py tests/test_me_routes.py
git commit -m "feat(routes): add GET /me and PATCH /me"
```

---

## Task 12: End-to-end smoke check

**Files:** none modified — runtime verification only.

- [ ] **Step 1: Confirm `.env` is populated for local run**

Open `.env` (NOT committed) and confirm it has real values for `OPENAI_API_KEY`, `DATABASE_URL`, `DATABASE_URL_DIRECT`, `SUPABASE_JWT_SECRET`. If any is missing, copy from `.env.example` and fill in your Supabase project values.

- [ ] **Step 2: Run migrations against your real Supabase project**

Run: `alembic upgrade head`
Expected: `Running upgrade  -> 0001, create users` and exits 0.

Verify in the Supabase dashboard → Table Editor that `public.users` exists.

- [ ] **Step 3: Start the API**

Run: `uvicorn app.main:app --reload`
Expected: server starts, no import errors.

- [ ] **Step 4: Hit `/healthz`**

Run: `curl -s http://127.0.0.1:8000/healthz`
Expected: `{"status":"ok"}`

- [ ] **Step 5: Hit `/me` without auth**

Run: `curl -s -i http://127.0.0.1:8000/api/v1/me`
Expected: HTTP 401, body `{"success":false,"error":"Missing Authorization header.","error_code":"UNAUTHORIZED"}`

- [ ] **Step 6: Hit `/me` with a real Supabase token**

From the mobile app (or via the Supabase dashboard JS console after a Google sign-in), grab a real `access_token`. Then:

Run: `curl -s http://127.0.0.1:8000/api/v1/me -H "Authorization: Bearer <PASTE_TOKEN>"`
Expected: HTTP 200, JSON body with `id`, `email`, `display_name`, `avatar_url`, `created_at`. The `id` matches the Supabase user UUID.

Verify in Supabase dashboard that a row was inserted in `public.users`.

- [ ] **Step 7: Hit `PATCH /me` with the same token**

Run:
```bash
curl -s -X PATCH http://127.0.0.1:8000/api/v1/me \
  -H "Authorization: Bearer <PASTE_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"display_name":"Hieu Vo"}'
```
Expected: HTTP 200, `display_name` is `"Hieu Vo"` in the response.

- [ ] **Step 8: Done — commit any final cleanup**

If you tweaked anything during smoke testing:

```bash
git add -A
git commit -m "chore: smoke-test cleanup"
```

---

## After this plan

The mobile session (`~/Documents/vietcalorie`) implements its half of Section 11 of the spec: install `supabase_flutter` (or RN equivalent), call `signInWithOAuth(OAuthProvider.google)`, and attach `Authorization: Bearer ${session.accessToken}` to every API call. The API contract is fully defined in this plan and the spec — no further coordination required between sessions.

Future plans (each gets its own spec → plan):
- Meals/foods table + endpoints (the calorie tracking domain)
- Email-sync strategy (open question §12 of spec)
- Test-DB strategy for CI (open question §12 of spec)
