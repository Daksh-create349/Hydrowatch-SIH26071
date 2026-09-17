"""Integration tests for POST /api/v1/predict/risk pipeline endpoint."""

from unittest.mock import AsyncMock, patch
import pytest
from fastapi.testclient import TestClient

from backend.app.core.errors import ServiceUnavailableError
from backend.app.main import app
from backend.app.schemas.common import Coordinates, GeoBoundingBox
from backend.app.schemas.nwp import NWPForecastItem, NWPForecastSummary, NWPPointForecastResponse
from backend.app.schemas.prediction import InundationPipelineResponse, RainfallPipelineResponse
from backend.app.schemas.radar import RadarDataResponse, RadarTileReflectivity

client = TestClient(app)


def mock_rainfall_response():
    return RainfallPipelineResponse(
        status="success",
        prediction_date="2026-09-16",
        observation_date="2026-09-15",
        coordinates=Coordinates(latitude=19.0760, longitude=72.8777),
        location_name="Mumbai",
        heavy_rain_predicted=False,
        heavy_rain_probability=0.25,
        threshold=0.81,
        model_version="heavy_rainfall_xgboost_v2",
        historical_records_used=30,
        features_computed=37,
        latest_weather={"PRECTOTCORR": 14.5, "T2M": 28.0},
    )


def mock_nwp_response():
    return NWPPointForecastResponse(
        status="success",
        source="Open-Meteo GFS (NOAA 0.25° Seamless)",
        model_name="GFS_0.25",
        coordinates=Coordinates(latitude=19.0760, longitude=72.8777),
        generated_at="2026-09-16T10:00:00Z",
        forecast_horizon_hours=24,
        forecast_count=24,
        units={"precipitation": "mm"},
        summary=NWPForecastSummary(
            total_precipitation_mm=30.0,
            max_hourly_precipitation_mm_hr=7.5,
            min_temperature_c=24.0,
            max_temperature_c=31.0,
            max_wind_speed_ms=8.0,
            max_cape_j_kg=550.0,
        ),
        forecasts=[
            NWPForecastItem(
                valid_time="2026-09-16T11:00:00Z",
                lead_hours=1,
                precipitation_mm_hr=1.5,
                temperature_2m_c=28.0,
                relative_humidity_pct=82.0,
                dew_point_2m_c=24.0,
                surface_pressure_hpa=1010.0,
                surface_pressure_kpa=101.0,
                wind_speed_10m_ms=5.0,
                cape_j_kg=350.0,
            )
        ],
    )


def mock_radar_response():
    return RadarDataResponse(
        status="success",
        source="RainViewer Global Doppler Radar Composite",
        latest_scan=RadarTileReflectivity(
            source="RainViewer Global Doppler Radar Composite",
            radar_product="DWR_MAXZ_COMPOSITE",
            timestamp_iso="2026-09-16T10:00:00Z",
            unix_timestamp=1789552800,
            requested_coordinates=Coordinates(latitude=19.0760, longitude=72.8777),
            bounding_box=GeoBoundingBox(min_lat=18.0, max_lat=20.0, min_lon=71.0, max_lon=73.0),
            zoom_level=6,
            tile_x=47,
            tile_y=28,
            dimensions=[256, 256],
            total_tile_pixels=65536,
            active_echo_pixels=1500,
            echo_coverage_pct=2.29,
            max_reflectivity_dbz=28.5,
            mean_reflectivity_dbz=16.0,
            estimated_max_rain_rate_mm_hr=2.1,
            tile_url="https://tilecache.rainviewer.com/v2/radar/1789552800/256/6/47/28/2/1_1.png",
        ),
        available_frames_count=13,
    )


def mock_inundation_response():
    return InundationPipelineResponse(
        status="success",
        requested_location=Coordinates(latitude=19.0760, longitude=72.8777),
        location_name="Mumbai",
        selected_scene={
            "scene_id": "S2A_MSIL2A_TEST",
            "acquisition_datetime": "2026-09-16T05:00:00Z",
            "cloud_coverage_percentage": 10.0,
        },
        model_version="flood_unet_sentinel2_6band",
        threshold=0.5,
        grid_resolution_m=10.0,
        raster_dimensions=[512, 512],
        valid_area_sq_km=26.2,
        flooded_area_sq_km=1.2,
        flooded_percentage=4.58,
        polygon_count=5,
        geojson={"type": "FeatureCollection", "features": []},
    )


