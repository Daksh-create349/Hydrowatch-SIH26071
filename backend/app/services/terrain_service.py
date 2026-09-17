"""Terrain and Elevation Service interface."""

from typing import Optional
from backend.app.schemas.common import Coordinates, GeoBoundingBox
from backend.app.services.base import BaseService


class TerrainService(BaseService):
    """
    Interface for Digital Elevation Model (DEM), slope, and terrain vulnerability factors.
    DEM data integration (Copernicus DEM / SRTM) is intentionally NOT CONNECTED yet.
    """

    def __init__(self):
        super().__init__(
            name="TerrainService",
            description="Topographic elevation, slope, and catchment vulnerability processing",
        )
        self._is_connected = False

    def check_connection(self) -> bool:
        return False

    def get_elevation_at_point(self, coordinates: Coordinates) -> float:
        """Fetch real elevation above sea level in meters."""
        raise NotImplementedError(
            "Terrain elevation provider is not yet connected. Fake elevation is strictly forbidden."
        )

    def get_dem_clip(self, bounding_box: GeoBoundingBox) -> str:
        """Extract DEM raster clip for target bounding box."""
        raise NotImplementedError(
            "DEM raster clipping pipeline is not yet connected."
        )
