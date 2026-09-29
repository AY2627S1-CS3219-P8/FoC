from fastapi.testclient import TestClient

def test_health_returns_healthy(client: TestClient):
    # Send a GET request to "/health" and store the response
    res = client.get("/health")

    # Assert that the response status code is 200
    assert res.status_code == 200

    # Assert that the response JSON equals {"status": "healthy"}
    assert res.json() == {"status": "healthy"}
