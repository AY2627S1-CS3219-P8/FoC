# AI Assistance Disclosure:
# Tool: Claude Code (model: claude-opus-5-5), date: 2026-11-03
# Scope: Writing implementation code — write environment-backed settings that treat empty variables as missing, validate the DATABASE_URL scheme and LOG_LEVEL, and raise errors naming the variable.
# Author review: Keith confirmed review of all affected changes.
# Details: notification-service/ai/usage-log.md; ai-20261103-001
# Tool: Claude Code (model: claude-opus-5-5), date: 2026-11-04
# Scope: Writing implementation code — add worker-only settings for the Kafka bootstrap servers and a required timezone-aware NOTIFICATIONS_START_AT (ai-20261104-003).
# Author review: Keith confirmed verification, with 551 tests passed on the Pytest suite (ai-20261104-003).
# Details: notification-service/ai/usage-log.md; ai-20261104-003

"""Environment-backed configuration for the Notification Service."""

import logging
import os
from dataclasses import dataclass
from datetime import datetime

DATABASE_URL_SCHEME = "postgresql+psycopg://"
LOG_LEVELS = ("CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG")


class ConfigError(RuntimeError):
    """Raised when a required environment variable is missing or invalid."""


def required_env(name: str) -> str:
    """Return a non-empty environment variable without logging its value."""

    value = os.getenv(name, "").strip()
    if not value:
        raise ConfigError(f"{name} must be set")
    return value


def _log_level_env(name: str, default: str) -> str:
    value = os.getenv(name, "").strip().upper() or default
    if value not in LOG_LEVELS:
        raise ConfigError(f"{name} must be one of: {', '.join(LOG_LEVELS)}")
    return value


@dataclass(frozen=True)
class Settings:
    """Runtime settings shared by the API and the worker."""

    database_url: str
    log_level: str = "INFO"

    @classmethod
    def from_env(cls) -> "Settings":
        database_url = required_env("DATABASE_URL")
        if not database_url.startswith(DATABASE_URL_SCHEME):
            raise ConfigError("DATABASE_URL must use the postgresql+psycopg scheme")
        return cls(
            database_url=database_url,
            log_level=_log_level_env("LOG_LEVEL", "INFO"),
        )


def _aware_datetime_env(name: str) -> datetime:
    value = required_env(name)
    message = f"{name} must be an ISO-8601 date and time with a timezone"
    # fromisoformat accepts any character as the date/time separator.
    if "T" not in value:
        raise ConfigError(message)
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        raise ConfigError(message) from None
    if parsed.utcoffset() is None:
        raise ConfigError(message)
    return parsed


@dataclass(frozen=True, kw_only=True)
class WorkerSettings(Settings):
    """Settings only the worker needs, so the API does not have to supply them."""

    kafka_bootstrap_servers: str
    notifications_start_at: datetime

    @classmethod
    def from_env(cls) -> "WorkerSettings":
        shared = Settings.from_env()
        return cls(
            database_url=shared.database_url,
            log_level=shared.log_level,
            kafka_bootstrap_servers=required_env("KAFKA_BOOTSTRAP_SERVERS"),
            notifications_start_at=_aware_datetime_env("NOTIFICATIONS_START_AT"),
        )


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
