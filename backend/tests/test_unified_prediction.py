"""Unit and integration tests for unified end-to-end prediction pipeline (POST /api/v1/predict)."""

from unittest.mock import AsyncMock, patch
import pytest
from fastapi.testclient import TestClient

from backend.app.core.errors import ServiceUnavailableError
from backend.app.main import app
from backend.app.schemas.common import Coordinates, GeoBoundingBox
from backend.app.schemas.nwp import NWPForecastItem, NWPForecastSummary, NWPPointForecastResponse
from backend.app.schemas.prediction import InundationPipelineResponse, RainfallPipelineResponse
from backend.app.schemas.radar import RadarDataResponse, RadarTileReflectivity
from backend.app.schemas.unified import UnifiedPredictionRequest
from backend.app.services.unified_prediction_service import UnifiedPredictionService

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
        geojson={
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [[[72.87, 19.07], [72.88, 19.07], [72.88, 19.08], [72.87, 19.07]]],
                    },
                    "properties": {"area_sq_m": 12000.0, "perimeter_m": 450.0},
                }
            ],
        },
    )


# ============================================================
# UNIFIED PIPELINE INTEGRATION TESTS
# ============================================================

@patch("backend.app.services.weather_service.WeatherObservationService.predict_rainfall")
@patch("backend.app.services.nwp_service.NWPService.fetch_point_forecast")
@patch("backend.app.services.radar_service.RadarService.fetch_radar_composite")
@patch("backend.app.services.satellite_imagery_service.SatelliteImageryService.predict_inundation")
def test_unified_prediction_full_evidence_success(mock_sat, mock_radar, mock_nwp, mock_rainfall):
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
        "min_polygon_area_sq_m": 500.0,
        "location_name": "Mumbai Test Station",
    }

    response = client.post("/api/v1/predict", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "success"
    assert "generated_at" in data

    # 1. Rainfall section
    rf = data["rainfall_prediction"]
    assert rf is not None
    assert rf["probability"] == 0.15
    assert rf["predicted"] is False
    assert rf["threshold"] == 0.81
    assert rf["observation_date"] == "2026-09-15"
    assert rf["model_version"] == "heavy_rainfall_xgboost_v2"
    assert rf["historical_records_used"] == 30
    assert rf["latest_precipitation_mm"] == 10.0

    # 2. NWP section
    nwp = data["nwp"]
    assert nwp is not None
    assert "Open-Meteo" in nwp["source"]
    assert nwp["forecast_horizon_hours"] == 24
    assert nwp["accumulated_precipitation_mm"] == 15.0
    assert nwp["peak_hourly_precipitation_mm_hr"] == 4.0
    assert len(nwp["valid_times"]) == 1

    # 3. Radar section
    radar = data["radar"]
    assert radar is not None
    assert "RainViewer" in radar["source"]
    assert radar["max_reflectivity_dbz"] == 25.0
    assert radar["estimated_rain_rate_mm_hr"] == 1.5
    assert radar["coverage_percentage"] == 2.29
    assert radar["tile_url"] is not None

    # 4. Inundation section with GeoJSON
    inundation = data["inundation"]
    assert inundation is not None
    assert inundation["flooded_area_sq_km"] == 0.8
    assert inundation["flooded_percentage"] == 3.0
    assert inundation["polygon_count"] == 5
    assert inundation["geojson"]["type"] == "FeatureCollection"
    assert len(inundation["geojson"]["features"]) == 1

    # 5. Composite Risk
    risk = data["risk"]
    assert risk["score"] >= 0.0
    assert risk["level"] in ["LOW", "MODERATE", "HIGH", "EXTREME"]
    assert risk["fusion"]["policy_applied"] == "FULL_EVIDENCE"
    assert len(risk["explanations"]) == 4

    # 6. Warning Decision
    warning = data["warning"]
    assert warning["status"] in ["NO_ALERT", "MONITOR", "PREPARE", "ACTION"]
    assert warning["prototype_only"] is True
    assert warning["official_warning_issued"] is False
    assert "EXPERIMENTAL PROTOTYPE ASSESSMENT" in warning["disclaimer"]

    # 7. Source Status
    status_map = data["source_status"]
    assert len(status_map) == 4
    for key in ["weather_model1", "nwp", "radar", "satellite_model2"]:
        assert status_map[key]["available"] is True
        assert status_map[key]["status"] == "success"
        assert status_map[key]["latency_ms"] >= 0.0
        assert status_map[key]["error"] is None

    # 8. Timing Breakdown
    timing = data["timing"]
    assert timing["total_ms"] >= 0.0
    assert timing["weather_model1_ms"] >= 0.0
    assert timing["nwp_ms"] >= 0.0
    assert timing["radar_ms"] >= 0.0
    assert timing["satellite_model2_ms"] >= 0.0
    assert timing["fusion_ms"] >= 0.0
    assert timing["warning_ms"] >= 0.0

    # 9. Provenance
    # 9. Provenance
    prov = data["provenance"]
    assert prov["model_versions"]["heavy_rainfall_model"] == "heavy_rainfall_xgboost_v2"
    assert prov["model_versions"]["flood_inundation_model"] == "flood_unet_sentinel2_6band"
    assert "configured_risk_weights" in prov
    assert "configured_thresholds" in prov


@patch("backend.app.services.weather_service.WeatherObservationService.predict_rainfall")
@patch("backend.app.services.nwp_service.NWPService.fetch_point_forecast")
@patch("backend.app.services.radar_service.RadarService.fetch_radar_composite")
@patch("backend.app.services.satellite_imagery_service.SatelliteImageryService.predict_inundation")
def test_unified_prediction_trailing_slash_support(mock_sat, mock_radar, mock_nwp, mock_rainfall):
    mock_rainfall.return_value = mock_rainfall_response()
    mock_nwp.return_value = mock_nwp_response()
    mock_radar.return_value = mock_radar_response()
    mock_sat.return_value = mock_inundation_response()

    payload = {"latitude": 19.0760, "longitude": 72.8777}
    resp = client.post("/api/v1/predict/", json=payload)
    assert resp.status_code == 200
    assert resp.json()["status"] == "success"


@patch("backend.app.services.weather_service.WeatherObservationService.predict_rainfall")
@patch("backend.app.services.nwp_service.NWPService.fetch_point_forecast")
@patch("backend.app.services.radar_service.RadarService.fetch_radar_composite")
@patch("backend.app.services.satellite_imagery_service.SatelliteImageryService.predict_inundation")
def test_unified_prediction_partial_radar_missing(mock_sat, mock_radar, mock_nwp, mock_rainfall):
    mock_rainfall.return_value = mock_rainfall_response(prob=0.3)
    mock_nwp.return_value = mock_nwp_response(hourly_rate=5.0)
    mock_radar.side_effect = ServiceUnavailableError("RainViewer Doppler radar API timed out")
    mock_sat.return_value = mock_inundation_response(flooded_area=1.0)

    payload = {"latitude": 19.0760, "longitude": 72.8777}
    response = client.post("/api/v1/predict", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["radar"] is None
    assert data["source_status"]["radar"]["available"] is False
    assert data["source_status"]["radar"]["status"] == "failed"
    assert "RainViewer Doppler radar API timed out" in data["source_status"]["radar"]["error"]
    assert data["risk"]["fusion"]["policy_applied"] == "PARTIAL_EVIDENCE"
    assert "radar_nowcast" in data["risk"]["fusion"]["unavailable_sources"]
    assert data["warning"]["prototype_only"] is True


@patch("backend.app.services.weather_service.WeatherObservationService.predict_rainfall")
@patch("backend.app.services.nwp_service.NWPService.fetch_point_forecast")
@patch("backend.app.services.radar_service.RadarService.fetch_radar_composite")
@patch("backend.app.services.satellite_imagery_service.SatelliteImageryService.predict_inundation")
def test_unified_prediction_partial_satellite_missing(mock_sat, mock_radar, mock_nwp, mock_rainfall):
    mock_rainfall.return_value = mock_rainfall_response(prob=0.2)
    mock_nwp.return_value = mock_nwp_response(hourly_rate=3.0)
    mock_radar.return_value = mock_radar_response(dbz=20.0)
    mock_sat.side_effect = ServiceUnavailableError("Earth Search STAC catalog unavailable")

    payload = {"latitude": 19.0760, "longitude": 72.8777}
    response = client.post("/api/v1/predict", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["inundation"] is None
    assert data["source_status"]["satellite_model2"]["available"] is False
    assert data["source_status"]["satellite_model2"]["status"] == "failed"
    assert "Earth Search STAC catalog unavailable" in data["source_status"]["satellite_model2"]["error"]
    assert data["risk"]["fusion"]["policy_applied"] == "PARTIAL_EVIDENCE"
    assert "satellite_inundation" in data["risk"]["fusion"]["unavailable_sources"]


@patch("backend.app.services.weather_service.WeatherObservationService.predict_rainfall")
@patch("backend.app.services.nwp_service.NWPService.fetch_point_forecast")
@patch("backend.app.services.radar_service.RadarService.fetch_radar_composite")
@patch("backend.app.services.satellite_imagery_service.SatelliteImageryService.predict_inundation")
def test_unified_prediction_partial_weather_missing(mock_sat, mock_radar, mock_nwp, mock_rainfall):
    mock_rainfall.side_effect = ServiceUnavailableError("NASA POWER service down")
    mock_nwp.return_value = mock_nwp_response(hourly_rate=3.0)
    mock_radar.return_value = mock_radar_response(dbz=20.0)
    mock_sat.return_value = mock_inundation_response(flooded_area=0.5)

    payload = {"latitude": 19.0760, "longitude": 72.8777}
    response = client.post("/api/v1/predict", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["rainfall_prediction"] is None
    assert data["source_status"]["weather_model1"]["available"] is False
    assert data["source_status"]["weather_model1"]["status"] == "failed"
    assert "NASA POWER service down" in data["source_status"]["weather_model1"]["error"]
    assert "heavy_rainfall_model" in data["risk"]["fusion"]["unavailable_sources"]


@patch("backend.app.services.weather_service.WeatherObservationService.predict_rainfall")
@patch("backend.app.services.nwp_service.NWPService.fetch_point_forecast")
@patch("backend.app.services.radar_service.RadarService.fetch_radar_composite")
@patch("backend.app.services.satellite_imagery_service.SatelliteImageryService.predict_inundation")
def test_unified_prediction_insufficient_evidence_raises_422(mock_sat, mock_radar, mock_nwp, mock_rainfall):
    mock_rainfall.return_value = mock_rainfall_response(prob=0.1)
    mock_nwp.side_effect = ServiceUnavailableError("NWP down")
    mock_radar.side_effect = ServiceUnavailableError("Radar down")
    mock_sat.side_effect = ServiceUnavailableError("Satellite down")

    payload = {"latitude": 19.0760, "longitude": 72.8777}
    response = client.post("/api/v1/predict", json=payload)
    assert response.status_code == 422
    data = response.json()
    assert data["error"]["code"] == "INSUFFICIENT_HISTORICAL_DATA"
    assert "Insufficient multi-source evidence" in data["error"]["message"]


def test_unified_prediction_validation_errors():
    # 1. Invalid latitude
    resp = client.post("/api/v1/predict", json={"latitude": 95.0, "longitude": 72.8})
    assert resp.status_code == 422

    # 2. Invalid longitude
    resp = client.post("/api/v1/predict", json={"latitude": 19.0, "longitude": -195.0})
    assert resp.status_code == 422

    # 3. Invalid prediction_date format
    resp = client.post("/api/v1/predict", json={"latitude": 19.0, "longitude": 72.8, "prediction_date": "16-09-2026"})
    assert resp.status_code == 422

    # 4. Invalid satellite_date format
    resp = client.post("/api/v1/predict", json={"latitude": 19.0, "longitude": 72.8, "satellite_date": "bad-date"})
    assert resp.status_code == 422

    # 5. Invalid satellite_max_cloud
    resp = client.post("/api/v1/predict", json={"latitude": 19.0, "longitude": 72.8, "satellite_max_cloud": 150.0})
    assert resp.status_code == 422

    # 6. Invalid nwp_horizon_hours
    resp = client.post("/api/v1/predict", json={"latitude": 19.0, "longitude": 72.8, "nwp_horizon_hours": 0})
    assert resp.status_code == 422

    # 7. Invalid min_polygon_area_sq_m
    resp = client.post("/api/v1/predict", json={"latitude": 19.0, "longitude": 72.8, "min_polygon_area_sq_m": -10.0})
    assert resp.status_code == 422


@patch("backend.app.services.weather_service.WeatherObservationService.predict_rainfall")
@patch("backend.app.services.nwp_service.NWPService.fetch_point_forecast")
@patch("backend.app.services.radar_service.RadarService.fetch_radar_composite")
@patch("backend.app.services.satellite_imagery_service.SatelliteImageryService.predict_inundation")
def test_unified_prediction_deterministic_and_idempotent(mock_sat, mock_radar, mock_nwp, mock_rainfall):
    mock_rainfall.return_value = mock_rainfall_response(prob=0.85, precip=70.0)
    mock_nwp.return_value = mock_nwp_response(hourly_rate=25.0, accum=80.0)
    mock_radar.return_value = mock_radar_response(dbz=52.0, rain_rate=35.0)
    mock_sat.return_value = mock_inundation_response(flooded_area=6.0, pct=15.0)

    payload = {"latitude": 19.0760, "longitude": 72.8777, "prediction_date": "2026-09-16"}

    resp1 = client.post("/api/v1/predict", json=payload)
    resp2 = client.post("/api/v1/predict", json=payload)

    assert resp1.status_code == 200
    assert resp2.status_code == 200

    d1 = resp1.json()
    d2 = resp2.json()

    assert d1["risk"]["score"] == d2["risk"]["score"]
    assert d1["risk"]["level"] == d2["risk"]["level"]
    assert d1["warning"]["status"] == d2["warning"]["status"]
    assert d1["warning"]["urgency"] == d2["warning"]["urgency"]
    assert d1["warning"]["triggers"] == d2["warning"]["triggers"]


@patch("backend.app.services.weather_service.WeatherObservationService.predict_rainfall")
@patch("backend.app.services.nwp_service.NWPService.fetch_point_forecast")
@patch("backend.app.services.radar_service.RadarService.fetch_radar_composite")
@patch("backend.app.services.satellite_imagery_service.SatelliteImageryService.predict_inundation")
def test_unified_prediction_no_duplicate_provider_calls(mock_sat, mock_radar, mock_nwp, mock_rainfall):
    mock_rainfall.return_value = mock_rainfall_response()
    mock_nwp.return_value = mock_nwp_response()
    mock_radar.return_value = mock_radar_response()
    mock_sat.return_value = mock_inundation_response()

    payload = {"latitude": 19.0760, "longitude": 72.8777}
    resp = client.post("/api/v1/predict", json=payload)
    assert resp.status_code == 200

    assert mock_rainfall.call_count == 1
    assert mock_nwp.call_count == 1
    assert mock_radar.call_count == 1
    assert mock_sat.call_count == 1


def test_unified_prediction_model_singletons_reused():
    from backend.app.services.model1_service import Model1Service
    from backend.app.services.model2_service import Model2Service

    m1_first = Model1Service.get_instance()
    m1_second = Model1Service.get_instance()
    assert m1_first is m1_second

    m2_first = Model2Service.get_instance()
    m2_second = Model2Service.get_instance()
    assert m2_first is m2_second

