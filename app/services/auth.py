import logging
from functools import lru_cache
from typing import Any
from uuid import UUID

import jwt
from jwt import PyJWKClient
from pydantic import BaseModel

from ..config import get_settings
from ..errors import UnauthorizedError

logger = logging.getLogger(__name__)

# Algorithms Supabase may use to sign access tokens. ES256/RS256 = "JWT Signing Keys"
# (asymmetric, public key fetched from JWKS). HS256 = legacy shared-secret mode.
_ASYMMETRIC_ALGS = ("ES256", "RS256")


class SupabaseClaims(BaseModel):
    """The subset of Supabase JWT claims we care about, plus extracted profile fields."""

    sub: UUID
    email: str
    display_name: str | None = None
    avatar_url: str | None = None


@lru_cache
def _jwks_client() -> PyJWKClient:
    settings = get_settings()
    jwks_url = f"{settings.supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"
    # cache_keys=True keeps the keys in memory; default lifespan is 5min and refresh
    # happens automatically when a token references an unknown kid.
    return PyJWKClient(jwks_url, cache_keys=True)


def _log_token_header(token: str, label: str) -> None:
    """Best-effort log of the JWT header (no signature verification)."""
    try:
        header = jwt.get_unverified_header(token)
        unverified = jwt.decode(token, options={"verify_signature": False})
        logger.warning(
            "[auth] %s alg=%s kid=%s aud=%s iss=%s sub=%s",
            label,
            header.get("alg"),
            header.get("kid"),
            unverified.get("aud"),
            unverified.get("iss"),
            unverified.get("sub"),
        )
    except Exception as exc:
        logger.warning("[auth] %s could not decode header: %s", label, exc)


def verify_supabase_jwt(token: str) -> SupabaseClaims:
    """Decode and validate a Supabase-issued access token. Returns extracted claims.

    Selects the verification path based on the token header's `alg`:
      - ES256/RS256 → fetch the matching public key from the project's JWKS endpoint.
      - HS256 → verify with the shared `SUPABASE_JWT_SECRET` (legacy projects).
    """
    settings = get_settings()
    try:
        header = jwt.get_unverified_header(token)
    except jwt.DecodeError as exc:
        raise UnauthorizedError("Invalid token.") from exc

    alg = header.get("alg")

    try:
        if alg in _ASYMMETRIC_ALGS:
            signing_key = _jwks_client().get_signing_key_from_jwt(token).key
            decoded: dict[str, Any] = jwt.decode(
                token,
                signing_key,
                algorithms=[alg],
                audience=settings.supabase_jwt_audience,
            )
        elif alg == "HS256":
            decoded = jwt.decode(
                token,
                settings.supabase_jwt_secret,
                algorithms=["HS256"],
                audience=settings.supabase_jwt_audience,
            )
        else:
            _log_token_header(token, f"unsupported alg {alg!r}")
            raise UnauthorizedError("Unsupported token algorithm.")
    except jwt.ExpiredSignatureError as exc:
        _log_token_header(token, "expired")
        raise UnauthorizedError("Token has expired.") from exc
    except jwt.InvalidAudienceError as exc:
        _log_token_header(token, "bad audience")
        raise UnauthorizedError("Token audience mismatch.") from exc
    except jwt.InvalidSignatureError as exc:
        _log_token_header(token, "bad signature")
        raise UnauthorizedError("Invalid token signature.") from exc
    except jwt.DecodeError as exc:
        _log_token_header(token, "decode error")
        raise UnauthorizedError("Invalid token.") from exc
    except jwt.InvalidTokenError as exc:
        _log_token_header(token, f"invalid token ({type(exc).__name__})")
        raise UnauthorizedError("Invalid token.") from exc

    metadata = decoded.get("user_metadata") or {}
    return SupabaseClaims(
        sub=decoded["sub"],
        email=decoded.get("email", ""),
        display_name=metadata.get("name"),
        avatar_url=metadata.get("avatar_url") or metadata.get("picture"),
    )
