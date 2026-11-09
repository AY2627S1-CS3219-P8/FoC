"""Structured stdout logging for FoC application processes."""

from __future__ import annotations

import json
import logging
import logging.config
import os
from datetime import datetime, timezone
from typing import Any

from .context import get_context


_DEFAULT_LEVEL = "INFO"
_DEFAULT_ENVIRONMENT = "development"


class JsonFormatter(logging.Formatter):
    """Render one log record as one JSON object.

    Application fields should be supplied under ``extra={"fields": {...}}``.
    Keeping application data in a dedicated mapping avoids collisions with
    Python's reserved ``LogRecord`` attributes.
    """

    def __init__(
        self,
        *,
        service: str,
        environment: str,
    ) -> None:
        super().__init__()
        self.service = service
        self.environment = environment

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(
                record.created, timezone.utc
            ).isoformat().replace("+00:00", "Z"),
            "level": record.levelname,
            "service": self.service,
            "environment": self.environment,
            "logger": record.name,
            "event": getattr(record, "event", record.getMessage()),
        }

        context = get_context()
        fields = getattr(record, "fields", {})
        if fields:
            if not isinstance(fields, dict):
                raise TypeError("logging extra['fields'] must be a dictionary")
            payload.update(fields)
        payload.update(context)

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, default=str, ensure_ascii=True)


def _level_name(level: str | int | None) -> str:
    if level is None:
        level = os.getenv("LOG_LEVEL", _DEFAULT_LEVEL)
    if isinstance(level, int):
        return logging.getLevelName(level)
    normalized = level.upper()
    if normalized not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
        raise ValueError(f"Unsupported log level: {level!r}")
    return normalized


def configure_logging(
    service: str,
    *,
    environment: str | None = None,
    level: str | int | None = None,
) -> None:
    """Configure the root logger and Uvicorn loggers for one process.

    Logs go to stdout so the container runtime can collect them. Calling this
    more than once is safe and replaces handlers installed by a process host.
    """

    if not service or any(character.isspace() for character in service):
        raise ValueError("service must be a non-empty name without whitespace")

    active_environment = environment or os.getenv(
        "APP_ENV", _DEFAULT_ENVIRONMENT
    )
    formatter = {
        "()": "foc_observability.logging.JsonFormatter",
        "service": service,
        "environment": active_environment,
    }
    handler = {
        "class": "logging.StreamHandler",
        "level": "NOTSET",
        "formatter": "json",
        "stream": "ext://sys.stdout",
    }

    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {"json": formatter},
            "handlers": {"stdout": handler},
            "root": {
                "level": _level_name(level),
                "handlers": ["stdout"],
            },
            "loggers": {
                # Uvicorn otherwise keeps its own text handlers and can emit
                # duplicate records after application startup configuration.
                "uvicorn": {
                    "level": "INFO",
                    "handlers": ["stdout"],
                    "propagate": False,
                },
                "uvicorn.access": {
                    "level": "INFO",
                    "handlers": ["stdout"],
                    "propagate": False,
                },
                "uvicorn.error": {
                    "level": "INFO",
                    "handlers": ["stdout"],
                    "propagate": False,
                },
                # SQL statements and connection details should stay out of
                # normal production logs unless explicitly enabled locally.
                "sqlalchemy.engine": {
                    "level": "WARNING",
                    "handlers": [],
                    "propagate": True,
                },
            },
        }
    )


def log_event(
    logger: logging.Logger,
    level: int,
    event: str,
    *,
    exc_info: Any = None,
    **fields: Any,
) -> None:
    """Write a named event with collision-safe structured fields."""

    if not event or any(character.isspace() for character in event):
        raise ValueError("event must be a non-empty name without whitespace")
    logger.log(
        level,
        event,
        extra={"event": event, "fields": fields},
        exc_info=exc_info,
    )
