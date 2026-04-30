import time
from uuid import uuid4

import httpx
import jwt
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.deps import get_current_user, get_db_session
from app.errors import register_handlers

pytest_plugins = ["tests.db_conftest"]
pytestmark = pytest.mark.db


def _mint(claims: dict) -> str:
    return jwt.encode(claims, get_settings().supabase_jwt_secret, algorithm="HS256")


def _make_app(db_session: AsyncSession | None = None) -> FastAPI:
    app = FastAPI()
    register_handlers(app)

    @app.get("/whoami")
    async def whoami(user=Depends(get_current_user)):
        return {"id": str(user.id), "email": user.email}

    if db_session is not None:
        # Inject the test's db_session so that the dep operates within the
        # savepoint-isolated transaction. This ensures the auth_user_id FK
        # is visible and all writes roll back after the test.
        async def _override_db():
            yield db_session

        app.dependency_overrides[get_db_session] = _override_db

    return app


def test_missing_auth_header_returns_401(test_engine):
    client = TestClient(_make_app())
    response = client.get("/whoami")
    assert response.status_code == 401
    assert response.json()["error_code"] == "UNAUTHORIZED"


def test_malformed_bearer_returns_401(test_engine):
    client = TestClient(_make_app())
    response = client.get("/whoami", headers={"Authorization": "garbage"})
    assert response.status_code == 401
    assert response.json()["error_code"] == "UNAUTHORIZED"


async def test_valid_token_creates_profile_and_returns_user(test_engine, db_session, auth_user_id):
    token = _mint(
        {
            "sub": str(auth_user_id),
            "email": "auth@example.com",
            "aud": "authenticated",
            "exp": int(time.time()) + 3600,
            "user_metadata": {"name": "Hieu", "avatar_url": "https://a/v.png"},
        }
    )

    app = _make_app(db_session=db_session)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(
            "/whoami", headers={"Authorization": f"Bearer {token}"}
        )

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(auth_user_id)
    assert body["email"] == "auth@example.com"
