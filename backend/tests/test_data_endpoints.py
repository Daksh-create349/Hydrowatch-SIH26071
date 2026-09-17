"""API integration tests for /api/v1/data/nwp and /api/v1/data/radar endpoints."""

from unittest.mock import patch
import httpx
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.cache import cache
from backend.tests.test_nwp_service import create_mock_open_meteo_payload
from backend.tests.test_radar_service import generate_mock_radar_png


def test_api_nwp_endpoint_success():
    """Verify GET /api/v1/data/nwp returns 200 and valid schema."""
    mock_payload = create_mock_open_meteo_payload(24)

    def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=mock_payload)

    mock_transport = httpx.MockTransport(mock_handler)
    mock_client = httpx.AsyncClient(transport=mock_transport)

    cache.clear()
    with patch("backend.app.services.nwp_client.httpx.AsyncClient", return_value=mock_client):
        with TestClient(app) as client:
            resp = client.get("/api/v1/data/nwp?latitude=19.0760&longitude=72.8777&forecast_days=1")
            assert resp.status_code == 200, resp.text
            data = resp.json()

            assert data["status"] == "success"
            assert data["coordinates"]["latitude"] == 19.0760
            assert data["coordinates"]["longitude"] == 72.8777
            assert data["forecast_count"] == 24
            assert "summary" in data
            assert "forecasts" in data
            assert len(data["forecasts"]) == 24
            assert data["forecasts"][0]["surface_pressure_kpa"] > 0


def test_api_nwp_endpoint_invalid_latitude():
    """Verify endpoint rejects invalid out-of-range latitude."""
    with TestClient(app) as client:
        resp = client.get("/api/v1/data/nwp?latitude=119.0760&longitude=72.8777")
        assert resp.status_code == 422
        assert resp.json()["success"] is False


def test_api_nwp_endpoint_upstream_error():
    """Verify upstream 500 error maps to 502 Bad Gateway."""
    def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="NOAA Open-Meteo failure")

    mock_transport = httpx.MockTransport(mock_handler)
    mock_client = httpx.AsyncClient(transport=mock_transport)

    cache.clear()
    with patch("backend.app.services.nwp_client.httpx.AsyncClient", return_value=mock_client):
        with TestClient(app) as client:
            resp = client.get("/api/v1/data/nwp?latitude=19.0760&longitude=72.8777")
            assert resp.status_code == 502
            assert resp.json()["success"] is False
            assert resp.json()["error"]["code"] == "EXTERNAL_API_ERROR"


def test_api_radar_endpoint_success():
    """Verify GET /api/v1/data/radar returns 200 and valid schema."""
    mock_catalog = {
        "host": "https://tilecache.rainviewer.com",
        "radar": {
            "past": [
                {"time": 1789564000, "path": "/v2/radar/frame1"},
                {"time": 1789564600, "path": "/v2/radar/frame2"},
            ]
        },
    }
    png_bytes = generate_mock_radar_png(has_echoes=True)

    def mock_handler(request: httpx.Request) -> httpx.Response:
        if "weather-maps.json" in str(request.url):
            return httpx.Response(200, json=mock_catalog)
        return httpx.Response(200, content=png_bytes, headers={"Content-Type": "image/png"})

    mock_transport = httpx.MockTransport(mock_handler)
    real_async_client_cls = httpx.AsyncClient

    cache.clear()
    with patch(
        "backend.app.services.radar_client.httpx.AsyncClient",
        side_effect=lambda **kwargs: real_async_client_cls(transport=mock_transport),
    ):
        with TestClient(app) as client:
            resp = client.get("/api/v1/data/radar?latitude=19.0760&longitude=72.8777&zoom=6")
            assert resp.status_code == 200, resp.text
            data = resp.json()

            assert data["status"] == "success"
            assert data["source"] == "RainViewer Global Doppler Radar Composite"
            assert "latest_scan" in data
            assert data["latest_scan"]["zoom_level"] == 6
            assert data["latest_scan"]["active_echo_pixels"] > 0
            assert data["latest_scan"]["bounding_box"]["min_lat"] <= 19.0760 <= data["latest_scan"]["bounding_box"]["max_lat"]


def test_api_radar_endpoint_invalid_longitude():
    """Verify endpoint rejects invalid out-of-range longitude."""
    with TestClient(app) as client:
        resp = client.get("/api/v1/data/radar?latitude=19.0760&longitude=-272.8777")
        assert resp.status_code == 422
        assert resp.json()["success"] is False


def test_api_radar_endpoint_upstream_error():
    """Verify upstream catalog failure maps to 502 Bad Gateway."""
    def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="RainViewer API down")

    mock_transport = httpx.MockTransport(mock_handler)
    mock_client = httpx.AsyncClient(transport=mock_transport)

    cache.clear()
    with patch("backend.app.services.radar_client.httpx.AsyncClient", return_value=mock_client):
        with TestClient(app) as client:
            resp = client.get("/api/v1/data/radar?latitude=19.0760&longitude=72.8777")
            assert resp.status_code == 502
            assert resp.json()["success"] is False
            assert resp.json()["error"]["code"] == "EXTERNAL_API_ERROR"
