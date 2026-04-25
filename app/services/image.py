import io

from PIL import Image, UnidentifiedImageError

from ..config import get_settings
from ..errors import InvalidImageError, UnsupportedFormatError

SUPPORTED_MEDIA_TYPES = {"image/jpeg", "image/png", "image/webp"}
MIN_DIMENSION = 100
MAX_DIMENSION = 4096


def validate_and_normalize(image_bytes: bytes, media_type: str) -> tuple[bytes, str]:
    if not image_bytes:
        raise InvalidImageError("Image payload is empty.")

    if media_type not in SUPPORTED_MEDIA_TYPES:
        raise UnsupportedFormatError(
            f"Unsupported media type '{media_type}'. Use JPEG, PNG, or WEBP."
        )

    settings = get_settings()
    if len(image_bytes) > settings.max_image_bytes:
        raise InvalidImageError(
            f"Image exceeds max size of {settings.max_image_bytes} bytes."
        )

    try:
        image = Image.open(io.BytesIO(image_bytes))
        image.load()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise InvalidImageError(f"Could not decode image: {exc}") from exc

    width, height = image.size
    if width < MIN_DIMENSION or height < MIN_DIMENSION:
        raise InvalidImageError(
            f"Image dimensions too small ({width}x{height}). Minimum {MIN_DIMENSION}x{MIN_DIMENSION}."
        )

    if max(width, height) > MAX_DIMENSION:
        image.thumbnail((MAX_DIMENSION, MAX_DIMENSION))

    if image.mode != "RGB":
        image = image.convert("RGB")

    out = io.BytesIO()
    image.save(out, format="JPEG", quality=90)
    return out.getvalue(), "image/jpeg"
