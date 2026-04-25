import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from openai import OpenAI

from app.main import create_app
from app.services.vision import OpenAIVisionClient, get_vision_client


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "pho.jpg"

pytestmark = pytest.mark.live


@pytest.fixture
def live_client():
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key or api_key.startswith("test"):
        pytest.skip("OPENAI_API_KEY not set or is the test placeholder")
    if not FIXTURE_PATH.exists():
        pytest.skip(f"Fixture image not found at {FIXTURE_PATH}")

    app = create_app()
    real_client = OpenAIVisionClient(
        client=OpenAI(api_key=api_key),
        model=os.environ.get("OPENAI_MODEL", "gpt-4o"),
    )
    app.dependency_overrides[get_vision_client] = lambda: real_client
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_live_analyze_real_image(live_client):
    with FIXTURE_PATH.open("rb") as f:
        response = live_client.post(
            "/api/v1/analyze",
            files={"image": ("pho.jpg", f.read(), "image/jpeg")},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert isinstance(body["dish_name"], str) and body["dish_name"]
    assert body["nutrition"]["calories_kcal"] > 0
    assert body["confidence"] in {"high", "medium", "low"}
