import base64
import io
from unittest.mock import MagicMock

from PIL import Image

from app.errors import LLMError, NoFoodDetectedError, RateLimitedError
from app.schemas.nutrition import AnalyzeResponse, NutritionData


HAPPY_RESPONSE = AnalyzeResponse(
    dish_name="Phở bò",
    confidence="high",
    nutrition=NutritionData(calories_kcal=480, protein_g=28, carbs_g=62, fat_g=10),
    notes="Standard bowl",
)


def _jpeg_bytes(width: int = 200, height: int = 200) -> bytes:
    image = Image.new("RGB", (width, height), color=(200, 100, 50))
    out = io.BytesIO()
    image.save(out, format="JPEG")
    return out.getvalue()


def test_multipart_happy_path(client, mock_vision: MagicMock):
    mock_vision.analyze_food.return_value = HAPPY_RESPONSE
    response = client.post(
        "/api/v1/analyze",
        files={"image": ("pho.jpg", _jpeg_bytes(), "image/jpeg")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["dish_name"] == "Phở bò"
    assert body["nutrition"]["calories_kcal"] == 480
    assert body["confidence"] == "high"
    assert mock_vision.analyze_food.called


def test_base64_happy_path(client, mock_vision: MagicMock):
    mock_vision.analyze_food.return_value = HAPPY_RESPONSE
    img_b64 = base64.b64encode(_jpeg_bytes()).decode("ascii")
    response = client.post(
        "/api/v1/analyze",
        json={"image_base64": img_b64, "media_type": "image/jpeg"},
    )
    assert response.status_code == 200
    assert response.json()["dish_name"] == "Phở bò"


def test_multipart_missing_image(client):
    response = client.post("/api/v1/analyze", files={})
    assert response.status_code == 400
    body = response.json()
    assert body["success"] is False
    assert body["error_code"] == "INVALID_IMAGE"


def test_multipart_unsupported_format(client):
    # GIF bytes are rejected by the media-type check before Pillow sees them
    response = client.post(
        "/api/v1/analyze",
        files={"image": ("anim.gif", b"GIF89a" + b"\x00" * 200, "image/gif")},
    )
    assert response.status_code == 422
    assert response.json()["error_code"] == "UNSUPPORTED_FORMAT"


def test_base64_invalid_encoding(client):
    response = client.post(
        "/api/v1/analyze",
        json={"image_base64": "not valid base64!!!", "media_type": "image/jpeg"},
    )
    assert response.status_code == 400
    assert response.json()["error_code"] == "INVALID_IMAGE"


def test_base64_missing_field(client):
    response = client.post(
        "/api/v1/analyze",
        json={"media_type": "image/jpeg"},  # no image_base64
    )
    assert response.status_code == 400
    assert response.json()["error_code"] == "INVALID_IMAGE"


def test_no_food_detected(client, mock_vision: MagicMock):
    mock_vision.analyze_food.side_effect = NoFoodDetectedError()
    response = client.post(
        "/api/v1/analyze",
        files={"image": ("blank.jpg", _jpeg_bytes(), "image/jpeg")},
    )
    assert response.status_code == 400
    assert response.json()["error_code"] == "NO_FOOD_DETECTED"


def test_rate_limited(client, mock_vision: MagicMock):
    mock_vision.analyze_food.side_effect = RateLimitedError()
    response = client.post(
        "/api/v1/analyze",
        files={"image": ("x.jpg", _jpeg_bytes(), "image/jpeg")},
    )
    assert response.status_code == 429
    assert response.json()["error_code"] == "RATE_LIMITED"


def test_llm_error(client, mock_vision: MagicMock):
    mock_vision.analyze_food.side_effect = LLMError()
    response = client.post(
        "/api/v1/analyze",
        files={"image": ("x.jpg", _jpeg_bytes(), "image/jpeg")},
    )
    assert response.status_code == 500
    assert response.json()["error_code"] == "LLM_ERROR"


def test_unsupported_content_type(client):
    response = client.post(
        "/api/v1/analyze",
        content=b"raw bytes",
        headers={"Content-Type": "application/octet-stream"},
    )
    assert response.status_code == 422
    assert response.json()["error_code"] == "UNSUPPORTED_FORMAT"
