"""Spatial risk assessment, evidence fusion, and explainability schemas."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator

from backend.app.schemas.common import Coordinates, GeoBoundingBox, Location


class RiskLevel(str, Enum):
    """Multi-source integrated flood risk levels (prototype decision thresholds)."""
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    EXTREME = "EXTREME"
    SEVERE = "EXTREME"


# ============================================================
# NORMALIZED EVIDENCE STRUCTURES
# ============================================================

class RainfallEvidence(BaseModel):
    """Normalized evidence from observational weather and Model 1 XGBoost inference."""
    heavy_rain_probability: float = Field(..., ge=0.0, le=1.0, description="Predicted heavy rainfall probability")
    heavy_rain_predicted: bool = Field(..., description="Binary classification (prob >= threshold)")
    model_threshold: float = Field(default=0.81, description="Frozen Model 1 decision threshold")
    observation_date: str = Field(..., description="Latest meteorological observation date used (D-1)")
    latest_precipitation_mm: float = Field(..., ge=0.0, description="Observed precipitation on D-1 in mm/day")
    historical_records_used: int = Field(default=30, ge=30, description="Historical lookback days")
    source: str = Field(default="NASA POWER + Model 1 XGBoost", description="Source pipeline identifier")
    available: bool = Field(default=True, description="Availability flag")


class NwpEvidence(BaseModel):
    """Normalized evidence from Numerical Weather Prediction (NOAA GFS via Open-Meteo)."""
    forecast_precipitation_mm_hr: float = Field(..., ge=0.0, description="Mean or current forecast precipitation in mm/hr")
    max_hourly_precipitation_mm_hr: float = Field(..., ge=0.0, description="Peak hourly rainfall intensity in mm/hr")
    accumulated_precipitation_mm: float = Field(..., ge=0.0, description="Accumulated rainfall over forecast horizon in mm")
    max_cape_j_kg: Optional[float] = Field(None, ge=0.0, description="Peak Convective Available Potential Energy in J/kg")
    forecast_horizon_hours: int = Field(default=24, gt=0, description="Analyzed forecast horizon in hours")
    forecast_start_time: Optional[str] = Field(None, description="ISO timestamp of first forecast step")
    forecast_end_time: Optional[str] = Field(None, description="ISO timestamp of final forecast step")
    source_model: str = Field(default="NOAA GFS 0.25° via Open-Meteo", description="NWP source and model identifier")
    available: bool = Field(default=True, description="Availability flag")


class RadarEvidence(BaseModel):
    """Normalized evidence from Doppler Weather Radar composite scan (RainViewer)."""
    max_reflectivity_dbz: float = Field(..., ge=0.0, le=95.0, description="Peak radar reflectivity in dBZ")
    mean_reflectivity_dbz: float = Field(..., ge=0.0, le=95.0, description="Mean active echo reflectivity in dBZ")
    active_echo_percentage: float = Field(..., ge=0.0, le=100.0, description="Spatial echo coverage percentage in radar tile")
    estimated_peak_rain_rate_mm_hr: float = Field(..., ge=0.0, description="Marshall-Palmer Z-R estimated peak rain rate in mm/hr")
    observation_timestamp: Optional[str] = Field(None, description="Observation timestamp of radar frame in UTC")
    source: str = Field(default="RainViewer Global Doppler Radar Composite", description="Radar data provider")
    available: bool = Field(default=True, description="Availability flag")


class SatelliteInundationEvidence(BaseModel):
    """Normalized evidence from Sentinel-2 multispectral imagery and Model 2 FloodUNet."""
    flooded_area_sq_km: float = Field(..., ge=0.0, description="Estimated inundated surface area in square kilometers")
    valid_area_sq_km: float = Field(..., gt=0.0, description="Total analyzed ground surface area in square kilometers")
    flooded_percentage: float = Field(..., ge=0.0, le=100.0, description="Inundation percentage of analyzed area")
    polygon_count: int = Field(..., ge=0, description="Number of vector inundation polygons detected")
    scene_id: Optional[str] = Field(None, description="Sentinel-2 Granule / Scene ID")
    scene_acquisition_datetime: Optional[str] = Field(None, description="Acquisition UTC timestamp")
    cloud_coverage_percentage: Optional[float] = Field(None, ge=0.0, le=100.0, description="Scene cloud coverage")
    model_threshold: float = Field(default=0.5, description="Model 2 FloodUNet decision threshold")
    temporal_status: str = Field(default="CURRENT", description="'CURRENT' (<48h), 'RECENT' (48-168h), or 'HISTORICAL' (>168h)")
    observation_age_hours: float = Field(default=0.0, ge=0.0, description="Observation age in hours relative to analysis time")
    source: str = Field(default="Sentinel-2 L2A via Element 84 Earth Search", description="Satellite imagery provider")
    available: bool = Field(default=True, description="Availability flag")

    @field_validator("scene_acquisition_datetime", mode="before")
    @classmethod
    def convert_dt_to_iso(cls, v: Any) -> Optional[str]:
        if v is None:
            return None
        if isinstance(v, datetime):
            return v.isoformat()
        return str(v)


# ============================================================
# EXPLAINABILITY & PROTOTYPE WARNING SCHEMAS
# ============================================================

class SourceExplanation(BaseModel):
    """Structured mathematical and physical explanation for an individual evidence stream."""
    source: str = Field(..., description="Stream key, e.g. 'heavy_rainfall_model', 'nwp_forecast'")
    name: str = Field(..., description="Human-readable source name")
    description: str = Field(..., description="Contextual physical explanation")
    raw_value: Any = Field(..., description="Observed physical value or key metric")
    normalized_score: float = Field(..., ge=0.0, le=1.0, description="Normalized risk contribution [0.0, 1.0]")
    original_weight: float = Field(..., ge=0.0, le=1.0, description="Configured static weight")
    effective_weight: float = Field(..., ge=0.0, le=1.0, description="Active normalized weight after missing-source policy")
    contribution: float = Field(..., ge=0.0, le=1.0, description="Effective weight multiplied by normalized score")
    timestamp: Optional[str] = Field(None, description="Observation or forecast timestamp")
    status: str = Field(default="available", description="'available', 'unavailable', or 'historical'")


class PrototypeWarningCandidate(BaseModel):
    """
    Structured prototype warning candidate assessment.
    Explicitly NOT an official IMD government weather warning.
    """
    risk_level: RiskLevel = Field(..., description="Derived prototype risk level")
    urgency: str = Field(..., description="'NONE', 'MONITOR', 'PREPARE', or 'ACTION'")
    trigger_reasons: List[str] = Field(default_factory=list, description="Specific criteria that triggered the risk score")
    recommended_monitoring: str = Field(..., description="Recommended observational monitoring cadence")
    disclaimer: str = Field(
        default="EXPERIMENTAL PROTOTYPE ASSESSMENT FOR SIH 2026 PS 26071. NOT AN OFFICIAL GOVERNMENT WARNING.",
        description="Mandatory disclaimer distinguishing prototype ML output from official IMD warnings",
    )


class FusionMetadata(BaseModel):
    """Provenance and policy application metadata for multi-source risk fusion."""
    policy_applied: str = Field(..., description="'FULL_EVIDENCE', 'PARTIAL_EVIDENCE', or 'INSUFFICIENT_EVIDENCE'")
    original_weights: Dict[str, float] = Field(..., description="Baseline configured weights summing to 1.0")
    effective_weights: Dict[str, float] = Field(..., description="Dynamically renormalized weights summing to 1.0")
    available_sources: List[str] = Field(..., description="List of successfully ingested sources")
    unavailable_sources: List[str] = Field(default_factory=list, description="List of unavailable or failed sources")
    freshness: Dict[str, Any] = Field(default_factory=dict, description="Age and timestamp metadata per source")


class RiskScoreDetail(BaseModel):
    """Composite risk score and level breakdown."""
    score: float = Field(..., ge=0.0, le=1.0, description="Deterministic composite multi-source risk score [0.0, 1.0]")
    level: RiskLevel = Field(..., description="Categorized risk level")
    thresholds: Dict[str, float] = Field(..., description="Configured risk category thresholds")


# ============================================================
# API CONTRACT SCHEMAS
# ============================================================

class RiskAssessmentRequest(BaseModel):
    """Request payload for multi-source risk assessment endpoint."""
    latitude: float = Field(..., ge=-90.0, le=90.0, description="Target latitude in decimal degrees")
    longitude: float = Field(..., ge=-180.0, le=180.0, description="Target longitude in decimal degrees")
    prediction_date: Optional[str] = Field(None, description="Target prediction date in YYYY-MM-DD format (default: today)")
    nwp_horizon_hours: Optional[int] = Field(default=24, ge=1, le=168, description="NWP forecast window in hours")
    satellite_max_cloud: Optional[float] = Field(default=25.0, ge=0.0, le=100.0, description="Max cloud coverage for Sentinel-2 discovery")
    location_name: Optional[str] = Field(None, description="Optional descriptive location name")


class RiskAssessmentResponse(BaseModel):
    """Complete response payload for POST /api/v1/predict/risk."""
    status: str = Field(default="success", description="Pipeline execution status")
    requested_location: Coordinates = Field(..., description="Coordinates analyzed")
    location_name: Optional[str] = Field(None, description="Descriptive location name")
    risk: RiskScoreDetail = Field(..., description="Composite risk score, level, and thresholds")
    evidence: Dict[str, Any] = Field(..., description="Normalized evidence from all available sources")
    fusion: FusionMetadata = Field(..., description="Weights, policy applied, and source availability metadata")
    explanations: List[SourceExplanation] = Field(..., description="Mathematical explainability decomposition")
    prototype_warning_assessment: PrototypeWarningCandidate = Field(..., description="Prototype warning candidate and triggers")
    generated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat(), description="UTC timestamp of assessment")


# ============================================================
# LEGACY BASELINE COMPATIBILITY SCHEMAS
# ============================================================

class RiskAssessment(BaseModel):
    """Integrated heavy rainfall and inundation risk score for a region (baseline schema)."""
    location: Location
    assessment_time: datetime
    overall_risk_level: RiskLevel
    rainfall_risk_score: float = Field(..., ge=0.0, le=1.0)
    inundation_risk_score: float = Field(..., ge=0.0, le=1.0)
    composite_risk_score: float = Field(..., ge=0.0, le=1.0)
    vulnerability_factors: Dict[str, float] = Field(
        default_factory=dict,
        description="Topographic, drainage, and urban density risk multipliers",
    )
    summary: str


class SpatialRiskGrid(BaseModel):
    """Gridded spatial risk assessment across a bounding box (baseline schema)."""
    bounding_box: GeoBoundingBox
    grid_resolution_km: float
    grid_shape: List[int]
    risk_level_matrix_uri: Optional[str] = None
