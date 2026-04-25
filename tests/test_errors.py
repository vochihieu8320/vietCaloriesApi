import pytest

from app.errors import (
    AppError,
    InvalidImageError,
    LLMError,
    NoFoodDetectedError,
    RateLimitedError,
    UnsupportedFormatError,
)


@pytest.mark.parametrize(
    "exc_cls,expected_code,expected_status",
    [
        (InvalidImageError, "INVALID_IMAGE", 400),
        (UnsupportedFormatError, "UNSUPPORTED_FORMAT", 422),
        (NoFoodDetectedError, "NO_FOOD_DETECTED", 400),
        (LLMError, "LLM_ERROR", 500),
        (RateLimitedError, "RATE_LIMITED", 429),
    ],
)
def test_each_error_has_code_and_status(exc_cls, expected_code, expected_status):
    err = exc_cls()
    assert err.error_code == expected_code
    assert err.http_status == expected_status
    assert isinstance(err, AppError)
    assert err.message  # non-empty default message


def test_custom_message_preserved():
    err = InvalidImageError("custom reason")
    assert err.message == "custom reason"
    assert str(err) == "custom reason"


def test_default_message_used_when_none_passed():
    err = InvalidImageError()
    assert "invalid" in err.message.lower()
