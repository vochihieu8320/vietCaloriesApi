from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..deps import get_current_user, get_db_session
from ..errors import NotFoundError
from ..models.user import User
from ..repositories.meal import MealRepository
from ..schemas.meal import MealCreate, MealRead, MealUpdate

router = APIRouter(prefix="/api/v1", tags=["meals"])


@router.post("/meals", response_model=MealRead, status_code=201)
async def create_meal(
    body: MealCreate,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> MealRead:
    repo = MealRepository(session)
    meal = await repo.create(
        user_id=user.id,
        meal_type=body.meal_type,
        dish_name=body.dish_name,
        confidence=body.confidence,
        calories_kcal=body.calories_kcal,
        protein_g=body.protein_g,
        carbs_g=body.carbs_g,
        fat_g=body.fat_g,
        notes=body.notes,
        consumed_at=body.consumed_at,
    )
    return MealRead.model_validate(meal)


@router.get("/meals", response_model=list[MealRead])
async def list_meals(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    since: datetime | None = Query(default=None),
    until: datetime | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
) -> list[MealRead]:
    repo = MealRepository(session)
    meals = await repo.list_for_user(user.id, since=since, until=until, limit=limit)
    return [MealRead.model_validate(m) for m in meals]


@router.patch("/meals/{meal_id}", response_model=MealRead)
async def update_meal(
    meal_id: UUID,
    body: MealUpdate,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> MealRead:
    repo = MealRepository(session)
    meal = await repo.get_by_id(meal_id, user_id=user.id)
    if meal is None:
        raise NotFoundError("Meal not found.")
    updates = body.model_dump(exclude_unset=True)
    updated = await repo.update(meal, **updates)
    return MealRead.model_validate(updated)


@router.delete("/meals/{meal_id}", status_code=204)
async def delete_meal(
    meal_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> None:
    repo = MealRepository(session)
    meal = await repo.get_by_id(meal_id, user_id=user.id)
    if meal is None:
        raise NotFoundError("Meal not found.")
    await repo.delete(meal)
