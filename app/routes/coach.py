from typing import Annotated

from fastapi import APIRouter, Depends

from ..deps import get_current_user
from ..models.user import User
from ..schemas.coach import CoachAskRequest, CoachAskResponse
from ..services.coach import get_coach_client

router = APIRouter(prefix="/api/v1", tags=["coach"])


@router.post("/coach/ask", response_model=CoachAskResponse)
async def coach_ask(
    payload: CoachAskRequest,
    user: Annotated[User, Depends(get_current_user)],
) -> CoachAskResponse:
    """Single-turn ask: question + today's nutrition state → short answer + chips.

    Auth-gated so the OpenAI quota only burns for signed-in users. The
    coach client is built per-request inside the handler — wiring it as a
    `Depends(...)` made FastAPI mistakenly auto-embed the request body
    (likely because the factory's optional `Settings | None = None`
    parameter pulled the parser onto a different code path).
    """
    coach = get_coach_client()
    return coach.ask(payload)
