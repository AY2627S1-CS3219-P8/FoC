"""Tests for the User Service health endpoint."""

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health_check():
    """The health endpoint reports that the service is healthy."""

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}
