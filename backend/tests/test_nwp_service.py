"""Unit tests for Open-Meteo NOAA GFS NWP client and service."""

from unittest.mock import patch
import httpx
import pytest

from backend.app.core.errors import ExternalApiError, WeatherObservationValidationError
from backend.app.schemas.common import Coordinates
from backend.app.services.cache import cache
from backend.app.services.nwp_client import OpenMeteoNwpClient
from backend.app.services.nwp_service import NWPService


def create_mock_open_meteo_payload(num_hours: int = 24) -> dict:
    """Generate representative raw Open-Meteo GFS JSON response."""
    return {
        "latitude": 19.0760,
        "longitude": 72.8777,
        "elevation": 14.0,
        "hourly_units": {
            "time": "iso8601",
            "precipitation": "mm",
            "temperature_2m": "°C",
            "relative_humidity_2m": "%",
            "dew_point_2m": "°C",
            "surface_pressure": "hPa",
            "wind_speed_10m": "m/s",
            "cape": "J/kg",
        },
        "hourly": {
            "time": [f"2026-09-17T{h:02d}:00" for h in range(num_hours)],
            "precipitation": [round(float(h % 5) * 1.5, 2) for h in range(num_hours)],
            "temperature_2m": [round(26.0 + (h % 6) * 0.5, 1) for h in range(num_hours)],
            "relative_humidity_2m": [round(75.0 + (h % 10), 1) for h in range(num_hours)],
            "dew_point_2m": [round(22.0 + (h % 3) * 0.4, 1) for h in range(num_hours)],
            "surface_pressure": [round(1008.0 - (h % 4) * 0.5, 1) for h in range(num_hours)],
            "wind_speed_10m": [round(3.5 + (h % 4) * 0.8, 2) for h in range(num_hours)],
            "cape": [round(250.0 + (h % 5) * 100.0, 1) for h in range(num_hours)],
        },
    }


def test_nwp_parser_valid():
    """Verify parser extracts and structures hourly NWP forecast and summary."""
    client = OpenMeteoNwpClient()
    coords = Coordinates(latitude=19.0760, longitude=72.8777)
    payload = create_mock_open_meteo_payload(24)

    resp = client.parse_response(payload, coords)
    assert resp.status == "success"
    assert resp.model_name == "gfs_seamless"
    assert resp.forecast_count == 24
    assert resp.forecast_horizon_hours == 24
    assert resp.elevation_m == 14.0

    # Test unit conversions
    first = resp.forecasts[0]
    assert first.lead_hours == 0
    assert first.surface_pressure_hpa == 1008.0
    assert first.surface_pressure_kpa == 100.8  # hPa / 10.0
    assert first.precipitation_mm_hr == 0.0
    assert first.temperature_2m_c == 26.0
    assert first.cape_j_kg == 250.0

    # Test summary statistics
    assert resp.summary.total_precipitation_mm > 0.0
    assert resp.summary.max_hourly_precipitation_mm_hr >= 0.0
    assert resp.summary.max_cape_j_kg is not None
    assert resp.summary.max_cape_j_kg >= 250.0


def test_nwp_parser_missing_variable():
    """Verify parser rejects payload missing required atmospheric variables."""
    client = OpenMeteoNwpClient()
    coords = Coordinates(latitude=19.0760, longitude=72.8777)
    payload = create_mock_open_meteo_payload(12)
    del payload["hourly"]["wind_speed_10m"]

    with pytest.raises(WeatherObservationValidationError) as exc:
        client.parse_response(payload, coords)
    assert "wind_speed_10m" in str(exc.value)


def test_nwp_parser_non_finite_value():
    """Verify parser rejects NaN or infinite forecast numbers."""
    client = OpenMeteoNwpClient()
    coords = Coordinates(latitude=19.0760, longitude=72.8777)
    payload = create_mock_open_meteo_payload(10)
    payload["hourly"]["temperature_2m"][3] = float("nan")

    with pytest.raises(WeatherObservationValidationError) as exc:
        client.parse_response(payload, coords)
    assert "Non-finite" in str(exc.value)


@pytest.mark.anyio
async def test_nwp_client_http_500_raises_external_error():
    """Verify upstream 500 error raises ExternalApiError with status 502."""
    def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="Internal Server Error at NOAA")

    transport = httpx.MockTransport(mock_handler)
    client = OpenMeteoNwpClient(http_client=httpx.AsyncClient(transport=transport))

    with pytest.raises(ExternalApiError) as exc:
        await client.fetch_point_forecast(Coordinates(latitude=19.0760, longitude=72.8777))
    assert exc.value.status_code == 502
    assert "OPEN_METEO_GFS" in exc.value.code or "EXTERNAL_API_ERROR" in exc.value.code


@pytest.mark.anyio
async def test_nwp_service_cache_mechanism():
    """Verify NWPService caches responses to avoid repeated network calls."""
    payload = create_mock_open_meteo_payload(12)
    call_count = 0

    def mock_handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(200, json=payload)

    transport = httpx.MockTransport(mock_handler)
    async_client = httpx.AsyncClient(transport=transport)
    nwp_client = OpenMeteoNwpClient(http_client=async_client)
    service = NWPService(nwp_client=nwp_client)

    cache.clear()
    coords = Coordinates(latitude=19.0760, longitude=72.8777)

    # First call: hits transport
    res1 = await service.fetch_point_forecast(coords, forecast_days=1)
    assert call_count == 1
    assert res1.forecast_count == 12

    # Second call: served from cache
    res2 = await service.fetch_point_forecast(coords, forecast_days=1)
    assert call_count == 1
    assert res2.forecast_count == 12
