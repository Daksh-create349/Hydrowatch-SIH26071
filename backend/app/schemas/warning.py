"""Early warning and advisory alert schemas."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from backend.app.schemas.common import Coordinates, Location
from backend.app.schemas.risk import RiskLevel, RiskScoreDetail


# ============================================================
# ENUMS & CONSTANTS
# ============================================================

class AlertSeverity(str, Enum):
    """IMD standard weather warning color codes."""
    GREEN = "green"    # No warning / normal
    YELLOW = "yellow"  # Be updated / watch
    ORANGE = "orange"  # Be prepared / alert
    RED = "red"        # Take action / warning


class WarningStatus(str, Enum):
    """Deterministic prototype warning status states."""
    NO_ALERT = "NO_ALERT"
    MONITOR = "MONITOR"
    PREPARE = "PREPARE"
    ACTION = "ACTION"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class WarningUrgency(str, Enum):
    """Warning operational urgency levels."""
    NONE = "NONE"
    MONITOR = "MONITOR"
    PREPARE = "PREPARE"
    ACTION = "ACTION"


# ============================================================
# STRUCTURED PHYSICAL TRIGGERS & FRESHNESS
# ============================================================

class PhysicalTrigger(BaseModel):
    """Structured concrete physical or model trigger."""
    source: str = Field(..., description="Evidence stream source key (e.g. radar_nowcast, heavy_rainfall_model)")
    metric: str = Field(..., description="Observed parameter name (e.g. max_reflectivity_dbz, heavy_rain_probability)")
    observed_value: Any = Field(..., description="Actual measured or predicted value")
    threshold: float = Field(..., description="Trigger decision threshold")
    triggered: bool = Field(..., description="True if observed value reached or exceeded threshold")
    unit: str = Field(..., description="Physical measurement unit")
    timestamp: Optional[str] = Field(None, description="Observation or forecast step timestamp")
    description: str = Field(..., description="Contextual physical explanation")


class EvidenceFreshness(BaseModel):
    """Temporal freshness disclosure across all ingested streams."""
    current_sources: List[str] = Field(default_factory=list, description="Sources with fresh observations (<= 48h)")
    stale_sources: List[str] = Field(default_factory=list, description="Sources with aged observations (48h - 168h)")
    historical_sources: List[str] = Field(default_factory=list, description="Sources with historical data (> 168h)")
    source_timestamps: Dict[str, Optional[str]] = Field(default_factory=dict, description="Latest timestamp per source")
    satellite_is_historical: bool = Field(default=False, description="Flag indicating satellite imagery is historical context")


class WarningProvenance(BaseModel):
    """Deterministic provenance tracking for warning decision."""
    risk_assessment_id: Optional[str] = Field(None, description="Reference risk assessment identifier")
    model_versions: Dict[str, str] = Field(..., description="Model 1 and Model 2 checkpoint versions")
    source_providers: Dict[str, str] = Field(..., description="Underlying environmental data providers")
    source_timestamps: Dict[str, Optional[str]] = Field(..., description="Timestamps of all input data")
    configured_thresholds: Dict[str, float] = Field(..., description="Active trigger threshold dictionary")
    configured_risk_weights: Dict[str, float] = Field(..., description="Risk fusion weights applied")
    rules_version: str = Field(default="v1.0_prototype_sih2026", description="Deterministic decision rules version")


# ============================================================
# WARNING DECISION CORE SCHEMAS
# ============================================================

class WarningDecision(BaseModel):
    """Structured warning decision body."""
    status: WarningStatus = Field(..., description="Warning decision state")
    risk_level: RiskLevel = Field(..., description="Composite risk level from fusion engine")
    urgency: WarningUrgency = Field(..., description="Derived operational urgency")
    triggered: bool = Field(..., description="True if any warning state other than NO_ALERT or INSUFFICIENT_DATA was triggered, or any physical trigger fired")
    trigger_reasons: List[str] = Field(default_factory=list, description="Human-readable concrete reasons")
    triggers: List[PhysicalTrigger] = Field(default_factory=list, description="Structured physical trigger evaluation")
    generated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat(), description="Decision UTC timestamp")
    valid_until: Optional[str] = Field(None, description="Forward validity timestamp (ISO 8601 UTC) or null if indefensible")
    validity_reason: str = Field(..., description="Physical justification for validity window or why null")
    prototype_only: bool = Field(default=True, description="Strictly true for all prototype outputs")
    official_warning_issued: bool = Field(default=False, description="Strictly false: not an official government warning")
    disclaimer: str = Field(
        default="EXPERIMENTAL PROTOTYPE ASSESSMENT FOR SIH 2026 PS 26071. NOT AN OFFICIAL IMD GOVERNMENT WARNING. NOT SANCTIONED FOR OFFICIAL EMERGENCY BROADCAST.",
        description="Mandatory disclaimer distinguishing prototype ML output from official IMD warnings",
    )
    escalation_notes: Optional[str] = Field(None, description="Disclosed discrepancy if a physical trigger materially exceeds composite score")


class WarningAssessmentRequest(BaseModel):
    """Request payload for POST /api/v1/predict/warning."""
    latitude: float = Field(..., ge=-90.0, le=90.0, description="Target latitude in decimal degrees")
    longitude: float = Field(..., ge=-180.0, le=180.0, description="Target longitude in decimal degrees")
    prediction_date: Optional[str] = Field(None, description="Target prediction date in YYYY-MM-DD format")
    nwp_horizon_hours: Optional[int] = Field(default=24, ge=1, le=168, description="NWP forecast window in hours")
    satellite_max_cloud: Optional[float] = Field(default=25.0, ge=0.0, le=100.0, description="Max cloud coverage for Sentinel-2 discovery")
    location_name: Optional[str] = Field(None, description="Optional descriptive location name")


class WarningDecisionResponse(BaseModel):
    """Complete response payload for POST /api/v1/predict/warning."""
    status: str = Field(default="success", description="Pipeline execution status")
    requested_location: Coordinates = Field(..., description="Target coordinates analyzed")
    location_name: Optional[str] = Field(None, description="Descriptive location name")
    risk: RiskScoreDetail = Field(..., description="Underlying composite risk details from fusion engine")
    warning: WarningDecision = Field(..., description="Deterministic warning decision details")
    evidence_freshness: EvidenceFreshness = Field(..., description="Data freshness and staleness disclosure")
    source_provenance: WarningProvenance = Field(..., description="Full mathematical and model provenance")
    supporting_evidence: Dict[str, Any] = Field(..., description="Normalized evidence from risk assessment")


# ============================================================
# LEGACY BASELINE COMPATIBILITY SCHEMAS
# ============================================================

class AlertAction(BaseModel):
    """Recommended action item for disaster management authorities or citizens."""
    priority: int = Field(..., ge=1, le=5)
    target_audience: str = Field(..., description="e.g., 'Public', 'Municipal Corporations', 'NDRF'")
    action: str


class WarningAlert(BaseModel):
    """Official early warning alert following IMD disaster management guidelines (baseline schema)."""
    alert_id: str
    issued_at: datetime
    valid_from: datetime
    valid_until: datetime
    location: Location
    severity: AlertSeverity
    headline: str
    description: str
    recommended_actions: List[AlertAction] = Field(default_factory=list)
