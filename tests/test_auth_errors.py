from app.errors import DatabaseError, UnauthorizedError


def test_unauthorized_error_defaults():
    exc = UnauthorizedError()
    assert exc.error_code == "UNAUTHORIZED"
    assert exc.http_status == 401
    assert "token" in exc.message.lower()


def test_unauthorized_error_custom_message():
    exc = UnauthorizedError("Token has expired.")
    assert exc.message == "Token has expired."
    assert exc.error_code == "UNAUTHORIZED"
    assert exc.http_status == 401


def test_database_error_defaults():
    exc = DatabaseError()
    assert exc.error_code == "DATABASE_ERROR"
    assert exc.http_status == 500
