import os

# Set BEFORE importing app modules so config loads cleanly
os.environ.setdefault("OPENAI_API_KEY", "test-key-not-real")

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.services.vision import OpenAIVisionClient, get_vision_client


@pytest.fixture
def mock_vision() -> MagicMock:
    return MagicMock(spec=OpenAIVisionClient)


@pytest.fixture
def app(mock_vision: MagicMock):
    application = create_app()
    application.dependency_overrides[get_vision_client] = lambda: mock_vision
    yield application
    application.dependency_overrides.clear()


@pytest.fixture
def client(app) -> TestClient:
    return TestClient(app)
