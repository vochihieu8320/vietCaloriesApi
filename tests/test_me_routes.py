import time

import httpx
import jwt
import pytest

from app.config import get_settings
from app.deps import get_db_session, get_current_user
from app.main import create_app

pytest_plugins = ["tests.db_conftest"]
pytestmark = pytest.mark.db


def _mint(sub: str, **extra) -> str:
    payload = {
        "sub": sub,
        "email": extra.get("email", f"{sub}@example.com"),
        "aud": "authenticated",
        "exp": int(time.time()) + 3600,
        "user_metadata": extra.get("user_metadata", {"name": "Test", "avatar_url": "https://a/v.png"}),
    }
    return jwt.encode(payload, get_settings().supabase_jwt_secret, algorithm="HS256")


def _build_app(db_session=None):
    app = create_app()
    if db_session is not None:
        app.dependency_overrides[get_db_session] = lambda: db_session
    return app


async def test_get_me_unauthenticated_returns_401():
    app = _build_app()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/me")
    assert response.status_code == 401
    assert response.json()["error_code"] == "UNAUTHORIZED"


async def test_get_me_authenticated_returns_profile(db_session, auth_user_id):
    app = _build_app(db_session)
    token = _mint(str(auth_user_id))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(auth_user_id)
    assert body["email"] == f"{auth_user_id}@example.com"
    assert body["display_name"] == "Test"
    assert body["avatar_url"] == "https://a/v.png"


async def test_patch_me_updates_display_name(db_session, auth_user_id):
    app = _build_app(db_session)
    token = _mint(str(auth_user_id))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # First call establishes the profile.
        await client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"})

        response = await client.patch(
            "/api/v1/me",
            headers={"Authorization": f"Bearer {token}"},
            json={"display_name": "Renamed"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["display_name"] == "Renamed"
    assert body["avatar_url"] == "https://a/v.png"


async def test_patch_me_with_empty_body_keeps_values(db_session, auth_user_id):
    app = _build_app(db_session)
    token = _mint(str(auth_user_id))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        await client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"})

        response = await client.patch(
            "/api/v1/me",
            headers={"Authorization": f"Bearer {token}"},
            json={},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["display_name"] == "Test"
