"""Satellite Precipitation Service interface."""

from datetime import datetime
from typing import List, Optional
from backend.app.schemas.common import Coordinates, GeoBoundingBox
from backend.app.schemas.satellite import SatellitePrecipitationObservation
from backend.app.services.base import BaseService


class SatellitePrecipitationService(BaseService):
    """
    Interface for satellite precipitation products (GPM IMERG / INSAT-3DR).
    Satellite precipitation feed is intentionally NOT CONNECTED yet.
    """

    def __init__(self):
        super().__init__(
            name="SatellitePrecipitationService",
            description="Gridded satellite precipitation products (GPM / INSAT)",
        )
        self._is_connected = False

    def check_connection(self) -> bool:
        return False

    def get_latest_precipitation(
        self, coordinates: Coordinates
    ) -> SatellitePrecipitationObservation:
        """Fetch latest satellite precipitation estimate at coordinates."""
        raise NotImplementedError(
            "Satellite precipitation feed is not yet connected. Fake precipitation data is strictly forbidden."
        )

    def get_gridded_precipitation(
        self, bounding_box: GeoBoundingBox, timestamp: Optional[datetime] = None
    ) -> List[SatellitePrecipitationObservation]:
        """Fetch spatial raster/grid of satellite precipitation estimates."""
        raise NotImplementedError(
            "Gridded satellite precipitation pipeline is not yet connected."
        )
