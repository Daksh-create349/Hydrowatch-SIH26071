"""Integration tests for POST /api/v1/predict/warning pipeline endpoint."""

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


def mock_rainfall_response(prob=0.25, precip=14.5):
    return RainfallPipelineResponse(
        status="success",
        prediction_date="2026-09-16",
        observation_date="2026-09-15",
        coordinates=Coordinates(latitude=19.0760, longitude=72.8777),
        location_name="Mumbai",
        heavy_rain_predicted=prob >= 0.81,
        heavy_rain_probability=prob,
        threshold=0.81,
        model_version="heavy_rainfall_xgboost_v2",
        historical_records_used=30,
        features_computed=37,
        latest_weather={"PRECTOTCORR": precip, "T2M": 28.0},
    )


def mock_nwp_response(hourly_rate=7.5, accum=30.0):
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
            total_precipitation_mm=accum,
            max_hourly_precipitation_mm_hr=hourly_rate,
            min_temperature_c=24.0,
            max_temperature_c=31.0,
            max_wind_speed_ms=8.0,
            max_cape_j_kg=550.0,
        ),
        forecasts=[
            NWPForecastItem(
                valid_time="2026-09-16T11:00:00Z",
                lead_hours=1,
                precipitation_mm_hr=hourly_rate,
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


def mock_radar_response(dbz=28.5, rain_rate=2.1):
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
            max_reflectivity_dbz=dbz,
            mean_reflectivity_dbz=16.0,
            estimated_max_rain_rate_mm_hr=rain_rate,
            tile_url="https://tilecache.rainviewer.com/v2/radar/1789552800/256/6/47/28/2/1_1.png",
        ),
        available_frames_count=13,
    )


def mock_inundation_response(flooded_area=1.2, pct=4.58):
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
        flooded_area_sq_km=flooded_area,
        flooded_percentage=pct,
        polygon_count=5,
        geojson={"type": "FeatureCollection", "features": []},
    )


# ============================================================
# ENDPOINT TESTS
# ============================================================


