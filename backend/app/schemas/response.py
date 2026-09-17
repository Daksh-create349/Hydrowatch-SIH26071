"""Unified API response schemas."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from backend.app.schemas.common import DataSourceStatus, Location
from backend.app.schemas.prediction import InundationPrediction, RainfallPrediction
from backend.app.schemas.risk import RiskAssessment
from backend.app.schemas.warning import WarningAlert


class BaseApiResponse(BaseModel):
    """Standard generic wrapper for API responses."""
    success: bool = True
    message: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    data: Optional[Any] = None


class AnalysisResponse(BaseModel):
    """Unified analysis response combining predictions, spatial risk, and warnings."""
    request_id: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    location: Location
    rainfall_prediction: Optional[RainfallPrediction] = None
    inundation_prediction: Optional[InundationPrediction] = None
    risk_assessment: Optional[RiskAssessment] = None
    warnings: List[WarningAlert] = Field(default_factory=list)
    data_sources: List[DataSourceStatus] = Field(
        default_factory=list,
        description="Audit trace of data source statuses utilized during analysis",
    )
    metadata: Dict[str, Any] = Field(default_factory=dict)
