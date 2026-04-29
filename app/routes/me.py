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
    return updated
