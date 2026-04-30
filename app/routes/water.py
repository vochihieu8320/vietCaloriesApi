from datetime import datetime, time, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..deps import get_current_user, get_db_session
from ..models.user import User
from ..repositories.water import WaterRepository
from ..schemas.water import WaterLogCreate, WaterLogRead, WaterTotal

router = APIRouter(prefix="/api/v1", tags=["water"])


@router.post("/water", response_model=WaterLogRead, status_code=201)
async def create_water_log(
    body: WaterLogCreate,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> WaterLogRead:
    repo = WaterRepository(session)
    log = await repo.create(
        user_id=user.id,
        amount_ml=body.amount_ml,
        consumed_at=body.consumed_at,
    )
    return WaterLogRead.model_validate(log)


@router.get("/water/today", response_model=WaterTotal)
async def water_today(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> WaterTotal:
    """Sum of water_logs for the current UTC day. Mobile clients can compute
    a local-day window themselves, but this endpoint is a useful default."""
    now = datetime.now(timezone.utc)
    start = datetime.combine(now.date(), time.min, tzinfo=timezone.utc)
    end = start + timedelta(days=1)
    repo = WaterRepository(session)
    total_ml, count = await repo.total_for_user(user.id, since=start, until=end)
    return WaterTotal(total_ml=total_ml, log_count=count)
