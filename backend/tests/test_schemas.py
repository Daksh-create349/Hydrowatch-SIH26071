"""Tests for Pydantic data validation schemas."""

from datetime import datetime, timezone
import pytest
from pydantic import ValidationError

from backend.app.schemas.common import Coordinates, GeoBoundingBox, Location
from backend.app.schemas.prediction import InundationPrediction, RainfallPrediction
from backend.app.schemas.response import AnalysisResponse
from backend.app.schemas.risk import RiskAssessment, RiskLevel
from backend.app.schemas.warning import AlertAction, AlertSeverity, WarningAlert
from backend.app.schemas.weather import WeatherFeatureVector


def test_coordinates_validation():
    """Verify coordinate bounds checking."""
    # Valid
    c = Coordinates(latitude=19.0760, longitude=72.8777)
    assert c.latitude == 19.0760
    assert c.longitude == 72.8777

    # Invalid latitude
    with pytest.raises(ValidationError):
        Coordinates(latitude=105.0, longitude=72.0)

    # Invalid longitude
    with pytest.raises(ValidationError):
        Coordinates(latitude=19.0, longitude=-190.0)


def test_weather_feature_vector_37_fields():
    """Verify 37 leakage-safe weather features validate."""
    feature_dict = {
        "PRECTOTCORR": 12.5,
        "T2M": 28.5,
        "T2MDEW": 24.1,
        "RH2M": 82.0,
        "PS": 100.5,
        "WS2M": 3.4,
        "WS10M": 5.2,
        "ALLSKY_SFC_SW_DWN": 18.2,
        "rain_lag_1d": 5.0,
        "rain_lag_2d": 2.0,
        "rain_lag_3d": 0.0,
        "rain_lag_7d": 15.0,
        "rain_lag_14d": 30.0,
        "rain_sum_prev_3d": 7.0,
        "rain_sum_prev_7d": 22.0,
        "rain_sum_prev_14d": 52.0,
        "rain_sum_prev_30d": 110.0,
        "rain_mean_prev_7d": 3.14,
        "rain_max_prev_7d": 12.0,
        "T2M_lag_1d": 28.0,
        "T2MDEW_lag_1d": 24.0,
        "RH2M_lag_1d": 80.0,
        "PS_lag_1d": 100.4,
        "WS2M_lag_1d": 3.1,
        "WS10M_lag_1d": 4.9,
        "ALLSKY_SFC_SW_DWN_lag_1d": 17.8,
        "temperature_change_1d": 0.5,
        "humidity_change_1d": 2.0,
        "pressure_change_1d": 0.1,
        "wind_change_1d": 0.3,
        "month": 7,
        "month_sin": -0.5,
        "month_cos": -0.866,
        "doy_sin": 0.12,
        "doy_cos": 0.99,
        "latitude": 19.0760,
        "longitude": 72.8777,
    }
    vec = WeatherFeatureVector(**feature_dict)
    assert vec.month == 7
    assert vec.PRECTOTCORR == 12.5


def test_analysis_response_schema():
    """Verify unified analysis response serialization."""
    loc = Location(
        name="Mumbai",
        state="Maharashtra",
        coordinates=Coordinates(latitude=19.0760, longitude=72.8777),
    )
    resp = AnalysisResponse(
        request_id="req_test_001",
        location=loc,
        warnings=[
            WarningAlert(
                alert_id="ALT-2026-001",
                issued_at=datetime.now(timezone.utc),
                valid_from=datetime.now(timezone.utc),
                valid_until=datetime.now(timezone.utc),
                location=loc,
                severity=AlertSeverity.ORANGE,
                headline="Heavy Rainfall Alert for Mumbai",
                description="High probability of heavy precipitation within 24 hours.",
                recommended_actions=[
                    AlertAction(
                        priority=1,
                        target_audience="Public",
                        action="Avoid waterlogged low-lying roads.",
                    )
                ],
            )
        ],
    )
    serialized = resp.model_dump()
    assert serialized["request_id"] == "req_test_001"
    assert serialized["warnings"][0]["severity"] == "orange"
