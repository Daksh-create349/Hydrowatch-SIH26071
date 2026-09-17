"""Unified end-to-end prediction schemas and contracts."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from backend.app.schemas.common import Coordinates
from backend.app.schemas.nwp import NWPForecastSummary
from backend.app.schemas.prediction import RainfallXaiSummary
from backend.app.schemas.risk import (
    FusionMetadata,
    RiskLevel,
    SourceExplanation,
)
from backend.app.schemas.warning import WarningDecision, WarningProvenance


class UnifiedPredictionRequest(BaseModel):
    """Request payload for unified end-to-end multi-source prediction."""
    latitude: float = Field(..., ge=-90.0, le=90.0, description="Target latitude in decimal degrees (-90 to 90)")
    longitude: float = Field(..., ge=-180.0, le=180.0, description="Target longitude in decimal degrees (-180 to 180)")
    prediction_date: Optional[str] = Field(None, description="Target prediction date in YYYY-MM-DD format (default: today)")
    analysis_datetime: Optional[str] = Field(None, description="Optional ISO 8601 UTC analysis timestamp")
    nwp_horizon_hours: Optional[int] = Field(default=24, ge=1, le=168, description="NWP forecast window in hours (1-168)")
    satellite_date: Optional[str] = Field(None, description="Target Sentinel-2 search date in YYYY-MM-DD format (default: latest)")
    satellite_max_cloud: Optional[float] = Field(default=25.0, ge=0.0, le=100.0, description="Max scene cloud percentage (0-100)")
    min_polygon_area_sq_m: Optional[float] = Field(default=500.0, ge=0.0, description="Minimum inundation polygon area in square meters")
    location_name: Optional[str] = Field(None, description="Optional descriptive location name")


class SourceStatusDetail(BaseModel):
    """Operational health, latency, and status for an individual environmental data stream."""
    available: bool = Field(..., description="Whether evidence stream was successfully ingested")
    status: str = Field(..., description="'success', 'unavailable', or 'failed'")
    source: str = Field(..., description="Provider or pipeline identifier")
    latency_ms: float = Field(..., description="Subtask execution duration in milliseconds")
    timestamp: Optional[str] = Field(None, description="Data acquisition or observation timestamp")
    error: Optional[str] = Field(None, description="Sanitized error description if stream failed")


class UnifiedRainfallSummary(BaseModel):
    """Summary of observational weather and Model 1 XGBoost heavy rainfall prediction."""
    probability: float = Field(..., ge=0.0, le=1.0, description="Predicted heavy rainfall probability [0.0, 1.0]")
    predicted: bool = Field(..., description="Binary classification (probability >= threshold)")
    threshold: float = Field(default=0.81, description="Applied Model 1 decision threshold (frozen at 0.81)")
    observation_date: str = Field(..., description="Latest meteorological observation date used (D-1)")
    model_version: str = Field(default="heavy_rainfall_xgboost_v2", description="Model 1 architecture")
    historical_records_used: int = Field(default=30, ge=30, description="Historical weather records used")
    latest_precipitation_mm: float = Field(..., ge=0.0, description="Observed precipitation on D-1 in mm/day")
    xai: Optional[RainfallXaiSummary] = Field(None, description="Explainable AI attribution decomposition for heavy rainfall")


class UnifiedNwpSummary(BaseModel):
    """Summary of Numerical Weather Prediction (NOAA GFS via Open-Meteo)."""
    source: str = Field(default="Open-Meteo GFS (NOAA 0.25° Seamless)", description="NWP provider")
    model_name: str = Field(default="GFS_0.25", description="Numerical model identifier")
    forecast_summary: NWPForecastSummary = Field(..., description="Horizon aggregate meteorological statistics")
    forecast_horizon_hours: int = Field(..., gt=0, description="Forecast duration in hours")
    valid_times: List[str] = Field(default_factory=list, description="Hourly forecast valid timestamps")
    peak_hourly_precipitation_mm_hr: float = Field(..., ge=0.0, description="Peak hourly rainfall intensity (mm/hr)")
    accumulated_precipitation_mm: float = Field(..., ge=0.0, description="Total accumulated rainfall over horizon (mm)")
    max_cape_j_kg: Optional[float] = Field(None, ge=0.0, description="Peak CAPE value (J/kg)")
    hourly_precipitation: List[float] = Field(default_factory=list, description="Chronological hourly forecast precipitation rates (mm/hr)")


class UnifiedRadarSummary(BaseModel):
    """Summary of Doppler Weather Radar observations (RainViewer)."""
    source: str = Field(default="RainViewer Global Doppler Radar Composite", description="Radar data provider")
    timestamp: Optional[str] = Field(None, description="Scan acquisition timestamp (ISO 8601 UTC)")
    max_reflectivity_dbz: float = Field(..., description="Peak observed radar reflectivity in dBZ")
    mean_reflectivity_dbz: float = Field(..., description="Mean active echo reflectivity in dBZ")
    estimated_rain_rate_mm_hr: float = Field(..., ge=0.0, description="Estimated peak rainfall rate (mm/hr)")
    coverage_percentage: float = Field(..., ge=0.0, le=100.0, description="Precipitation echo coverage percentage")
    tile_url: Optional[str] = Field(None, description="Direct HTTPS URI to radar raster tile")


class UnifiedInundationSummary(BaseModel):
    """Summary of Sentinel-2 multispectral imagery and Model 2 FloodUNet inundation."""
    source: str = Field(default="Sentinel-2 L2A via Element 84 Earth Search", description="Satellite provider")
    scene: Dict[str, Any] = Field(default_factory=dict, description="Metadata of analyzed Sentinel-2 scene")
    flooded_area_sq_km: float = Field(..., ge=0.0, description="Estimated inundated area in square kilometers")
    valid_area_sq_km: float = Field(..., ge=0.0, description="Total analyzed ground area in square kilometers")
    flooded_percentage: float = Field(..., ge=0.0, le=100.0, description="Percentage of valid ground area inundated")
    polygon_count: int = Field(..., ge=0, description="Number of vector inundation polygons detected")
    geojson: Dict[str, Any] = Field(..., description="WGS84 GeoJSON FeatureCollection of inundation polygons")


class UnifiedRiskSummary(BaseModel):
    """Multi-source integrated flood risk score and explainability."""
    score: float = Field(..., ge=0.0, le=1.0, description="Deterministic composite multi-source risk score [0.0, 1.0]")
    level: RiskLevel = Field(..., description="Categorized risk level (LOW, MODERATE, HIGH, EXTREME)")
    thresholds: Dict[str, float] = Field(..., description="Active risk category boundaries")
    fusion: FusionMetadata = Field(..., description="Fusion policy, weights, and source availability metadata")
    explanations: List[SourceExplanation] = Field(..., description="Explainability decomposition per source")


class UnifiedTimingDetail(BaseModel):
    """High-resolution timing breakdown across pipeline stages in milliseconds."""
    weather_model1_ms: float = Field(..., ge=0.0, description="NASA POWER + Model 1 execution time (ms)")
    nwp_ms: float = Field(..., ge=0.0, description="Open-Meteo GFS NWP execution time (ms)")
    radar_ms: float = Field(..., ge=0.0, description="RainViewer radar execution time (ms)")
    satellite_model2_ms: float = Field(..., ge=0.0, description="Sentinel-2 + Model 2 execution time (ms)")
    fusion_ms: float = Field(..., ge=0.0, description="Risk fusion execution time (ms)")
    warning_ms: float = Field(..., ge=0.0, description="Warning decision execution time (ms)")
    total_ms: float = Field(..., ge=0.0, description="Total end-to-end execution time (ms)")


class UnifiedPredictionResponse(BaseModel):
    """Complete unified multi-source prediction response for frontend consumption."""
    status: str = Field(default="success", description="Overall execution status")
    request: Dict[str, Any] = Field(..., description="Echo of input request parameters")
    generated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat(), description="UTC timestamp of response generation")
    rainfall_prediction: Optional[UnifiedRainfallSummary] = Field(None, description="Model 1 heavy rainfall prediction")
    nwp: Optional[UnifiedNwpSummary] = Field(None, description="NOAA GFS NWP forecast summary")
    radar: Optional[UnifiedRadarSummary] = Field(None, description="Doppler radar nowcast summary")
    inundation: Optional[UnifiedInundationSummary] = Field(None, description="Sentinel-2 Model 2 inundation and GeoJSON polygons")
    risk: UnifiedRiskSummary = Field(..., description="Composite risk score and mathematical explainability")
    warning: WarningDecision = Field(..., description="Deterministic warning decision, triggers, and disclaimer")
    source_status: Dict[str, SourceStatusDetail] = Field(..., description="Individual source availability and error details")
    timing: UnifiedTimingDetail = Field(..., description="Pipeline execution latency breakdown in milliseconds")
    provenance: WarningProvenance = Field(..., description="Complete model, source, and configuration provenance")
