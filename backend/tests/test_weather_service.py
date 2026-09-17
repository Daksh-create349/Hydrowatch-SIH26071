"""Unit tests for NASA POWER API client, response parser, and Model 1 feature builder."""

from datetime import date, timedelta
import math
import pytest
import httpx

from backend.app.core.errors import (
    ExternalApiError,
    InsufficientHistoricalDataError,
    WeatherObservationValidationError,
)
from backend.app.schemas.common import Coordinates
from backend.app.schemas.weather import DailyWeatherRecord
from backend.app.services.feature_builder import Model1FeatureBuilder
from backend.app.services.model1_service import MODEL1_FEATURE_ORDER
from backend.app.services.nasa_power_client import REQUIRED_NASA_POWER_PARAMS, NasaPowerClient


def create_mock_nasa_power_payload(start_date: date, num_days: int) -> dict:
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
                val = float(idx % 15)  # Varied rainfall pattern
            elif p == "T2M":
                val = 28.0 + (idx % 5) * 0.5
            elif p == "T2MDEW":
                val = 24.0 + (idx % 3) * 0.2
            elif p == "RH2M":
                val = 75.0 + (idx % 10)
            elif p == "PS":
                val = 100.5 - (idx % 4) * 0.1
            elif p == "WS2M":
                val = 2.5 + (idx % 3) * 0.3
            elif p == "WS10M":
                val = 4.0 + (idx % 3) * 0.4
            elif p == "ALLSKY_SFC_SW_DWN":
                val = 15.0 + (idx % 6)
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
        "header": {"title": "NASA POWER Test Data"},
    }


def test_nasa_power_parser_valid():
    """Verify parser extracts and orders daily weather records."""
    client = NasaPowerClient()
    coords = Coordinates(latitude=19.0760, longitude=72.8777)
    payload = create_mock_nasa_power_payload(date(2024, 1, 1), 35)

    records = client.parse_response(payload, coords)
    assert len(records) == 35
    assert records[0].date == date(2024, 1, 1)
    assert records[-1].date == date(2024, 1, 1) + timedelta(days=34)
    assert records[0].PRECTOTCORR >= 0.0
    assert records[0].T2M > 20.0


def test_nasa_power_parser_missing_parameter():
    """Verify parser rejects payload missing any required parameter."""
    client = NasaPowerClient()
    coords = Coordinates(latitude=19.0760, longitude=72.8777)
    payload = create_mock_nasa_power_payload(date(2024, 1, 1), 10)
    del payload["properties"]["parameter"]["WS10M"]

    with pytest.raises(WeatherObservationValidationError) as exc:
        client.parse_response(payload, coords)
    assert "WS10M" in str(exc.value)


def test_nasa_power_parser_non_finite_value():
    """Verify parser rejects non-finite meteorological values."""
    client = NasaPowerClient()
    coords = Coordinates(latitude=19.0760, longitude=72.8777)
    payload = create_mock_nasa_power_payload(date(2024, 1, 1), 5)
    # Inject NaN
    payload["properties"]["parameter"]["T2M"]["20240102"] = float("nan")

    with pytest.raises(WeatherObservationValidationError) as exc:
        client.parse_response(payload, coords)
    assert "Non-finite" in str(exc.value) or "missing" in str(exc.value)


def test_nasa_power_parser_sentinel_missing_value():
    """Verify parser rejects NASA POWER -999.0 sentinel value."""
    client = NasaPowerClient()
    coords = Coordinates(latitude=19.0760, longitude=72.8777)
    payload = create_mock_nasa_power_payload(date(2024, 1, 1), 5)
    payload["properties"]["parameter"]["PRECTOTCORR"]["20240103"] = -999.0

    with pytest.raises(WeatherObservationValidationError) as exc:
        client.parse_response(payload, coords)
    assert "-999" in str(exc.value)


def test_feature_builder_exact_37_features_and_order():
    """Verify feature builder produces exactly 37 features in the exact model ordering."""
    start_date = date(2024, 1, 1)
    pred_date = date(2024, 2, 10)  # D = Feb 10, D-1 = Feb 9
    client = NasaPowerClient()
    coords = Coordinates(latitude=19.0760, longitude=72.8777)
    payload = create_mock_nasa_power_payload(start_date, 45)  # 45 days of data
    records = client.parse_response(payload, coords)

    feature_vec = Model1FeatureBuilder.build_feature_vector(
        records=records,
        prediction_date=pred_date,
        coordinates=coords,
    )
    feature_dict = feature_vec.model_dump()

    # 1. Exact count
    assert len(feature_dict) == 37

    # 2. Exact keys in exact order
    computed_keys = list(feature_dict.keys())
    assert computed_keys == MODEL1_FEATURE_ORDER


