"""Doppler Weather Radar (DWR) service with real RainViewer Composite integration."""

import logging
from typing import Optional
import httpx

from backend.app.core.config import Settings, get_settings
from backend.app.schemas.common import Coordinates, GeoBoundingBox
from backend.app.schemas.radar import RadarDataResponse, RadarObservation, RadarReflectivityGrid
from backend.app.services.base import BaseService
from backend.app.services.cache import cache
from backend.app.services.radar_client import RainViewerRadarClient

logger = logging.getLogger("rainfall_backend.services.RadarService")


class RadarService(BaseService):
    """
    Service for ingesting Doppler Weather Radar (DWR) reflectivity scans.
    Wired to RainViewer Global Doppler Radar Composite network.
    """

    def __init__(
        self,
        settings: Optional[Settings] = None,
        radar_client: Optional[RainViewerRadarClient] = None,
        http_client: Optional[httpx.AsyncClient] = None,
    ):
        super().__init__(
            name="RadarService",
            description="Doppler Weather Radar volume scans and reflectivity products via RainViewer",
        )
        self.settings = settings or get_settings()
        self.client = radar_client or RainViewerRadarClient(
            settings=self.settings,
            http_client=http_client,
        )
        # Dedicated raw on-premise IMD station antenna feed is not connected; public composite API is active
        self._is_connected = False

    def check_connection(self) -> bool:
        """Dedicated antenna hardware connection status."""
        return False

    def get_latest_radar_scan(self, radar_station_id: str) -> RadarObservation:
        """
        Direct Doppler radar antenna hardware telemetry feed is not connected.
        Raises NotImplementedError to strictly prevent returning fake radar values.
        Use async fetch_radar_composite() for live radar composite scans.
        """
        raise NotImplementedError(
            "Radar network data pipeline is not yet connected. Fake radar values are strictly forbidden."
        )

    def get_reflectivity_composite(
        self, bounding_box: GeoBoundingBox
    ) -> RadarReflectivityGrid:
        """Fetch gridded composite reflectivity (dBZ) product (deferred)."""
        raise NotImplementedError(
            "Radar reflectivity composite pipeline is not yet connected."
        )

    async def fetch_radar_composite(
        self,
        coordinates: Coordinates,
        zoom_level: int = 6,
        use_cache: bool = True,
    ) -> RadarDataResponse:
        """
        Fetch real Doppler radar reflectivity tile covering coordinates.
        Uses in-memory cache to prevent redundant raster downloads within a 5-minute window.
        """
        cache_key = f"radar:{coordinates.latitude:.3f}:{coordinates.longitude:.3f}:{zoom_level}"
        if use_cache:
            cached_data = cache.get(cache_key)
            if cached_data is not None:
                logger.debug("Serving cached radar tile for %s", cache_key)
                return cached_data

        result = await self.client.fetch_radar_composite(coordinates, zoom_level)
        if use_cache:
            cache.set(cache_key, result, ttl_seconds=300)

        return result
