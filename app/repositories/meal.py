from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from ..errors import DatabaseError
from ..models.meal import Meal


class MealRepository:
    """All meal-related SQL/ORM access."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        user_id: UUID,
        meal_type: str,
        dish_name: str,
        confidence: str,
        calories_kcal: int,
        protein_g: float,
        carbs_g: float,
        fat_g: float,
        notes: str | None = None,
        consumed_at: datetime | None = None,
    ) -> Meal:
        try:
            meal = Meal(
                user_id=user_id,
                meal_type=meal_type,
                dish_name=dish_name,
                confidence=confidence,
                calories_kcal=calories_kcal,
                protein_g=protein_g,
                carbs_g=carbs_g,
                fat_g=fat_g,
                notes=notes,
            )
            if consumed_at is not None:
                meal.consumed_at = consumed_at
            self._session.add(meal)
            await self._session.flush()
            return meal
        except SQLAlchemyError as exc:
            raise DatabaseError(f"create meal failed: {exc}") from exc

    async def get_by_id(self, meal_id: UUID, *, user_id: UUID) -> Meal | None:
        """Fetch a meal scoped to a specific user (so users can't read others')."""
        try:
            result = await self._session.execute(
                select(Meal).where(Meal.id == meal_id, Meal.user_id == user_id)
            )
            return result.scalar_one_or_none()
        except SQLAlchemyError as exc:
            raise DatabaseError(f"get meal failed: {exc}") from exc

    async def update(self, meal: Meal, **fields) -> Meal:
        """Update only the fields whose value is not None."""
        try:
            for key, value in fields.items():
                if value is not None:
                    setattr(meal, key, value)
            await self._session.flush()
            return meal
        except SQLAlchemyError as exc:
            raise DatabaseError(f"update meal failed: {exc}") from exc

    async def delete(self, meal: Meal) -> None:
        try:
            await self._session.delete(meal)
            await self._session.flush()
        except SQLAlchemyError as exc:
            raise DatabaseError(f"delete meal failed: {exc}") from exc

    async def list_for_user(
        self,
        user_id: UUID,
        *,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 200,
    ) -> list[Meal]:
        try:
            stmt = (
                select(Meal)
                .where(Meal.user_id == user_id)
                .order_by(Meal.consumed_at.desc())
                .limit(limit)
            )
            if since is not None:
                stmt = stmt.where(Meal.consumed_at >= since)
            if until is not None:
                stmt = stmt.where(Meal.consumed_at <= until)
            result = await self._session.execute(stmt)
            return list(result.scalars().all())
        except SQLAlchemyError as exc:
            raise DatabaseError(f"list meals failed: {exc}") from exc
