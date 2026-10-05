"""Tests for health and readiness endpoints."""

from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.db import get_db
from app.main import app


def test_health_check_returns_healthy():
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_readiness_check_requires_a_working_database(api):
    response = api["client"].get("/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_readiness_check_returns_503_when_database_is_unavailable():
    class FakeDatabase:
        def execute(self, _query):
            raise OperationalError("SELECT 1", {}, Exception("database unavailable"))

    def override_database():
        yield FakeDatabase()

    app.dependency_overrides[get_db] = override_database
    try:
        with TestClient(app) as client:
            response = client.get("/ready")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json() == {"detail": "Database unavailable"}
