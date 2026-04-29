import time
from uuid import UUID, uuid4

import jwt
import pytest

from app.config import get_settings
from app.errors import UnauthorizedError
from app.services.auth import verify_supabase_jwt


def _mint(claims: dict, secret: str | None = None) -> str:
    settings = get_settings()
    return jwt.encode(claims, secret or settings.supabase_jwt_secret, algorithm="HS256")


def _valid_claims() -> dict:
    return {
        "sub": str(uuid4()),
        "email": "user@example.com",
        "aud": "authenticated",
        "exp": int(time.time()) + 3600,
        "iat": int(time.time()),
        "user_metadata": {"name": "Test User", "avatar_url": "https://x/a.png"},
    }


def test_valid_token_returns_claims():
    claims = _valid_claims()
    token = _mint(claims)

    result = verify_supabase_jwt(token)

    assert result.sub == UUID(claims["sub"])
    assert result.email == "user@example.com"
    assert result.display_name == "Test User"
    assert result.avatar_url == "https://x/a.png"


def test_expired_token_raises():
    claims = _valid_claims()
    claims["exp"] = int(time.time()) - 1

    with pytest.raises(UnauthorizedError) as exc_info:
        verify_supabase_jwt(_mint(claims))
    assert "expired" in exc_info.value.message.lower()


def test_wrong_audience_raises():
    claims = _valid_claims()
    claims["aud"] = "anon"

    with pytest.raises(UnauthorizedError) as exc_info:
        verify_supabase_jwt(_mint(claims))
    assert "audience" in exc_info.value.message.lower()


def test_bad_signature_raises():
    token = _mint(_valid_claims(), secret="wrong-secret")

    with pytest.raises(UnauthorizedError) as exc_info:
        verify_supabase_jwt(token)
    msg = exc_info.value.message.lower()
    assert "signature" in msg or "invalid" in msg


def test_garbage_token_raises():
    with pytest.raises(UnauthorizedError):
        verify_supabase_jwt("not-a-jwt")


def test_avatar_url_falls_back_to_picture():
    claims = _valid_claims()
    claims["user_metadata"] = {"name": "X", "picture": "https://g/p.png"}

    result = verify_supabase_jwt(_mint(claims))
    assert result.avatar_url == "https://g/p.png"
