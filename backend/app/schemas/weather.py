"""Weather observation and feature schemas."""

from datetime import date as dt_date, datetime
import math
from typing import Optional
from pydantic import BaseModel, Field, field_validator, model_validator
from backend.app.schemas.common import Coordinates


class DailyWeatherRecord(BaseModel):
    """
    Daily meteorological record containing NASA POWER core variables.
    Strictly validates finite values and rejects sentinel missing values (-999.0).
    """
    date: dt_date = Field(..., description="Observation calendar date (UTC)")
    latitude: float = Field(..., ge=-90.0, le=90.0, description="Latitude in decimal degrees")
    longitude: float = Field(..., ge=-180.0, le=180.0, description="Longitude in decimal degrees")

    PRECTOTCORR: float = Field(..., ge=0.0, description="Precipitation corrected (mm/day)")
    T2M: float = Field(..., description="Temperature at 2m (°C)")
    T2MDEW: float = Field(..., description="Dew/Frost point at 2m (°C)")
    RH2M: float = Field(..., ge=0.0, le=100.0, description="Relative humidity at 2m (%)")
    PS: float = Field(..., gt=0.0, description="Surface pressure (kPa)")
    WS2M: float = Field(..., ge=0.0, description="Wind speed at 2m (m/s)")
    WS10M: float = Field(..., ge=0.0, description="Wind speed at 10m (m/s)")
    ALLSKY_SFC_SW_DWN: float = Field(..., ge=0.0, description="All sky surface shortwave downward irradiance (MJ/m²/day)")

    @field_validator(
        "PRECTOTCORR",
        "T2M",
        "T2MDEW",
        "RH2M",
        "PS",
        "WS2M",
        "WS10M",
        "ALLSKY_SFC_SW_DWN",
        mode="before",
    )
    @classmethod
    def validate_numeric_finite(cls, value: float) -> float:
        if value is None:
            raise ValueError("Meteorological parameter value cannot be None")
        try:
            val = float(value)
        except (TypeError, ValueError):
            raise ValueError(f"Invalid numeric meteorological parameter value: {value}")
        if not math.isfinite(val):
            raise ValueError(f"Meteorological parameter must be finite, got: {val}")
        if val in (-999.0, -999, -99.0):
            raise ValueError(f"Meteorological parameter contains missing/sentinel value: {val}")
        return val


class WeatherObservation(BaseModel):
    """Raw weather observation from surface weather station or automated weather station (AWS)."""
    station_id: Optional[str] = Field(None, description="Station identifier if applicable")
    timestamp: datetime = Field(..., description="Observation timestamp in UTC")
    coordinates: Coordinates = Field(..., description="Station or grid point coordinates")
    precipitation_mm: Optional[float] = Field(None, ge=0.0, description="Precipitation in mm")
    temperature_c: Optional[float] = Field(None, description="Air temperature at 2m (Celsius)")
    dew_point_c: Optional[float] = Field(None, description="Dew point temperature at 2m (Celsius)")
    relative_humidity_pct: Optional[float] = Field(None, ge=0.0, le=100.0, description="Relative humidity %")
    surface_pressure_kpa: Optional[float] = Field(None, gt=0.0, description="Surface pressure in kPa")
    wind_speed_2m_ms: Optional[float] = Field(None, ge=0.0, description="Wind speed at 2m in m/s")
    wind_speed_10m_ms: Optional[float] = Field(None, ge=0.0, description="Wind speed at 10m in m/s")
    solar_radiation_w_m2: Optional[float] = Field(None, ge=0.0, description="Solar downward shortwave radiation (W/m²)")



class WeatherFeatureVector(BaseModel):
    """
    Leakage-safe 37-feature meteorological input vector for Model 1 (XGBoost).
    Matches feature specifications from best_heavy_rain_xgboost_v2.json.
    """
    # Base atmospheric variables
    PRECTOTCORR: float = Field(..., description="Precipitation corrected (mm/day)")
    T2M: float = Field(..., description="Temperature at 2m (°C)")
    T2MDEW: float = Field(..., description="Dew/Frost point at 2m (°C)")
    RH2M: float = Field(..., description="Relative humidity at 2m (%)")
    PS: float = Field(..., description="Surface pressure (kPa)")
    WS2M: float = Field(..., description="Wind speed at 2m (m/s)")
    WS10M: float = Field(..., description="Wind speed at 10m (m/s)")
    ALLSKY_SFC_SW_DWN: float = Field(..., description="All sky surface shortwave downward irradiance (MJ/m²/day)")

    # Precipitation lag features
    rain_lag_1d: float = Field(..., description="Precipitation lag 1 day (mm)")
    rain_lag_2d: float = Field(..., description="Precipitation lag 2 days (mm)")
    rain_lag_3d: float = Field(..., description="Precipitation lag 3 days (mm)")
    rain_lag_7d: float = Field(..., description="Precipitation lag 7 days (mm)")
    rain_lag_14d: float = Field(..., description="Precipitation lag 14 days (mm)")

    # Rolling precipitation sums & statistics
    rain_sum_prev_3d: float = Field(..., description="Sum of precipitation past 3 days (mm)")
    rain_sum_prev_7d: float = Field(..., description="Sum of precipitation past 7 days (mm)")
    rain_sum_prev_14d: float = Field(..., description="Sum of precipitation past 14 days (mm)")
    rain_sum_prev_30d: float = Field(..., description="Sum of precipitation past 30 days (mm)")
    rain_mean_prev_7d: float = Field(..., description="Mean precipitation past 7 days (mm)")
    rain_max_prev_7d: float = Field(..., description="Max daily precipitation past 7 days (mm)")

    # 1-day lag features for atmospheric parameters
    T2M_lag_1d: float = Field(..., description="Temperature lag 1 day")
    T2MDEW_lag_1d: float = Field(..., description="Dew point lag 1 day")
    RH2M_lag_1d: float = Field(..., description="Relative humidity lag 1 day")
    PS_lag_1d: float = Field(..., description="Surface pressure lag 1 day")
    WS2M_lag_1d: float = Field(..., description="Wind speed 2m lag 1 day")
    WS10M_lag_1d: float = Field(..., description="Wind speed 10m lag 1 day")
    ALLSKY_SFC_SW_DWN_lag_1d: float = Field(..., description="Radiation lag 1 day")

    # 1-day temporal difference features
    temperature_change_1d: float = Field(..., description="T2M - T2M_lag_1d")
    humidity_change_1d: float = Field(..., description="RH2M - RH2M_lag_1d")
    pressure_change_1d: float = Field(..., description="PS - PS_lag_1d")
    wind_change_1d: float = Field(..., description="WS2M - WS2M_lag_1d")

    # Calendar and cyclical encodings
    month: int = Field(..., ge=1, le=12, description="Month of year (1-12)")
    month_sin: float = Field(..., description="Sine encoding of month")
    month_cos: float = Field(..., description="Cosine encoding of month")
    doy_sin: float = Field(..., description="Sine encoding of day of year")
    doy_cos: float = Field(..., description="Cosine encoding of day of year")

    # Geospatial coordinates
    latitude: float = Field(..., ge=-90.0, le=90.0, description="Latitude")
    longitude: float = Field(..., ge=-180.0, le=180.0, description="Longitude")
