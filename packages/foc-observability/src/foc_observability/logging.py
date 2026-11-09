"""Structured stdout logging for FoC application processes."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

from .context import get_context


_DEFAULT_LEVEL = "INFO"
_DEFAULT_ENVIRONMENT = "development"
_STANDARD_RECORD_FIELDS = frozenset(
    {
        "name",
        "msg",
        "args",
        "levelname",
        "levelno",
        "pathname",
        "filename",
        "module",
        "exc_info",
        "exc_text",
        "stack_info",
        "lineno",
        "funcName",
        "created",
        "msecs",
        "relativeCreated",
        "thread",
        "threadName",
        "processName",
        "process",
        "taskName",
        "message",
        "asctime",
        "event",
        "fields",
    }
)


class _JsonStreamHandler(logging.StreamHandler):
    """Marker type used to replace only handlers owned by this package."""

    foc_observability_handler = True


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

        # Preserve existing call sites that use logger calls such as
        # ``extra={"attempt": attempt}`` while they migrate to the explicit
        # ``fields`` mapping.
        legacy_fields = {
            key: value
            for key, value in record.__dict__.items()
            if key not in _STANDARD_RECORD_FIELDS and not key.startswith("_")
        }
        payload.update(legacy_fields)
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
    more than once is safe. Existing non-FoC root handlers are preserved so
    test capture handlers and embedding applications continue to work.
    """

    if not service or any(character.isspace() for character in service):
        raise ValueError("service must be a non-empty name without whitespace")

    active_environment = environment or os.getenv(
        "APP_ENV", _DEFAULT_ENVIRONMENT
    )
    formatter = JsonFormatter(
        service=service,
        environment=active_environment,
    )
    active_level = _level_name(level)

    root_logger = logging.getLogger()
    root_logger.setLevel(active_level)
    _replace_owned_handlers(root_logger, formatter)

    # Uvicorn otherwise keeps its own text handlers and can emit duplicate
    # records after application startup configuration. RequestContextMiddleware
    # emits the canonical structured access event, so suppress Uvicorn's
    # opaque duplicate access line.
    for logger_name in ("uvicorn", "uvicorn.error"):
        server_logger = logging.getLogger(logger_name)
        _remove_owned_handlers(server_logger)
        for handler in list(server_logger.handlers):
            server_logger.removeHandler(handler)
            handler.close()
        server_logger.addHandler(_new_handler(formatter))
        server_logger.setLevel(active_level)
        server_logger.propagate = False

    access_logger = logging.getLogger("uvicorn.access")
    _remove_owned_handlers(access_logger)
    for handler in list(access_logger.handlers):
        access_logger.removeHandler(handler)
        handler.close()
    access_logger.propagate = False
    access_logger.disabled = True

    # SQL statements and connection details should stay out of normal
    # production logs unless explicitly enabled locally.
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


def _new_handler(formatter: JsonFormatter) -> _JsonStreamHandler:
    handler = _JsonStreamHandler()
    handler.setLevel(logging.NOTSET)
    handler.setFormatter(formatter)
    return handler


def _remove_owned_handlers(logger: logging.Logger) -> None:
    for handler in list(logger.handlers):
        if getattr(handler, "foc_observability_handler", False):
            logger.removeHandler(handler)
            handler.close()


def _replace_owned_handlers(
    logger: logging.Logger, formatter: JsonFormatter
) -> None:
    _remove_owned_handlers(logger)
    logger.addHandler(_new_handler(formatter))


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