@patch("backend.app.services.weather_service.WeatherObservationService.predict_rainfall")
@patch("backend.app.services.nwp_service.NWPService.fetch_point_forecast")
@patch("backend.app.services.radar_service.RadarService.fetch_radar_composite")
@patch("backend.app.services.satellite_imagery_service.SatelliteImageryService.predict_inundation")
def test_warning_endpoint_full_evidence_success(mock_sat, mock_radar, mock_nwp, mock_rainfall):
    mock_rainfall.return_value = mock_rainfall_response(prob=0.15, precip=10.0)
    mock_nwp.return_value = mock_nwp_response(hourly_rate=4.0, accum=15.0)
    mock_radar.return_value = mock_radar_response(dbz=25.0, rain_rate=1.5)
    mock_sat.return_value = mock_inundation_response(flooded_area=0.8, pct=3.0)

    payload = {
        "latitude": 19.0760,
        "longitude": 72.8777,
        "prediction_date": "2026-09-16",
        "nwp_horizon_hours": 24,
        "satellite_max_cloud": 20.0,
        "location_name": "Mumbai Test Site",
    }

    resp = client.post("/api/v1/predict/warning", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    assert data["status"] == "success"
    assert data["requested_location"]["latitude"] == 19.0760
    assert data["requested_location"]["longitude"] == 72.8777
    assert data["location_name"] == "Mumbai Test Site"

    # Warning decision fields
    warning = data["warning"]
    assert warning["status"] in ["NO_ALERT", "MONITOR", "PREPARE", "ACTION"]
    assert warning["prototype_only"] is True
    assert warning["official_warning_issued"] is False
    assert "NOT AN OFFICIAL IMD GOVERNMENT WARNING" in warning["disclaimer"]
    assert len(warning["triggers"]) >= 4

    # Freshness
    freshness = data["evidence_freshness"]
    assert len(freshness["current_sources"]) >= 1

    # Provenance
    prov = data["source_provenance"]
    assert "heavy_rainfall_model" in prov["model_versions"]
    assert "flood_inundation_model" in prov["model_versions"]
    assert prov["rules_version"] == "v1.0_prototype_sih2026"


@patch("backend.app.services.weather_service.WeatherObservationService.predict_rainfall")
@patch("backend.app.services.nwp_service.NWPService.fetch_point_forecast")
@patch("backend.app.services.radar_service.RadarService.fetch_radar_composite")
@patch("backend.app.services.satellite_imagery_service.SatelliteImageryService.predict_inundation")
def test_warning_endpoint_action_state_under_severe_threat(mock_sat, mock_radar, mock_nwp, mock_rainfall):
    # Severe multi-source storm
    mock_rainfall.return_value = mock_rainfall_response(prob=0.95, precip=95.0)
    mock_nwp.return_value = mock_nwp_response(hourly_rate=45.0, accum=140.0)
    mock_radar.return_value = mock_radar_response(dbz=58.0, rain_rate=65.0)
    mock_sat.return_value = mock_inundation_response(flooded_area=22.0, pct=42.0)

    payload = {
        "latitude": 19.0760,
        "longitude": 72.8777,
        "prediction_date": "2026-09-16",
    }

    resp = client.post("/api/v1/predict/warning", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    warning = data["warning"]
    assert warning["status"] == "ACTION"
    assert warning["urgency"] == "ACTION"
    assert warning["risk_level"] == "EXTREME"
    assert warning["triggered"] is True
    assert len(warning["trigger_reasons"]) >= 3


@patch("backend.app.services.weather_service.WeatherObservationService.predict_rainfall")
@patch("backend.app.services.nwp_service.NWPService.fetch_point_forecast")
@patch("backend.app.services.radar_service.RadarService.fetch_radar_composite")
@patch("backend.app.services.satellite_imagery_service.SatelliteImageryService.predict_inundation")
def test_warning_endpoint_partial_evidence_radar_missing(mock_sat, mock_radar, mock_nwp, mock_rainfall):
    mock_rainfall.return_value = mock_rainfall_response(prob=0.20, precip=5.0)
    mock_nwp.return_value = mock_nwp_response(hourly_rate=3.0, accum=12.0)
    mock_radar.side_effect = ServiceUnavailableError("Radar tile stream offline")
    mock_sat.return_value = mock_inundation_response(flooded_area=0.5, pct=1.5)

    payload = {
        "latitude": 19.0760,
        "longitude": 72.8777,
        "prediction_date": "2026-09-16",
    }

    resp = client.post("/api/v1/predict/warning", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    # Adapts to NWP validity
    warning = data["warning"]
    assert warning["status"] == "NO_ALERT"
    assert "NOAA GFS synoptic NWP forecast cycle" in warning["validity_reason"]


@patch("backend.app.services.weather_service.WeatherObservationService.predict_rainfall")
@patch("backend.app.services.nwp_service.NWPService.fetch_point_forecast")
@patch("backend.app.services.radar_service.RadarService.fetch_radar_composite")
@patch("backend.app.services.satellite_imagery_service.SatelliteImageryService.predict_inundation")
def test_warning_endpoint_insufficient_evidence_returns_422(mock_sat, mock_radar, mock_nwp, mock_rainfall):
    mock_rainfall.return_value = mock_rainfall_response()
    mock_nwp.side_effect = ServiceUnavailableError("NWP offline")
    mock_radar.side_effect = ServiceUnavailableError("Radar offline")
    mock_sat.side_effect = ServiceUnavailableError("Satellite offline")

    payload = {
        "latitude": 19.0760,
        "longitude": 72.8777,
        "prediction_date": "2026-09-16",
    }

    resp = client.post("/api/v1/predict/warning", json=payload)
    assert resp.status_code == 422
    data = resp.json()
    assert data["error"]["code"] == "INSUFFICIENT_HISTORICAL_DATA"


def test_warning_endpoint_invalid_coordinates():
    resp = client.post(
        "/api/v1/predict/warning",
        json={"latitude": 105.0, "longitude": 72.8777},
    )
    assert resp.status_code == 422


def test_warning_endpoint_invalid_date_format():
    resp = client.post(
        "/api/v1/predict/warning",
        json={
            "latitude": 19.0760,
            "longitude": 72.8777,
            "prediction_date": "2026/09/16",
        },
    )
    assert resp.status_code == 422
    data = resp.json()
    assert "Expected 'YYYY-MM-DD'" in data["error"]["message"]
