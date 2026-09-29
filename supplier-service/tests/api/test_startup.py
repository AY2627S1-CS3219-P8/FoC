import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.main import create_app


def test_startup_rejects_invalid_configuration(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://test_user:test_password@localhost:5432/test_supplier")
    monkeypatch.setenv("USER_SERVICE_URL", "http://localhost:8000")
    monkeypatch.setenv("AUTH_TIMEOUT_SECONDS", "0")    # Enter an invalid timeout
    monkeypatch.setenv("LOG_LEVEL", "INFO")

    # Called without injected settings, startup loads them from the environment
    app = create_app()

    with pytest.raises(ValidationError) as exc_info:
        # Enter a TestClient context using app
        with TestClient(app):
            pass

    errors = exc_info.value.errors()

    # Assert that an error identifies auth_timeout_seconds
    assert any(
        error["loc"] == ("auth_timeout_seconds",)
        for error in errors
    )
