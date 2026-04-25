import io
import os

import pytest
from PIL import Image

# ensure config import doesn't fail
os.environ.setdefault("OPENAI_API_KEY", "test-key-not-real")

from app.errors import InvalidImageError, UnsupportedFormatError
from app.services.image import validate_and_normalize


def _make_image_bytes(width: int, height: int, fmt: str = "JPEG") -> bytes:
    image = Image.new("RGB", (width, height), color=(255, 0, 0))
    out = io.BytesIO()
    image.save(out, format=fmt)
    return out.getvalue()


def test_rejects_unsupported_media_type():
    with pytest.raises(UnsupportedFormatError):
        validate_and_normalize(b"\x00\x01\x02", "image/gif")


def test_rejects_empty_payload():
    with pytest.raises(InvalidImageError):
        validate_and_normalize(b"", "image/jpeg")


def test_rejects_oversized_payload():
    big = _make_image_bytes(200, 200) + b"\x00" * (11 * 1024 * 1024)
    with pytest.raises(InvalidImageError):
        validate_and_normalize(big, "image/jpeg")


def test_rejects_undecodable_bytes():
    with pytest.raises(InvalidImageError):
        validate_and_normalize(b"not an image", "image/jpeg")


def test_rejects_too_small_dimensions():
    tiny = _make_image_bytes(50, 50)
    with pytest.raises(InvalidImageError):
        validate_and_normalize(tiny, "image/jpeg")


def test_resizes_when_max_dimension_exceeded():
    big = _make_image_bytes(5000, 3000)
    out_bytes, media_type = validate_and_normalize(big, "image/jpeg")
    out_image = Image.open(io.BytesIO(out_bytes))
    assert max(out_image.size) <= 4096
    assert media_type == "image/jpeg"


def test_passthrough_jpeg():
    img_bytes = _make_image_bytes(200, 200)
    out_bytes, media_type = validate_and_normalize(img_bytes, "image/jpeg")
    assert media_type == "image/jpeg"
    assert len(out_bytes) > 0


def test_passthrough_png_re_encodes_to_jpeg():
    img_bytes = _make_image_bytes(200, 200, fmt="PNG")
    out_bytes, media_type = validate_and_normalize(img_bytes, "image/png")
    out_image = Image.open(io.BytesIO(out_bytes))
    assert media_type == "image/jpeg"  # always re-encoded
    assert out_image.size == (200, 200)


def test_passthrough_webp_re_encodes_to_jpeg():
    img_bytes = _make_image_bytes(200, 200, fmt="WEBP")
    out_bytes, media_type = validate_and_normalize(img_bytes, "image/webp")
    assert media_type == "image/jpeg"
    assert len(out_bytes) > 0
