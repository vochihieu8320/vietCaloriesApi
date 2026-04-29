from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .schemas.nutrition import ErrorResponse


class AppError(Exception):
    error_code: str = "APP_ERROR"
    message: str = "An error occurred."
    http_status: int = 500

    def __init__(self, message: str | None = None):
        if message is not None:
            self.message = message
        super().__init__(self.message)


class InvalidImageError(AppError):
    error_code = "INVALID_IMAGE"
    message = "The provided image is invalid or could not be read."
    http_status = 400


class UnsupportedFormatError(AppError):
    error_code = "UNSUPPORTED_FORMAT"
    message = "Image format not supported. Use JPEG, PNG, or WEBP."
    http_status = 422


class NoFoodDetectedError(AppError):
    error_code = "NO_FOOD_DETECTED"
    message = "Could not detect food in the provided image."
    http_status = 400


class LLMError(AppError):
    error_code = "LLM_ERROR"
    message = "OpenAI call failed or returned an unparseable response."
    http_status = 500


class RateLimitedError(AppError):
    error_code = "RATE_LIMITED"
    message = "Too many requests. Please retry after a short delay."
    http_status = 429


class InsufficientQuotaError(AppError):
    error_code = "INSUFFICIENT_QUOTA"
    message = (
        "OpenAI account has no remaining quota. Add billing or buy credits at "
        "https://platform.openai.com/settings/organization/billing"
    )
    http_status = 429


class UnauthorizedError(AppError):
    error_code = "UNAUTHORIZED"
    message = "Missing or invalid Authorization token."
    http_status = 401


class DatabaseError(AppError):
    error_code = "DATABASE_ERROR"
    message = "Database operation failed."
    http_status = 500


def register_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.http_status,
            content=ErrorResponse(error=exc.message, error_code=exc.error_code).model_dump(),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=400,
            content=ErrorResponse(
                error="Request payload is invalid or malformed.",
                error_code="INVALID_IMAGE",
            ).model_dump(),
        )
