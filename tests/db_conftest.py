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


@pytest_asyncio.fixture(scope="session", loop_scope="session")
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
