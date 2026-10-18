import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from unittest.mock import MagicMock
from app.config import Settings
from app.main import create_app


def test_startup_rejects_invalid_configuration(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://test_user:test_password@localhost:5432/test_supplier")
    monkeypatch.setenv("USER_SERVICE_URL", "http://localhost:8000")
    monkeypatch.setenv("AUTH_TIMEOUT_SECONDS", "0")    
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

def test_startup_initializes_database_and_shutdown_disposes_engine(
    monkeypatch: pytest.MonkeyPatch,
    settings: Settings,
):
    engine = MagicMock()
    session_factory = MagicMock()
    build_engine = MagicMock(return_value=engine)
    build_session_factory = MagicMock(return_value=session_factory)

    monkeypatch.setattr("app.main.create_db_engine", build_engine)
    monkeypatch.setattr(
        "app.main.create_session_factory",
        build_session_factory,
    )

    app = create_app(settings)

    with TestClient(app):
        # Assert app.state.settings is settings
        assert app.state.settings is settings

        # Verify build_engine was called once with settings
        build_engine.assert_called_once_with(settings)

        # Verify build_session_factory was called once with engine
        build_session_factory.assert_called_once_with(engine)

        # Assert app.state.engine is engine
        assert app.state.engine is engine

        # Assert app.state.session_factory is session_factory
        assert app.state.session_factory is session_factory

        # Verify engine.dispose has not been called yet
        engine.dispose.assert_not_called()

    # Verify engine.dispose was called once without arguments
    engine.dispose.assert_called_once_with()
