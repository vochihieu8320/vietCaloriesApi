from typing import Any
from uuid import UUID

import jwt
from pydantic import BaseModel

from ..config import get_settings
from ..errors import UnauthorizedError


class SupabaseClaims(BaseModel):
    """The subset of Supabase JWT claims we care about, plus extracted profile fields."""

    sub: UUID
    email: str
    display_name: str | None = None
    avatar_url: str | None = None


def verify_supabase_jwt(token: str) -> SupabaseClaims:
    """Decode and validate a Supabase-issued access token. Returns extracted claims."""
    settings = get_settings()
    try:
        decoded: dict[str, Any] = jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            audience=settings.supabase_jwt_audience,
        )
    except jwt.ExpiredSignatureError as exc:
        raise UnauthorizedError("Token has expired.") from exc
    except jwt.InvalidAudienceError as exc:
        raise UnauthorizedError("Token audience mismatch.") from exc
    except jwt.InvalidSignatureError as exc:
        raise UnauthorizedError("Invalid token signature.") from exc
    except jwt.DecodeError as exc:
        raise UnauthorizedError("Invalid token.") from exc
    except jwt.InvalidTokenError as exc:
        raise UnauthorizedError("Invalid token.") from exc

    metadata = decoded.get("user_metadata") or {}
    return SupabaseClaims(
        sub=decoded["sub"],
        email=decoded.get("email", ""),
        display_name=metadata.get("name"),
        avatar_url=metadata.get("avatar_url") or metadata.get("picture"),
    )
