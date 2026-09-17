"""Domain services and data integration interfaces."""

from backend.app.services.base import BaseService
from backend.app.services.cache import DataCache, cache
from backend.app.services.feature_builder import Model1FeatureBuilder
from backend.app.services.model1_service import Model1Service
from backend.app.services.model2_service import Model2Service
from backend.app.services.nasa_power_client import NasaPowerClient
from backend.app.services.nwp_client import OpenMeteoNwpClient
from backend.app.services.nwp_service import NWPService
from backend.app.services.radar_client import RainViewerRadarClient
from backend.app.services.radar_service import RadarService
from backend.app.services.risk_assessment_service import RiskAssessmentService
from backend.app.services.risk_fusion_service import RiskFusionService
from backend.app.services.satellite_imagery_service import SatelliteImageryService
from backend.app.services.satellite_precip_service import SatellitePrecipitationService
from backend.app.services.terrain_service import TerrainService
from backend.app.services.warning_service import WarningService
from backend.app.services.weather_service import WeatherObservationService

__all__ = [
    "BaseService",
    "DataCache",
    "Model1FeatureBuilder",
    "Model1Service",
    "Model2Service",
    "NasaPowerClient",
    "NWPService",
    "OpenMeteoNwpClient",
    "RadarService",
    "RainViewerRadarClient",
    "RiskAssessmentService",
    "RiskFusionService",
    "SatelliteImageryService",
    "SatellitePrecipitationService",
    "TerrainService",
    "WarningService",
    "WeatherObservationService",
    "cache",
]