def test_feature_builder_math_and_lag_semantics():
    """Verify correctness of lags, rolling statistics, temporal changes, and calendar encodings."""
    pred_date = date(2024, 2, 1)  # D = 2024-02-01
    target_obs = date(2024, 1, 31)  # D-1 = 2024-01-31

    # Create synthetic daily records with exact known values for 32 days
    records = []
    for i in range(32):
        d = target_obs - timedelta(days=31 - i)
        records.append(
            DailyWeatherRecord(
                date=d,
                latitude=19.0760,
                longitude=72.8777,
                PRECTOTCORR=float(i),  # rain increases by 1 each day: 0, 1, ..., 31
                T2M=20.0 + float(i) * 0.1,
                T2MDEW=15.0 + float(i) * 0.1,
                RH2M=60.0,
                PS=101.0,
                WS2M=2.0 + float(i) * 0.05,
                WS10M=3.0,
                ALLSKY_SFC_SW_DWN=15.0,
            )
        )

    vec = Model1FeatureBuilder.build_feature_vector(
        records=records,
        prediction_date=pred_date,
        coordinates=Coordinates(latitude=19.0760, longitude=72.8777),
    )

    # D-1 is records[-1], PRECTOTCORR = 31.0
    assert vec.PRECTOTCORR == 31.0

    # Lags relative to D-1:
    # rain_lag_1d is at D-2 (records[-2]) -> 30.0
    # rain_lag_2d is at D-3 (records[-3]) -> 29.0
    # rain_lag_3d is at D-4 (records[-4]) -> 28.0
    # rain_lag_7d is at D-8 (records[-8]) -> 24.0
    # rain_lag_14d is at D-15 (records[-15]) -> 17.0
    assert vec.rain_lag_1d == 30.0
    assert vec.rain_lag_2d == 29.0
    assert vec.rain_lag_3d == 28.0
    assert vec.rain_lag_7d == 24.0
    assert vec.rain_lag_14d == 17.0

    # Rolling sums ending on D-1:
    # 3d sum: 31 + 30 + 29 = 90.0
    assert vec.rain_sum_prev_3d == 90.0
    # 7d sum: 31 + 30 + 29 + 28 + 27 + 26 + 25 = 196.0
    assert vec.rain_sum_prev_7d == 196.0
    # 7d mean: 196.0 / 7.0 = 28.0
    assert vec.rain_mean_prev_7d == 28.0
    # 7d max: 31.0
    assert vec.rain_max_prev_7d == 31.0

    # 1-day temporal differences:
    # temp_change_1d: T2M(D-1) - T2M(D-2) = (20.0 + 3.1) - (20.0 + 3.0) = 0.1
    assert round(vec.temperature_change_1d, 4) == 0.1
    # wind_change_1d: WS2M(D-1) - WS2M(D-2) = 0.05
    assert round(vec.wind_change_1d, 4) == 0.05

    # Calendar encodings for D-1 (Jan 31: month 1, doy 31)
    assert vec.month == 1
    expected_month_sin = round(math.sin(2.0 * math.pi * 1 / 12.0), 6)
    expected_month_cos = round(math.cos(2.0 * math.pi * 1 / 12.0), 6)
    assert vec.month_sin == expected_month_sin
    assert vec.month_cos == expected_month_cos

    expected_doy_sin = round(math.sin(2.0 * math.pi * 31 / 365.25), 6)
    expected_doy_cos = round(math.cos(2.0 * math.pi * 31 / 365.25), 6)
    assert vec.doy_sin == expected_doy_sin
    assert vec.doy_cos == expected_doy_cos


def test_feature_builder_enforces_zero_future_leakage():
    """Verify that records from target prediction date D or later are strictly ignored."""
    pred_date = date(2024, 2, 1)  # D = 2024-02-01
    target_obs = date(2024, 1, 31)  # D-1

    # Generate 35 days, including records for D (2024-02-01) and D+1 (2024-02-02)
    records = []
    for i in range(35):
        d = target_obs - timedelta(days=32 - i)
        records.append(
            DailyWeatherRecord(
                date=d,
                latitude=19.0760,
                longitude=72.8777,
                PRECTOTCORR=999.0 if d >= pred_date else float(i),
                T2M=25.0,
                T2MDEW=20.0,
                RH2M=60.0,
                PS=101.0,
                WS2M=2.0,
                WS10M=3.0,
                ALLSKY_SFC_SW_DWN=15.0,
            )
        )

    # Even though future records have PRECTOTCORR=999.0, they must be filtered out
    vec = Model1FeatureBuilder.build_feature_vector(
        records=records,
        prediction_date=pred_date,
        coordinates=Coordinates(latitude=19.0760, longitude=72.8777),
    )
    # The value at D-1 should be 32.0, never 999.0
    assert vec.PRECTOTCORR != 999.0


def test_feature_builder_insufficient_history_raises():
    """Verify InsufficientHistoricalDataError is raised when fewer than 30 records exist."""
    pred_date = date(2024, 2, 1)
    target_obs = date(2024, 1, 31)

    # Only 20 days provided, ending on target_obs (D-1)
    records = [
        DailyWeatherRecord(
            date=target_obs - timedelta(days=19 - i),
            latitude=19.0760,
            longitude=72.8777,
            PRECTOTCORR=1.0,
            T2M=25.0,
            T2MDEW=20.0,
            RH2M=60.0,
            PS=101.0,
            WS2M=2.0,
            WS10M=3.0,
            ALLSKY_SFC_SW_DWN=15.0,
        )
        for i in range(20)
    ]

    with pytest.raises(InsufficientHistoricalDataError) as exc:
        Model1FeatureBuilder.build_feature_vector(records, pred_date)
    assert exc.value.status_code == 422
    assert "Insufficient" in str(exc.value.message)


def test_feature_builder_date_discontinuity_raises():
    """Verify error is raised if there is a gap in historical daily records."""
    pred_date = date(2024, 2, 1)
    target_obs = date(2024, 1, 31)

    records = []
    for i in range(35):
        # Introduce a gap between day 10 and 12
        if i == 10:
            continue
        d = target_obs - timedelta(days=34 - i)
        records.append(
            DailyWeatherRecord(
                date=d,
                latitude=19.0760,
                longitude=72.8777,
                PRECTOTCORR=1.0,
                T2M=25.0,
                T2MDEW=20.0,
                RH2M=60.0,
                PS=101.0,
                WS2M=2.0,
                WS10M=3.0,
                ALLSKY_SFC_SW_DWN=15.0,
            )
        )

    with pytest.raises(WeatherObservationValidationError) as exc:
        Model1FeatureBuilder.build_feature_vector(records, pred_date)
    assert "Discontinuity" in str(exc.value.message)
