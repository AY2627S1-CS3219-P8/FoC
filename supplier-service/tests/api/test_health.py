# AI Assistance Disclosure:
# Tool: Codex (model: GPT-6), date: 2026-09-29
# Scope: Writing implementation code — add a test proving liveness does not connect to an unavailable database.
# Author review: Keith confirmed review of all affected readiness changes.
# Details: ../../ai/usage-log.md; ai-20260929-002

from fastapi.testclient import TestClient

def test_health_returns_healthy(client: TestClient):
    # Send a GET request to "/health" and store the response
    res = client.get("/health")

    # Assert that the response status code is 200
    assert res.status_code == 200

    # Assert that the response JSON equals {"status": "healthy"}
    assert res.json() == {"status": "healthy"}


def test_health_does_not_connect_to_database(client: TestClient, monkeypatch):
    from unittest.mock import MagicMock

    connect = MagicMock(side_effect=RuntimeError("Database unavailable"))
    monkeypatch.setattr(client.app.state.engine, "connect", connect)

    res = client.get("/health")

    assert res.status_code == 200
    assert res.json() == {"status": "healthy"}
    connect.assert_not_called()
