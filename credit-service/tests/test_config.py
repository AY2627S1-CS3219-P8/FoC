import pytest

from app.config import Settings


def base_environment(monkeypatch) -> None:
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql+psycopg://credit:test@credit-db/foc_credits"
    )
    monkeypatch.setenv("USER_SERVICE_URL", "http://user-service:8080")


def test_retry_schedule_is_configurable(monkeypatch) -> None:
    base_environment(monkeypatch)
    monkeypatch.setenv("CREDIT_RETRY_BACKOFF_SECONDS", "0.25, 1, 5")

    assert Settings.from_env().retry_backoff_seconds == (0.25, 1.0, 5.0)


@pytest.mark.parametrize("value", ["", "0,1", "one,2", "-1,2"])
def test_retry_schedule_rejects_invalid_values(monkeypatch, value: str) -> None:
    base_environment(monkeypatch)
    monkeypatch.setenv("CREDIT_RETRY_BACKOFF_SECONDS", value)

    with pytest.raises(RuntimeError):
        Settings.from_env()
