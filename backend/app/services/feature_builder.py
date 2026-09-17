"""Model 1 exact 37-feature builder with temporal leakage prevention."""

from datetime import date, timedelta
import logging
import math
from typing import Dict, List, Optional
import numpy as np

from backend.app.core.errors import (
    InsufficientHistoricalDataError,
    WeatherObservationValidationError,
)
from backend.app.schemas.common import Coordinates
from backend.app.schemas.weather import DailyWeatherRecord, WeatherFeatureVector
from backend.app.services.model1_service import MODEL1_FEATURE_ORDER

logger = logging.getLogger("rainfall_backend.services.Model1FeatureBuilder")


class Model1FeatureBuilder:
    """
    Constructs the exact 37 meteorological features required by Model 1 (XGBoost).
    
    Temporal Rules:
    - Target prediction date: D
    - Latest observation date: D - 1
    - Zero future leakage: Any record with date >= D is strictly excluded.
    - Historical lookback: Requires at least 30 continuous daily records ending on D - 1.
    """

    MIN_REQUIRED_DAYS: int = 30

    @classmethod
    def build_feature_vector(
        cls,
        records: List[DailyWeatherRecord],
        prediction_date: date,
        coordinates: Optional[Coordinates] = None,
    ) -> WeatherFeatureVector:
        """
        Build exact 37-feature vector for prediction_date D using historical records through D-1.
        
        Raises:
            InsufficientHistoricalDataError: If fewer than 30 continuous daily records exist through D-1.
            WeatherObservationValidationError: If latest observation is not D-1 or records contain gaps.
        """
        target_obs_date = prediction_date - timedelta(days=1)

        # 1. Enforce zero future leakage: strictly filter records to date <= D-1
        valid_history = [r for r in records if r.date <= target_obs_date]
        valid_history.sort(key=lambda r: r.date)

        if not valid_history:
            raise InsufficientHistoricalDataError(
                message=f"No meteorological observations available on or before {target_obs_date}",
                required_days=cls.MIN_REQUIRED_DAYS,
                available_days=0,
            )

        # 2. Check latest available observation date
        latest_record = valid_history[-1]
        if latest_record.date != target_obs_date:
            raise InsufficientHistoricalDataError(
                message=(
                    f"Latest available weather record is {latest_record.date}, but target observation "
                    f"date (D-1) for prediction date {prediction_date} is {target_obs_date}."
                ),
                required_days=cls.MIN_REQUIRED_DAYS,
                available_days=len(valid_history),
                details={
                    "prediction_date": str(prediction_date),
                    "target_observation_date": str(target_obs_date),
                    "latest_record_date": str(latest_record.date),
                },
            )

        # 3. Check sufficient count
        if len(valid_history) < cls.MIN_REQUIRED_DAYS:
            raise InsufficientHistoricalDataError(
                message=(
                    f"Insufficient weather history. Required at least {cls.MIN_REQUIRED_DAYS} daily "
                    f"records ending on {target_obs_date}, got {len(valid_history)}."
                ),
                required_days=cls.MIN_REQUIRED_DAYS,
                available_days=len(valid_history),
            )

        # 4. Take the last 30 records ending on D-1 and verify continuous daily sequence
        window = valid_history[-cls.MIN_REQUIRED_DAYS :]
        for i in range(1, len(window)):
            day_diff = (window[i].date - window[i - 1].date).days
            if day_diff != 1:
                raise WeatherObservationValidationError(
                    f"Discontinuity in weather history between {window[i-1].date} and {window[i].date} (gap of {day_diff} days)",
                    details={
                        "missing_range": [str(window[i - 1].date), str(window[i].date)],
                        "gap_days": day_diff,
                    },
                )

        # Coordinates
        lat = coordinates.latitude if coordinates else latest_record.latitude
        lon = coordinates.longitude if coordinates else latest_record.longitude

        # Extract values:
        # window[-1] is D-1 (t0)
        # window[-2] is D-2 (lag 1d)
        # window[-3] is D-3 (lag 2d)
        # window[-4] is D-4 (lag 3d)
        # window[-8] is D-8 (lag 7d)
        # window[-15] is D-15 (lag 14d)
        t0 = window[-1]
        t_minus_1 = window[-2]
        t_minus_2 = window[-3]
        t_minus_3 = window[-4]
        t_minus_7 = window[-8]
        t_minus_14 = window[-15]

        rain_series = [r.PRECTOTCORR for r in window]

        # Rolling calculations ending on D-1
        rain_sum_3d = float(np.sum(rain_series[-3:]))
        rain_sum_7d = float(np.sum(rain_series[-7:]))
        rain_sum_14d = float(np.sum(rain_series[-14:]))
        rain_sum_30d = float(np.sum(rain_series[-30:]))
        rain_mean_7d = float(np.mean(rain_series[-7:]))
        rain_max_7d = float(np.max(rain_series[-7:]))

        # 1-day temporal differences
        temp_change_1d = float(t0.T2M - t_minus_1.T2M)
        humid_change_1d = float(t0.RH2M - t_minus_1.RH2M)
        press_change_1d = float(t0.PS - t_minus_1.PS)
        wind_change_1d = float(t0.WS2M - t_minus_1.WS2M)

        # Cyclical calendar features for observation date (D-1)
        obs_month = target_obs_date.month
        month_sin = float(np.sin(2.0 * np.pi * obs_month / 12.0))
        month_cos = float(np.cos(2.0 * np.pi * obs_month / 12.0))

        obs_doy = target_obs_date.timetuple().tm_yday
        doy_sin = float(np.sin(2.0 * np.pi * obs_doy / 365.25))
        doy_cos = float(np.cos(2.0 * np.pi * obs_doy / 365.25))

        feature_map: Dict[str, float] = {
            # 1-8: Base variables at D-1
            "PRECTOTCORR": float(t0.PRECTOTCORR),
            "T2M": float(t0.T2M),
            "T2MDEW": float(t0.T2MDEW),
            "RH2M": float(t0.RH2M),
            "PS": float(t0.PS),
            "WS2M": float(t0.WS2M),
            "WS10M": float(t0.WS10M),
            "ALLSKY_SFC_SW_DWN": float(t0.ALLSKY_SFC_SW_DWN),
            # 9-13: Precipitation lags
            "rain_lag_1d": float(t_minus_1.PRECTOTCORR),
            "rain_lag_2d": float(t_minus_2.PRECTOTCORR),
            "rain_lag_3d": float(t_minus_3.PRECTOTCORR),
            "rain_lag_7d": float(t_minus_7.PRECTOTCORR),
            "rain_lag_14d": float(t_minus_14.PRECTOTCORR),
            # 14-19: Rolling precipitation statistics
            "rain_sum_prev_3d": round(rain_sum_3d, 4),
            "rain_sum_prev_7d": round(rain_sum_7d, 4),
            "rain_sum_prev_14d": round(rain_sum_14d, 4),
            "rain_sum_prev_30d": round(rain_sum_30d, 4),
            "rain_mean_prev_7d": round(rain_mean_7d, 4),
            "rain_max_prev_7d": round(rain_max_7d, 4),
            # 20-26: Atmospheric 1-day lags
            "T2M_lag_1d": float(t_minus_1.T2M),
            "T2MDEW_lag_1d": float(t_minus_1.T2MDEW),
            "RH2M_lag_1d": float(t_minus_1.RH2M),
            "PS_lag_1d": float(t_minus_1.PS),
            "WS2M_lag_1d": float(t_minus_1.WS2M),
            "WS10M_lag_1d": float(t_minus_1.WS10M),
            "ALLSKY_SFC_SW_DWN_lag_1d": float(t_minus_1.ALLSKY_SFC_SW_DWN),
            # 27-30: 1-day temporal differences
            "temperature_change_1d": round(temp_change_1d, 4),
            "humidity_change_1d": round(humid_change_1d, 4),
            "pressure_change_1d": round(press_change_1d, 4),
            "wind_change_1d": round(wind_change_1d, 4),
            # 31-35: Calendar encodings
            "month": obs_month,
            "month_sin": round(month_sin, 6),
            "month_cos": round(month_cos, 6),
            "doy_sin": round(doy_sin, 6),
            "doy_cos": round(doy_cos, 6),
            # 36-37: Coordinates
            "latitude": float(lat),
            "longitude": float(lon),
        }

        # Verify all 37 features are populated
        for expected_feature in MODEL1_FEATURE_ORDER:
            if expected_feature not in feature_map:
                raise ValueError(f"Feature builder failed to compute required feature: '{expected_feature}'")

        return WeatherFeatureVector(**feature_map)
