from typing import Annotated

from fastapi import APIRouter, Depends, Request

from ..deps import get_current_user
from ..models.user import User
from ..schemas.coach import CoachAskRequest, CoachAskResponse
from ..services.coach import CoachClient, get_coach_client

router = APIRouter(prefix="/api/v1", tags=["coach"])


@router.post("/coach/ask", response_model=CoachAskResponse)
async def coach_ask(
    request: Request,
    body: CoachAskRequest,
    user: Annotated[User, Depends(get_current_user)],
    coach: Annotated[CoachClient, Depends(get_coach_client)],
) -> CoachAskResponse:
    """Single-turn ask: question + today's nutrition state → short answer + chips.

    Auth-gated so the OpenAI quota only burns for signed-in users.
    """
    print(
        f"[COACH] ct={request.headers.get('content-type')!r} "
        f"len={request.headers.get('content-length')!r} "
        f"qlen={len(body.question)}"
    )
    return coach.ask(body)
