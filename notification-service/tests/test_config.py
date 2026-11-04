# AI Assistance Disclosure:
# Tool: Claude Code (model: claude-opus-5-5), date: 2026-11-03
# Scope: Writing implementation code — write tests for valid, missing, empty, whitespace-only, and wrong-scheme DATABASE_URL values, LOG_LEVEL validation, API startup failure, and non-zero worker exit.
# Author review: Keith confirmed review of all affected changes.
# Details: notification-service/ai/usage-log.md; ai-20261103-001

import os
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import ConfigError, Settings
from app.main import create_app

SERVICE_ROOT = Path(__file__).resolve().parents[1]
VALID_URL = "postgresql+psycopg://notification@notification-db:5432/foc_notifications"


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", VALID_URL)
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    return monkeypatch


def test_valid_environment_loads(env) -> None:
    settings = Settings.from_env()

    assert settings.database_url == VALID_URL
    assert settings.log_level == "INFO"


def test_log_level_is_normalised(env) -> None:
    env.setenv("LOG_LEVEL", "debug")

    assert Settings.from_env().log_level == "DEBUG"


@pytest.mark.parametrize("value", [None, "", "   "])
def test_missing_or_empty_database_url_is_rejected(env, value) -> None:
    if value is None:
        env.delenv("DATABASE_URL")
    else:
        env.setenv("DATABASE_URL", value)

    with pytest.raises(ConfigError, match="DATABASE_URL must be set"):
        Settings.from_env()


@pytest.mark.parametrize(
    "value",
    ["postgresql://u@h/db", "sqlite:///x.db", "not-a-url"],
)
def test_database_url_with_wrong_scheme_is_rejected(env, value: str) -> None:
    env.setenv("DATABASE_URL", value)

    with pytest.raises(ConfigError, match="DATABASE_URL"):
        Settings.from_env()


def test_invalid_log_level_is_rejected(env) -> None:
    env.setenv("LOG_LEVEL", "LOUD")

    with pytest.raises(ConfigError, match="LOG_LEVEL"):
        Settings.from_env()


def test_api_startup_fails_without_database_url(env) -> None:
    env.delenv("DATABASE_URL")

    with pytest.raises(ConfigError, match="DATABASE_URL must be set"):
        with TestClient(create_app()):
            pass


def _run_module(module: str, database_url: str) -> subprocess.CompletedProcess:
    environment = {
        key: value for key, value in os.environ.items() if key != "DATABASE_URL"
    }
    environment["DATABASE_URL"] = database_url
    return subprocess.run(
        [sys.executable, "-m", module],
        cwd=SERVICE_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
    )


@pytest.mark.parametrize("database_url", ["", "mysql://u@h/db"])
def test_worker_exits_non_zero_on_invalid_configuration(database_url: str) -> None:
    result = _run_module("app.worker", database_url)

    assert result.returncode != 0
    assert "DATABASE_URL" in result.stderr
