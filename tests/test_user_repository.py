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
