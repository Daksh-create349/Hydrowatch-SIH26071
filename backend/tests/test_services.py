"""Tests for service interfaces and connection integrity."""

from datetime import datetime, timezone
import pytest

from backend.app.schemas.common import Coordinates, GeoBoundingBox, Location
from backend.app.schemas.prediction import InundationPrediction, RainfallPrediction
from backend.app.schemas.risk import RiskAssessment, RiskLevel
from backend.app.schemas.satellite import Sentinel2Bands
from backend.app.services.model1_service import Model1Service
from backend.app.services.model2_service import Model2Service
from backend.app.services.nwp_service import NWPService
from backend.app.services.radar_service import RadarService
from backend.app.services.risk_fusion_service import RiskFusionService
from backend.app.services.satellite_imagery_service import SatelliteImageryService
from backend.app.services.satellite_precip_service import SatellitePrecipitationService
from backend.app.services.terrain_service import TerrainService
from backend.app.services.warning_service import WarningService
from backend.app.services.weather_service import WeatherObservationService


def test_weather_service_unconnected_raises_not_implemented():
    """Verify WeatherObservationService does not return fake data."""
    svc = WeatherObservationService()
    coords = Coordinates(latitude=19.0760, longitude=72.8777)
    with pytest.raises(NotImplementedError):
        svc.get_latest_observation(coords)
    with pytest.raises(NotImplementedError):
        svc.extract_feature_vector(coords, datetime.now(timezone.utc))


def test_nwp_service_unconnected_raises_not_implemented():
    """Verify NWPService does not return fake forecasts."""
    svc = NWPService()
    coords = Coordinates(latitude=19.0760, longitude=72.8777)
    bbox = GeoBoundingBox(min_lat=18.8, max_lat=19.3, min_lon=72.7, max_lon=73.1)
    with pytest.raises(NotImplementedError):
        svc.get_forecast_for_point(coords)
    with pytest.raises(NotImplementedError):
        svc.get_forecast_grid(bbox)


def test_radar_service_unconnected_raises_not_implemented():
    """Verify RadarService does not return fake radar returns."""
    svc = RadarService()
    bbox = GeoBoundingBox(min_lat=18.8, max_lat=19.3, min_lon=72.7, max_lon=73.1)
    with pytest.raises(NotImplementedError):
        svc.get_latest_radar_scan("MUMBAI_DWR")
    with pytest.raises(NotImplementedError):
        svc.get_reflectivity_composite(bbox)


def test_satellite_precip_service_unconnected_raises_not_implemented():
    """Verify SatellitePrecipitationService does not return fake precipitation."""
    svc = SatellitePrecipitationService()
    coords = Coordinates(latitude=19.0760, longitude=72.8777)
    with pytest.raises(NotImplementedError):
        svc.get_latest_precipitation(coords)


def test_satellite_imagery_service_unconnected_raises_not_implemented():
    """Verify SatelliteImageryService does not return fake bands."""
    svc = SatelliteImageryService()
    with pytest.raises(NotImplementedError):
        svc.download_and_extract_bands("scene_123")


def test_terrain_service_unconnected_raises_not_implemented():
    """Verify TerrainService does not return fake elevation."""
    svc = TerrainService()
    coords = Coordinates(latitude=19.0760, longitude=72.8777)
    with pytest.raises(NotImplementedError):
        svc.get_elevation_at_point(coords)


def test_model1_service_real_loading_and_inference():
    """Verify Model 1 real loading and inference with 37 features."""
    from backend.app.schemas.weather import WeatherFeatureVector
    svc = Model1Service()
    svc.load()
    assert svc.is_loaded is True
    assert svc.has_model_artifact() is True

    feat = WeatherFeatureVector(
        PRECTOTCORR=10.0, T2M=28.0, T2MDEW=24.0, RH2M=80.0, PS=100.0,
        WS2M=3.0, WS10M=5.0, ALLSKY_SFC_SW_DWN=15.0,
        rain_lag_1d=5.0, rain_lag_2d=2.0, rain_lag_3d=0.0, rain_lag_7d=10.0, rain_lag_14d=25.0,
        rain_sum_prev_3d=7.0, rain_sum_prev_7d=17.0, rain_sum_prev_14d=42.0, rain_sum_prev_30d=90.0,
        rain_mean_prev_7d=2.43, rain_max_prev_7d=10.0,
        T2M_lag_1d=27.5, T2MDEW_lag_1d=23.5, RH2M_lag_1d=79.0, PS_lag_1d=100.1,
        WS2M_lag_1d=2.8, WS10M_lag_1d=4.8, ALLSKY_SFC_SW_DWN_lag_1d=14.5,
        temperature_change_1d=0.5, humidity_change_1d=1.0, pressure_change_1d=-0.1, wind_change_1d=0.2,
        month=7, month_sin=-0.5, month_cos=-0.866, doy_sin=0.12, doy_cos=0.99,
        latitude=19.0760, longitude=72.8777,
    )
    result = svc.predict_heavy_rainfall(feat)
    assert 0.0 <= result.heavy_rain_probability <= 1.0
    assert result.decision_threshold == 0.81


def test_model2_service_predict_inundation_contract():
    """Verify Model 2 predict_inundation raises NotImplementedError for Sentinel2Bands."""
    svc = Model2Service()
    with pytest.raises(NotImplementedError):
        svc.predict_inundation(Sentinel2Bands())


def test_risk_fusion_unconnected_raises_not_implemented():
    """Verify RiskFusionService does not return fake risk scores."""
    svc = RiskFusionService()
    loc = Location(
        name="Mumbai",
        coordinates=Coordinates(latitude=19.0760, longitude=72.8777),
    )
    r_pred = RainfallPrediction(
        target_date="2026-09-17",
        coordinates=Coordinates(latitude=19.0760, longitude=72.8777),
        heavy_rain_probability=0.75,
        is_heavy_rain=True,
    )
    i_pred = InundationPrediction(
        scene_timestamp=datetime.now(timezone.utc),
        bounding_box=GeoBoundingBox(min_lat=18.8, max_lat=19.3, min_lon=72.7, max_lon=73.1),
        water_pixel_count=1000,
        total_valid_pixels=10000,
        flooded_area_percentage=10.0,
    )
    with pytest.raises(NotImplementedError):
        svc.assess_risk(loc, r_pred, i_pred)


def test_warning_service_unconnected_raises_not_implemented():
    """Verify WarningService does not return fake warnings."""
    svc = WarningService()
    loc = Location(
        name="Mumbai",
        coordinates=Coordinates(latitude=19.0760, longitude=72.8777),
    )
    risk = RiskAssessment(
        location=loc,
        assessment_time=datetime.now(timezone.utc),
        overall_risk_level=RiskLevel.HIGH,
        rainfall_risk_score=0.8,
        inundation_risk_score=0.7,
        composite_risk_score=0.75,
        summary="High risk assessment test",
    )
    with pytest.raises(NotImplementedError):
        svc.generate_warnings(loc, risk)
