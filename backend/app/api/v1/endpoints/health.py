"""Health check endpoint."""

from datetime import datetime, timezone
from typing import Any, Dict, List
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from backend.app.core.config import Settings, get_settings
from backend.app.schemas.common import ServiceHealthStatus
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

router = APIRouter()


class HealthCheckResponse(BaseModel):
    """Structured health response body."""
    status: str = Field("healthy", description="Overall health status")
    environment: str
    version: str
    project: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    services: List[ServiceHealthStatus]
    model_assets: Dict[str, Any]


@router.get(
    "/health",
    response_model=HealthCheckResponse,
    summary="System and Service Health Check",
    description="Returns structured health status, model asset presence, and integration states.",
)
def get_health(settings: Settings = Depends(get_settings)) -> HealthCheckResponse:
    # Instantiate service checkers to inspect current status
    services = [
        WeatherObservationService(),
        NWPService(),
        RadarService(),
        SatellitePrecipitationService(),
        SatelliteImageryService(),
        TerrainService(),
        Model1Service(),
        Model2Service(),
        RiskFusionService(),
        WarningService(),
    ]

    service_statuses = [svc.get_health_status() for svc in services]

    m1 = Model1Service.get_instance()
    m2 = Model2Service.get_instance()

    model_assets = {
        "model1_heavy_rain_xgboost": {
            "configured_path": str(m1.model_path),
            "asset_found": m1.has_model_artifact(),
            "pipeline_status": "ready" if m1.is_loaded else "not_loaded",
        },
        "model2_flood_unet": {
            "configured_path": str(m2.model_path),
            "asset_found": m2.has_model_artifact(),
            "pipeline_status": "ready" if m2.is_loaded else "not_loaded",
        },
    }

    return HealthCheckResponse(
        status="healthy",
        environment=settings.ENVIRONMENT,
        version=settings.APP_VERSION,
        project=settings.PROJECT_NAME,
        services=service_statuses,
        model_assets=model_assets,
    )
