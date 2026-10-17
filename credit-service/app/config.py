"""Environment-backed configuration for the Credit Service."""

import os
from dataclasses import dataclass


def required_env(name: str) -> str:
    """Return a non-empty environment variable without logging its value."""

    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} must be set")
    return value


def _positive_int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer") from exc
    if value <= 0:
        raise RuntimeError(f"{name} must be positive")
    return value


def _positive_float_sequence_env(
    name: str, default: tuple[float, ...]
) -> tuple[float, ...]:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        values = tuple(float(item.strip()) for item in raw.split(","))
    except ValueError as exc:
        raise RuntimeError(
            f"{name} must be a comma-separated list of numbers"
        ) from exc
    if not values or any(value <= 0 for value in values):
        raise RuntimeError(f"{name} values must all be positive")
    return values


@dataclass(frozen=True)
class Settings:
    """Runtime settings shared by the API and its adapters."""

    database_url: str
    user_service_url: str
    initial_credit_allocation: int = 100
    retry_backoff_seconds: tuple[float, ...] = (0.5, 1.0, 2.0, 4.0)
    log_level: str = "INFO"

    @classmethod
    def from_env(cls) -> "Settings":
        database_url = required_env("DATABASE_URL")
        if not database_url.startswith("postgresql+psycopg://"):
            raise RuntimeError("DATABASE_URL must use the postgresql+psycopg scheme")
        return cls(
            database_url=database_url,
            user_service_url=required_env("USER_SERVICE_URL"),
            initial_credit_allocation=_positive_int_env(
                "INITIAL_CREDIT_ALLOCATION", 100
            ),
            retry_backoff_seconds=_positive_float_sequence_env(
                "CREDIT_RETRY_BACKOFF_SECONDS", (0.5, 1.0, 2.0, 4.0)
            ),
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        )
