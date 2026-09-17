"""Tests for system health endpoints."""

from starlette.testclient import TestClient


def test_direct_health_endpoint(client: TestClient):
    """Verify GET /health returns 200 and valid schema."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "healthy"
    assert data["environment"] == "testing"
    assert "version" in data
    assert "timestamp" in data
    assert "services" in data
    assert len(data["services"]) == 10

    # Ensure services are marked disconnected in foundation stage
    for svc in data["services"]:
        assert "service" in svc
        assert "status" in svc
        assert "is_connected" in svc
        assert svc["is_connected"] is False

    # Check model assets block
    assert "model_assets" in data
    assert "model1_heavy_rain_xgboost" in data["model_assets"]
    assert "model2_flood_unet" in data["model_assets"]


def test_api_v1_health_endpoint(client: TestClient):
    """Verify GET /api/v1/health returns 200 and matches direct endpoint structure."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert len(data["services"]) == 10


def test_root_docs_redirect(client: TestClient):
    """Verify GET / redirects to /docs."""
    response = client.get("/", follow_redirects=False)
    assert response.status_code in (307, 302)
    assert response.headers["location"] == "/docs"
