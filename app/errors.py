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
