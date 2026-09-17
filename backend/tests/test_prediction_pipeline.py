"""API integration tests for the real rainfall prediction pipeline endpoint."""

from datetime import date, timedelta
from unittest.mock import patch
import httpx
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.nasa_power_client import REQUIRED_NASA_POWER_PARAMS


def generate_mock_nasa_power_response(start_date: date, num_days: int) -> dict:
    """Generate representative raw NASA POWER API JSON payload."""
    date_strs = [
        (start_date + timedelta(days=i)).strftime("%Y%m%d")
        for i in range(num_days)
    ]
    params = {}
    for p in REQUIRED_NASA_POWER_PARAMS:
        p_dict = {}
        for idx, d_str in enumerate(date_strs):
            if p == "PRECTOTCORR":
                val = float(idx % 12)
            elif p == "T2M":
                val = 27.5
            elif p == "T2MDEW":
                val = 23.0
            elif p == "RH2M":
                val = 78.0
            elif p == "PS":
                val = 100.8
            elif p == "WS2M":
                val = 2.8
            elif p == "WS10M":
                val = 4.2
            elif p == "ALLSKY_SFC_SW_DWN":
                val = 16.5
            else:
                val = 1.0
            p_dict[d_str] = val
        params[p] = p_dict

    return {
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": [72.8777, 19.0760, 10.0],
        },
        "properties": {
            "parameter": params,
        },
    }


def test_predict_rainfall_pipeline_success():
    """Verify end-to-end rainfall prediction pipeline with mocked transport and real Model 1."""
    pred_date_str = "2024-02-15"
    pred_date = date(2024, 2, 15)
    start_obs = pred_date - timedelta(days=45)
    mock_payload = generate_mock_nasa_power_response(start_obs, 45)

    def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=mock_payload)

    mock_transport = httpx.MockTransport(mock_handler)
    mock_client = httpx.AsyncClient(transport=mock_transport)

    # Patch the AsyncClient inside WeatherObservationService's NasaPowerClient
    with patch("backend.app.services.nasa_power_client.httpx.AsyncClient", return_value=mock_client):
        with TestClient(app) as client:
            resp = client.post(
                "/api/v1/predict/rainfall",
                json={
                    "latitude": 19.0760,
                    "longitude": 72.8777,
                    "prediction_date": pred_date_str,
                    "location_name": "Mumbai",
                },
            )

            assert resp.status_code == 200, resp.text
            data = resp.json()

            assert data["status"] == "success"
            assert data["prediction_date"] == "2024-02-15"
            assert data["observation_date"] == "2024-02-14"
            assert data["coordinates"]["latitude"] == 19.0760
            assert data["coordinates"]["longitude"] == 72.8777
            assert data["location_name"] == "Mumbai"
            assert "heavy_rain_predicted" in data
            assert isinstance(data["heavy_rain_probability"], float)
            assert 0.0 <= data["heavy_rain_probability"] <= 1.0
            assert data["threshold"] == 0.81
            assert data["model_version"] == "heavy_rainfall_xgboost_v2"
            assert data["historical_records_used"] >= 30
            assert data["features_computed"] == 37
            assert "latest_weather" in data
            assert data["latest_weather"]["date"] == "2024-02-14"


def test_predict_rainfall_invalid_coordinates():
    """Verify endpoint rejects out-of-range latitude."""
    with TestClient(app) as client:
        resp = client.post(
            "/api/v1/predict/rainfall",
            json={
                "latitude": 195.0,  # Invalid
                "longitude": 72.8777,
                "prediction_date": "2024-02-15",
            },
        )
        assert resp.status_code == 422
        data = resp.json()
        assert data["success"] is False
        assert data["error"]["code"] == "VALIDATION_ERROR"


def test_predict_rainfall_invalid_date_format():
    """Verify endpoint rejects unparseable date strings."""
    with TestClient(app) as client:
        resp = client.post(
            "/api/v1/predict/rainfall",
            json={
                "latitude": 19.0760,
                "longitude": 72.8777,
                "prediction_date": "15-02-2024",  # Wrong format
            },
        )
        assert resp.status_code == 422
        data = resp.json()
        assert data["success"] is False


def test_predict_rainfall_upstream_api_500():
    """Verify endpoint maps NASA POWER 500 error to 502 Bad Gateway."""
    def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="Internal Server Error at NASA")

    mock_transport = httpx.MockTransport(mock_handler)
    mock_client = httpx.AsyncClient(transport=mock_transport)

    with patch("backend.app.services.nasa_power_client.httpx.AsyncClient", return_value=mock_client):
        with TestClient(app) as client:
            resp = client.post(
                "/api/v1/predict/rainfall",
                json={
                    "latitude": 19.0760,
                    "longitude": 72.8777,
                    "prediction_date": "2024-02-15",
                },
            )
            assert resp.status_code == 502
            data = resp.json()
            assert data["success"] is False
            assert data["error"]["code"] == "EXTERNAL_API_ERROR"


def test_predict_rainfall_insufficient_history_returns_422():
    """Verify endpoint returns 422 when upstream only has 10 days of data."""
    pred_date = date(2024, 2, 15)
    start_obs = pred_date - timedelta(days=10)  # Only 10 days
    mock_payload = generate_mock_nasa_power_response(start_obs, 10)

    def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=mock_payload)

    mock_transport = httpx.MockTransport(mock_handler)
    mock_client = httpx.AsyncClient(transport=mock_transport)

    with patch("backend.app.services.nasa_power_client.httpx.AsyncClient", return_value=mock_client):
        with TestClient(app) as client:
            resp = client.post(
                "/api/v1/predict/rainfall",
                json={
                    "latitude": 19.0760,
                    "longitude": 72.8777,
                    "prediction_date": "2024-02-15",
                },
            )
            assert resp.status_code == 422
            data = resp.json()
            assert data["success"] is False
            assert data["error"]["code"] == "INSUFFICIENT_HISTORICAL_DATA"