@patch("backend.app.services.weather_service.WeatherObservationService.predict_rainfall")
@patch("backend.app.services.nwp_service.NWPService.fetch_point_forecast")
@patch("backend.app.services.radar_service.RadarService.fetch_radar_composite")
@patch("backend.app.services.satellite_imagery_service.SatelliteImageryService.predict_inundation")
def test_risk_endpoint_full_evidence_success(mock_sat, mock_radar, mock_nwp, mock_rainfall):
    mock_rainfall.return_value = mock_rainfall_response()
    mock_nwp.return_value = mock_nwp_response()
    mock_radar.return_value = mock_radar_response()
    mock_sat.return_value = mock_inundation_response()

    payload = {
        "latitude": 19.0760,
        "longitude": 72.8777,
        "prediction_date": "2026-09-16",
        "nwp_horizon_hours": 24,
        "satellite_max_cloud": 20.0,
        "location_name": "Mumbai Test Site",
    }

    resp = client.post("/api/v1/predict/risk", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    assert data["status"] == "success"
    assert data["requested_location"]["latitude"] == 19.0760
    assert data["requested_location"]["longitude"] == 72.8777
    assert data["location_name"] == "Mumbai Test Site"

    # Fusion metadata
    assert data["fusion"]["policy_applied"] == "FULL_EVIDENCE"
    assert len(data["fusion"]["available_sources"]) == 4
    assert len(data["fusion"]["unavailable_sources"]) == 0

    # Risk detail
    assert 0.0 <= data["risk"]["score"] <= 1.0
    assert data["risk"]["level"] in ["LOW", "MODERATE", "HIGH", "EXTREME"]

    # Explanations
    assert len(data["explanations"]) == 4

    # Prototype warning candidate
    assert "NOT AN OFFICIAL IMD GOVERNMENT WEATHER WARNING" in data["prototype_warning_assessment"]["disclaimer"]


@patch("backend.app.services.weather_service.WeatherObservationService.predict_rainfall")
@patch("backend.app.services.nwp_service.NWPService.fetch_point_forecast")
@patch("backend.app.services.radar_service.RadarService.fetch_radar_composite")
@patch("backend.app.services.satellite_imagery_service.SatelliteImageryService.predict_inundation")
def test_risk_endpoint_partial_evidence_radar_missing(mock_sat, mock_radar, mock_nwp, mock_rainfall):
    mock_rainfall.return_value = mock_rainfall_response()
    mock_nwp.return_value = mock_nwp_response()
    mock_radar.side_effect = ServiceUnavailableError("Radar tile stream offline")
    mock_sat.return_value = mock_inundation_response()

    payload = {
        "latitude": 19.0760,
        "longitude": 72.8777,
        "prediction_date": "2026-09-16",
    }

    resp = client.post("/api/v1/predict/risk", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    # Policy should reflect partial evidence
    assert data["fusion"]["policy_applied"] == "PARTIAL_EVIDENCE"
    assert "radar_nowcast" in data["fusion"]["unavailable_sources"]
    assert len(data["fusion"]["available_sources"]) == 3

    # Effective weight of radar is 0.0, rest renormalized to sum to 1.0
    assert data["fusion"]["effective_weights"]["radar_nowcast"] == 0.0
    total_weights = sum(data["fusion"]["effective_weights"].values())
    assert pytest.approx(total_weights, abs=1e-3) == 1.0


@patch("backend.app.services.weather_service.WeatherObservationService.predict_rainfall")
@patch("backend.app.services.nwp_service.NWPService.fetch_point_forecast")
@patch("backend.app.services.radar_service.RadarService.fetch_radar_composite")
@patch("backend.app.services.satellite_imagery_service.SatelliteImageryService.predict_inundation")
def test_risk_endpoint_insufficient_evidence_returns_422(mock_sat, mock_radar, mock_nwp, mock_rainfall):
    # 3 of 4 streams fail -> only 1 available source -> triggers 422
    mock_rainfall.return_value = mock_rainfall_response()
    mock_nwp.side_effect = ServiceUnavailableError("NWP forecast unavailable")
    mock_radar.side_effect = ServiceUnavailableError("Radar tile stream offline")
    mock_sat.side_effect = ServiceUnavailableError("No Sentinel scenes available")

    payload = {
        "latitude": 19.0760,
        "longitude": 72.8777,
        "prediction_date": "2026-09-16",
    }

    resp = client.post("/api/v1/predict/risk", json=payload)
    assert resp.status_code == 422
    data = resp.json()
    assert data["error"]["code"] == "INSUFFICIENT_HISTORICAL_DATA"
    assert "Insufficient multi-source evidence" in data["error"]["message"]


def test_risk_endpoint_invalid_coordinates():
    resp = client.post(
        "/api/v1/predict/risk",
        json={"latitude": 120.0, "longitude": 72.8777},  # Invalid latitude > 90
    )
    assert resp.status_code == 422


def test_risk_endpoint_invalid_date_format():
    resp = client.post(
        "/api/v1/predict/risk",
        json={
            "latitude": 19.0760,
            "longitude": 72.8777,
            "prediction_date": "16-09-2026",  # Invalid format
        },
    )
    assert resp.status_code == 422
    data = resp.json()
    assert "Expected 'YYYY-MM-DD'" in data["error"]["message"]
