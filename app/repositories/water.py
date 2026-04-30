from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from ..errors import DatabaseError
from ..models.water import WaterLog


class WaterRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        user_id: UUID,
        amount_ml: int,
        consumed_at: datetime | None = None,
    ) -> WaterLog:
        try:
            log = WaterLog(user_id=user_id, amount_ml=amount_ml)
            if consumed_at is not None:
                log.consumed_at = consumed_at
            self._session.add(log)
            await self._session.flush()
            return log
        except SQLAlchemyError as exc:
            raise DatabaseError(f"create water log failed: {exc}") from exc

    async def list_for_user(
        self,
        user_id: UUID,
        *,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 200,
    ) -> list[WaterLog]:
        try:
            stmt = (
                select(WaterLog)
                .where(WaterLog.user_id == user_id)
                .order_by(WaterLog.consumed_at.desc())
                .limit(limit)
            )
            if since is not None:
                stmt = stmt.where(WaterLog.consumed_at >= since)
            if until is not None:
                stmt = stmt.where(WaterLog.consumed_at <= until)
            result = await self._session.execute(stmt)
            return list(result.scalars().all())
        except SQLAlchemyError as exc:
            raise DatabaseError(f"list water failed: {exc}") from exc

    async def total_for_user(
        self,
        user_id: UUID,
        *,
        since: datetime,
        until: datetime,
    ) -> tuple[int, int]:
        """Return (total_ml, log_count) within [since, until]."""
        try:
            stmt = select(
                func.coalesce(func.sum(WaterLog.amount_ml), 0),
                func.count(WaterLog.id),
            ).where(
                WaterLog.user_id == user_id,
                WaterLog.consumed_at >= since,
                WaterLog.consumed_at <= until,
            )
            row = (await self._session.execute(stmt)).one()
            return int(row[0]), int(row[1])
        except SQLAlchemyError as exc:
            raise DatabaseError(f"sum water failed: {exc}") from exc
