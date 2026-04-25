import base64
import binascii
from typing import Annotated

from fastapi import APIRouter, Depends, File, Request, UploadFile

from ..errors import InvalidImageError, UnsupportedFormatError
from ..schemas.nutrition import AnalyzeRequestBase64, AnalyzeResponse
from ..services.image import validate_and_normalize
from ..services.vision import OpenAIVisionClient, get_vision_client

router = APIRouter(prefix="/api/v1", tags=["analyze"])


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(
    request: Request,
    vision: Annotated[OpenAIVisionClient, Depends(get_vision_client)],
    image: UploadFile | None = File(default=None),
) -> AnalyzeResponse:
    content_type = (request.headers.get("content-type") or "").split(";")[0].strip().lower()

    if content_type.startswith("multipart/"):
        if image is None:
            raise InvalidImageError("Missing 'image' field in multipart request.")
        image_bytes = await image.read()
        media_type = image.content_type or ""
    elif content_type == "application/json":
        body = await request.json()
        if not isinstance(body, dict):
            raise InvalidImageError("Request body must be a JSON object.")
        try:
            payload = AnalyzeRequestBase64(**body)
        except Exception as exc:
            raise InvalidImageError(f"Invalid JSON body: {exc}") from exc
        try:
            image_bytes = base64.b64decode(payload.image_base64, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise InvalidImageError(f"image_base64 is not valid base64: {exc}") from exc
        media_type = payload.media_type
    elif content_type:
        raise UnsupportedFormatError(
            f"Unsupported Content-Type '{content_type}'. Use multipart/form-data or application/json."
        )
    else:
        raise InvalidImageError("Missing image: no Content-Type header and no image provided.")

    normalized_bytes, normalized_media_type = validate_and_normalize(image_bytes, media_type)
    return vision.analyze_food(normalized_bytes, normalized_media_type)
