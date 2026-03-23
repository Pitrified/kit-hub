"""Tests for health check endpoints."""

from fastapi.testclient import TestClient


def test_health_check(client: TestClient) -> None:
    """Test basic health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data
    assert "timestamp" in data


def test_readiness_check(client: TestClient) -> None:
    """Test readiness probe endpoint."""
    response = client.get("/health/ready")
    assert response.status_code == 200

    data = response.json()
    assert "status" in data
    assert "checks" in data
    assert isinstance(data["checks"], dict)


def test_liveness_check(client: TestClient) -> None:
    """Test liveness probe endpoint."""
    response = client.get("/health/live")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "alive"
