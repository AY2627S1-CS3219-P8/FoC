import pytest

from app.config import Settings
from pydantic import ValidationError


def test_settings_defaults(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("AUTH_TIMEOUT_SECONDS", raising=False)
    monkeypatch.delenv("LOG_LEVEL", raising=False)

    settings = Settings(
        database_url="postgresql://test_user:test_password@localhost:5432/test_supplier",
        user_service_url="http://localhost:8000",
    )

    # Assert that auth_timeout_seconds has its default value
    assert settings.auth_timeout_seconds == 3.0

    # Assert that log_level has its default value
    assert settings.log_level == "INFO"

def test_settings_requires_database_url(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)

    # Exclude the required database_url field
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            user_service_url="http://localhost:8000",
            auth_timeout_seconds=3.0,
            log_level="INFO",
        )

    errors = exc_info.value.errors()

    # Check loc (field) and type (validation problem), verify that it was the missing database_url that is causing the error
    assert any(
        error["loc"] == ("database_url",) and error["type"] == "missing"
        for error in errors
    )

def test_settings_requires_user_service_url(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("USER_SERVICE_URL", raising=False)

    # Exclude the required user_service_url field
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            database_url="postgresql://test_user:test_password@localhost:5432/test_supplier",
            auth_timeout_seconds=3.0,
            log_level="INFO",
        )

    errors = exc_info.value.errors()

    # Check loc (field) and type (validation problem), verify that it was the missing user_service_url that is causing the error
    assert any(
        error["loc"] == ("user_service_url",) and error["type"] == "missing"
        for error in errors
    )

@pytest.mark.parametrize(
    "invalid_timeout",
    [0, -1, float("inf"), float("-inf"), float("nan")],
    ids=["zero", "negative", "infinity", "negative-infinity", "nan"],
)
def test_settings_rejects_invalid_auth_timeout(invalid_timeout: float):
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            database_url="postgresql://test_user:test_password@localhost:5432/test_supplier",
            user_service_url="http://localhost:8000",
            auth_timeout_seconds=invalid_timeout,
            log_level="INFO",
        )

    errors = exc_info.value.errors()

    # Assert that an error identifies auth_timeout_seconds
    assert any(
        # Checking just the field is sufficient since each case can produce different error types
        error["loc"] == ("auth_timeout_seconds",)
        for error in errors
    )

@pytest.mark.parametrize(
    ("field_name", "invalid_url"),
    [
        ("database_url", "not-a-url"),
        ("database_url", "https://localhost/supplier"),
        ("user_service_url", "not-a-url"),
        ("user_service_url", "ftp://localhost"),
    ],
    ids=[
        "malformed-database-url",
        "unsupported-database-scheme",
        "malformed-user-service-url",
        "unsupported-user-service-scheme",
    ],
)
# Test whether text that is not URL and unsupported schemas are caught
def test_settings_rejects_invalid_urls(field_name: str, invalid_url: str):
    values = {
        "database_url": "postgresql://test_user:test_password@localhost:5432/test_supplier",
        "user_service_url": "http://localhost:8000",
        "auth_timeout_seconds": 3.0,
        "log_level": "INFO",
    }

    # Replace the entry named field_name with invalid_url
    values[field_name] = invalid_url

    with pytest.raises(ValidationError) as exc_info:
        Settings(**values)

    errors = exc_info.value.errors()

    # Assert that an error identifies the field being tested
    assert any(
        error["loc"] == (field_name,)
        for error in errors
    )

@pytest.mark.parametrize(
    "invalid_log_level",
    ["TRACE", "info", ""],
    ids=["unsupported-level", "lowercase-level", "empty-level"],
)
# Test that unsupported log levels are rejected
def test_settings_rejects_invalid_log_level(invalid_log_level: str):
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            database_url="postgresql://test_user:test_password@localhost:5432/test_supplier",
            user_service_url="http://localhost:8000",
            auth_timeout_seconds=3.0,
            log_level=invalid_log_level,
        )

    errors = exc_info.value.errors()

    # TODO: Assert that an error identifies log_level.
    assert any(
        error["loc"] == ("log_level",)
        for error in errors
    )
