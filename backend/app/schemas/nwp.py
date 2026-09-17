"""Numerical Weather Prediction (NWP) schemas and data contracts."""

from datetime import datetime
import math
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator
from backend.app.schemas.common import Coordinates, GeoBoundingBox


class NWPForecastItem(BaseModel):
    """Hourly forecast record from NWP model."""
    valid_time: str = Field(..., description="Forecast valid timestamp (ISO 8601 UTC)")
    lead_hours: int = Field(..., ge=0, description="Forecast lead time in hours from run issuance")
    precipitation_mm_hr: float = Field(..., ge=0.0, description="Precipitation rate in mm/hour")
    temperature_2m_c: float = Field(..., description="Air temperature at 2m in Celsius")
    relative_humidity_pct: float = Field(..., ge=0.0, le=100.0, description="Relative humidity at 2m (%)")
    dew_point_2m_c: float = Field(..., description="Dew point temperature at 2m in Celsius")
    surface_pressure_hpa: float = Field(..., gt=0.0, description="Surface atmospheric pressure in hPa")
    surface_pressure_kpa: float = Field(..., gt=0.0, description="Surface atmospheric pressure in kPa")
    wind_speed_10m_ms: float = Field(..., ge=0.0, description="Wind speed at 10m in m/s")
    cape_j_kg: Optional[float] = Field(None, ge=0.0, description="Convective Available Potential Energy in J/kg")

    @field_validator("precipitation_mm_hr", "temperature_2m_c", "surface_pressure_hpa", "wind_speed_10m_ms", mode="before")
    @classmethod
    def validate_finite(cls, v: Any) -> float:
        if v is None:
            return 0.0
        val = float(v)
        if not math.isfinite(val):
            raise ValueError(f"Numeric forecast field must be finite, got: {val}")
        return val


class NWPForecastSummary(BaseModel):
    """Aggregate meteorological summary over forecast horizon."""
    total_precipitation_mm: float = Field(..., ge=0.0, description="Accumulated rainfall over forecast horizon (mm)")
    max_hourly_precipitation_mm_hr: float = Field(..., ge=0.0, description="Peak 1-hour rainfall intensity (mm/hr)")
    min_temperature_c: float = Field(..., description="Minimum forecast temperature (°C)")
    max_temperature_c: float = Field(..., description="Maximum forecast temperature (°C)")
    max_wind_speed_ms: float = Field(..., ge=0.0, description="Maximum wind speed (m/s)")
    max_cape_j_kg: Optional[float] = Field(None, ge=0.0, description="Peak CAPE value (J/kg)")


class NWPPointForecastResponse(BaseModel):
    """Normalized response payload for point NWP forecast queries."""
    status: str = Field(default="success", description="Query status")
    source: str = Field(default="Open-Meteo GFS (NOAA 0.25° Seamless)", description="NWP data provider")
    model_name: str = Field(default="GFS_0.25", description="Numerical model identifier")
    coordinates: Coordinates = Field(..., description="Requested geographic coordinates")
    elevation_m: Optional[float] = Field(None, description="Grid point elevation in meters")
    generated_at: str = Field(..., description="Timestamp when forecast was ingested/served (UTC)")
    forecast_horizon_hours: int = Field(..., gt=0, description="Total forecast lead duration in hours")
    forecast_count: int = Field(..., gt=0, description="Count of hourly forecast intervals")
    units: Dict[str, str] = Field(..., description="Physical measurement units dictionary")
    summary: NWPForecastSummary = Field(..., description="Horizon aggregate statistics")
    forecasts: List[NWPForecastItem] = Field(..., description="Chronological hourly forecast time series")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Model provenance and resolution metadata")


class NWPForecast(BaseModel):
    """Point-specific NWP forecast entry (foundation schema)."""
    model_name: str = Field(..., description="NWP model name, e.g. GFS, NCUM, WRF")
    issued_at: datetime = Field(..., description="Run issuance timestamp in UTC")
    forecast_for: datetime = Field(..., description="Forecast valid timestamp in UTC")
    lead_hours: int = Field(..., ge=0, description="Lead time in hours")
    coordinates: Coordinates = Field(..., description="Forecast point coordinates")
    precipitation_rate_mm_hr: Optional[float] = Field(None, ge=0.0)
    accumulated_precipitation_mm: Optional[float] = Field(None, ge=0.0)
    temperature_2m_c: Optional[float] = None
    wind_speed_10m_ms: Optional[float] = None
    convective_available_potential_energy_cape: Optional[float] = None


class NWPGridData(BaseModel):
    """Spatial grid metadata and data reference for NWP outputs."""
    model_name: str
    issued_at: datetime
    forecast_for: datetime
    lead_hours: int
    bounding_box: GeoBoundingBox
    grid_resolution_deg: float = Field(..., gt=0.0, description="Resolution in decimal degrees")
    variable_names: List[str] = Field(default_factory=list)
    grid_shape: List[int] = Field(..., description="[height, width] shape of grid")
    data_uri: Optional[str] = Field(None, description="Path or URI to raster/grid binary")
