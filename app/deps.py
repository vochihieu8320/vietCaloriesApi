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
            await session.commit()
        except Exception:
            await session.rollback()
            raise
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
    return user
