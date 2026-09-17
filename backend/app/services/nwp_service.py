"""Numerical Weather Prediction (NWP) service with real Open-Meteo NOAA GFS integration."""

import logging
from typing import List, Optional
import httpx

from backend.app.core.config import Settings, get_settings
from backend.app.schemas.common import Coordinates, GeoBoundingBox
from backend.app.schemas.nwp import NWPForecast, NWPGridData, NWPPointForecastResponse
from backend.app.services.base import BaseService
from backend.app.services.cache import cache
from backend.app.services.nwp_client import OpenMeteoNwpClient

logger = logging.getLogger("rainfall_backend.services.NWPService")


class NWPService(BaseService):
    """
    Service for ingesting Numerical Weather Prediction model runs.
    Wired to Open-Meteo GFS (NOAA Global Forecast System 0.25° grid).
    """

    def __init__(
        self,
        settings: Optional[Settings] = None,
        nwp_client: Optional[OpenMeteoNwpClient] = None,
        http_client: Optional[httpx.AsyncClient] = None,
    ):
        super().__init__(
            name="NWPService",
            description="Numerical Weather Prediction model forecast ingestion via Open-Meteo NOAA GFS",
        )
        self.settings = settings or get_settings()
        self.client = nwp_client or OpenMeteoNwpClient(
            settings=self.settings,
            http_client=http_client,
        )
        # In-situ dedicated GFS/NCUM cluster connection is not active; public API feed is operational
        self._is_connected = False

    def check_connection(self) -> bool:
        """Dedicated operational cluster feed status."""
        return False

    def get_forecast_for_point(
        self, coordinates: Coordinates, forecast_horizon_hours: int = 24
    ) -> List[NWPForecast]:
        """
        Synchronous direct telemetry ingestion is not connected.
        Raises NotImplementedError to strictly prevent returning fake forecast data.
        Use async fetch_point_forecast() for live NWP forecasts.
        """
        raise NotImplementedError(
            "Synchronous direct NWP cluster feed is not yet connected. "
            "Use async fetch_point_forecast() for real Open-Meteo NOAA GFS forecasts. "
            "Fake forecasts are strictly forbidden."
        )

    def get_forecast_grid(
        self, bounding_box: GeoBoundingBox, lead_hours: int = 24
    ) -> NWPGridData:
        """Fetch real NWP gridded precipitation and atmospheric fields (deferred)."""
        raise NotImplementedError(
            "NWP gridded forecast binary pipeline is not yet connected."
        )

    async def fetch_point_forecast(
        self,
        coordinates: Coordinates,
        forecast_days: int = 3,
        use_cache: bool = True,
    ) -> NWPPointForecastResponse:
        """
        Fetch real NWP atmospheric forecast for coordinates over forecast_days horizon.
        Uses in-memory cache to prevent redundant queries within a 10-minute window.
        """
        cache_key = f"nwp:{coordinates.latitude:.4f}:{coordinates.longitude:.4f}:{forecast_days}"
        if use_cache:
            cached_data = cache.get(cache_key)
            if cached_data is not None:
                logger.debug("Serving cached NWP forecast for %s", cache_key)
                return cached_data

        result = await self.client.fetch_point_forecast(coordinates, forecast_days)
        if use_cache:
            cache.set(cache_key, result, ttl_seconds=600)

        return result
