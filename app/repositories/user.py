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
