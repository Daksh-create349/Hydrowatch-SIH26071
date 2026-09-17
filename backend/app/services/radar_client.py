"""Doppler Weather Radar (DWR) client for RainViewer Global Radar Composite API."""

import asyncio
from datetime import datetime, timezone
import io
import logging
import math
from typing import Any, Dict, List, Optional, Tuple
import httpx
import numpy as np
from PIL import Image

from backend.app.core.config import Settings, get_settings
from backend.app.core.errors import ExternalApiError, WeatherObservationValidationError
from backend.app.schemas.common import Coordinates, GeoBoundingBox
from backend.app.schemas.radar import (
    RadarDataResponse,
    RadarFrameMetadata,
    RadarTileReflectivity,
)

logger = logging.getLogger("rainfall_backend.services.RainViewerRadarClient")


def coordinates_to_tile(lat_deg: float, lon_deg: float, zoom: int) -> Tuple[int, int]:
    """Convert decimal latitude/longitude and zoom level to Slippy Map tile coordinates (x, y)."""
    n = 2.0 ** zoom
    x = int((lon_deg + 180.0) / 360.0 * n)
    lat_rad = math.radians(lat_deg)
    # Clip latitude to Web Mercator range [-85.0511, 85.0511]
    lat_rad = max(math.radians(-85.0511), min(math.radians(85.0511), lat_rad))
    y = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
    return x, y


def tile_to_bounding_box(x: int, y: int, zoom: int) -> GeoBoundingBox:
    """Calculate geographic bounding box (WGS84) for a Slippy Map tile (x, y, zoom)."""
    n = 2.0 ** zoom
    min_lon = (x / n) * 360.0 - 180.0
    max_lon = ((x + 1) / n) * 360.0 - 180.0
    max_lat = math.degrees(math.atan(math.sinh(math.pi * (1.0 - 2.0 * (y / n)))))
    min_lat = math.degrees(math.atan(math.sinh(math.pi * (1.0 - 2.0 * ((y + 1) / n)))))
    return GeoBoundingBox(
        min_lat=round(min_lat, 5),
        max_lat=round(max_lat, 5),
        min_lon=round(min_lon, 5),
        max_lon=round(max_lon, 5),
    )


class RainViewerRadarClient:
    """
    Asynchronous client for RainViewer Global Doppler Radar Composite API.
    Ingests live radar sweeps, decodes Web Mercator raster tiles, and extracts reflectivity statistics.
    """

    def __init__(
        self,
        settings: Optional[Settings] = None,
        http_client: Optional[httpx.AsyncClient] = None,
    ):
        self.settings = settings or get_settings()
        self.catalog_url = self.settings.RADAR_BASE_URL
        self.tile_base_url = self.settings.RADAR_TILE_BASE_URL
        self.timeout_seconds = self.settings.RADAR_TIMEOUT_SECONDS
        self.max_retries = self.settings.RADAR_MAX_RETRIES
        self._custom_http_client = http_client

    async def fetch_radar_composite(
        self,
        coordinates: Coordinates,
        zoom_level: int = 6,
    ) -> RadarDataResponse:
        """
        Fetch real Doppler Weather Radar composite covering coordinates at specified zoom level.

        Raises:
            ExternalApiError: If catalog or radar tile fetch fails.
            WeatherObservationValidationError: If tile decoding fails or coordinates are out of range.
        """
        zoom = max(0, min(14, zoom_level))

        # 1. Fetch temporal frame catalog
        catalog = await self._fetch_catalog()

        host = catalog.get("host", self.tile_base_url)
        radar_meta = catalog.get("radar", {})
        past_frames = radar_meta.get("past", [])

        if not past_frames:
            raise ExternalApiError(
                service_name="RAINVIEWER_RADAR",
                message="Radar frame catalog returned zero operational frames",
                status_code=502,
            )

        latest_frame = past_frames[-1]
        frame_time = latest_frame["time"]
        frame_path = latest_frame["path"]

        # 2. Compute tile coordinates and spatial bounds
        tile_x, tile_y = coordinates_to_tile(coordinates.latitude, coordinates.longitude, zoom)
        bbox = tile_to_bounding_box(tile_x, tile_y, zoom)

        # 3. Download radar reflectivity PNG tile
        tile_url = f"{host}{frame_path}/256/{zoom}/{tile_x}/{tile_y}/2/0_0.png"

        logger.info(
            "Fetching Doppler radar tile from %s (zoom=%d, x=%d, y=%d) for (%f, %f)",
            tile_url,
            zoom,
            tile_x,
            tile_y,
            coordinates.latitude,
            coordinates.longitude,
        )

        tile_bytes = await self._fetch_tile_bytes(tile_url)

        # 4. Decode PNG and calculate reflectivity statistics
        reflectivity_summary = self._decode_radar_tile(
            tile_bytes=tile_bytes,
            tile_url=tile_url,
            requested_coords=coordinates,
            bounding_box=bbox,
            zoom=zoom,
            tile_x=tile_x,
            tile_y=tile_y,
            frame_time=frame_time,
        )

        # Build recent scans list
        recent_scans = [
            RadarFrameMetadata(
                time=f["time"],
                timestamp_iso=datetime.fromtimestamp(f["time"], tz=timezone.utc).isoformat(),
                path=f["path"],
                frame_type="past",
            )
            for f in past_frames[-5:]
        ]

        return RadarDataResponse(
            status="success",
            source="RainViewer Global Doppler Radar Composite",
            latest_scan=reflectivity_summary,
            available_frames_count=len(past_frames),
            recent_scans=recent_scans,
            metadata={
                "tile_zoom": zoom,
                "tile_x": tile_x,
                "tile_y": tile_y,
                "temporal_resolution": "10 minutes",
                "color_scheme": "Universal 2 (dBZ scale)",
                "z_r_formula": "Marshall-Palmer Z = 200 * R^1.6",
            },
        )

    async def _fetch_catalog(self) -> Dict[str, Any]:
        """Fetch latest weather maps catalog with retries."""
        headers = {"User-Agent": f"SIH2026-RainfallBackend/{self.settings.APP_VERSION}"}
        last_exc: Optional[Exception] = None

        for attempt in range(1, self.max_retries + 1):
            try:
                if self._custom_http_client:
                    resp = await self._custom_http_client.get(
                        self.catalog_url,
                        headers=headers,
                        timeout=self.timeout_seconds,
                    )
                else:
                    async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                        resp = await client.get(self.catalog_url, headers=headers)

                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                last_exc = e
                if attempt < self.max_retries:
                    await asyncio.sleep(0.5 * (2 ** (attempt - 1)))

        raise ExternalApiError(
            service_name="RAINVIEWER_RADAR",
            message=f"Failed to fetch radar catalog after {self.max_retries} retries: {str(last_exc)}",
            status_code=502,
        )

    async def _fetch_tile_bytes(self, tile_url: str) -> bytes:
        """Download binary raster tile with retries."""
        headers = {"User-Agent": f"SIH2026-RainfallBackend/{self.settings.APP_VERSION}"}
        last_exc: Optional[Exception] = None

        for attempt in range(1, self.max_retries + 1):
            try:
                if self._custom_http_client:
                    resp = await self._custom_http_client.get(
                        tile_url,
                        headers=headers,
                        timeout=self.timeout_seconds,
                    )
                else:
                    async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                        resp = await client.get(tile_url, headers=headers)

                resp.raise_for_status()
                return resp.content
            except Exception as e:
                last_exc = e
                if attempt < self.max_retries:
                    await asyncio.sleep(0.5 * (2 ** (attempt - 1)))

        raise ExternalApiError(
            service_name="RAINVIEWER_RADAR",
            message=f"Failed to download radar tile from {tile_url}: {str(last_exc)}",
            status_code=502,
        )

    def _decode_radar_tile(
        self,
        tile_bytes: bytes,
        tile_url: str,
        requested_coords: Coordinates,
        bounding_box: GeoBoundingBox,
        zoom: int,
        tile_x: int,
        tile_y: int,
        frame_time: int,
    ) -> RadarTileReflectivity:
        """Decode RGBA tile bytes and extract reflectivity dBZ statistics."""
        try:
            img = Image.open(io.BytesIO(tile_bytes)).convert("RGBA")
        except Exception as img_err:
            raise WeatherObservationValidationError(
                f"Failed to decode radar tile PNG bytes: {str(img_err)}"
            ) from img_err

        arr = np.array(img, dtype=np.uint8)
        if arr.shape[0] != 256 or arr.shape[1] != 256:
            raise WeatherObservationValidationError(
                f"Unexpected radar tile dimensions: {arr.shape[:2]}, expected [256, 256]"
            )

        # Alpha channel denotes precipitation echo mask
        alpha = arr[:, :, 3]
        echo_mask = alpha > 0
        active_count = int(np.sum(echo_mask))
        total_pixels = 256 * 256
        coverage_pct = round((active_count / total_pixels) * 100.0, 3)

        if active_count == 0:
            max_dbz = 0.0
            mean_dbz = 0.0
            est_rain_rate = 0.0
        else:
            # Color intensity in scheme 2 maps reflectivity from 5 to 75 dBZ
            rgb = arr[:, :, :3]
            intensities = rgb[echo_mask].mean(axis=1) / 255.0
            dbz_values = 5.0 + intensities * 70.0
            max_dbz = round(float(np.max(dbz_values)), 1)
            mean_dbz = round(float(np.mean(dbz_values)), 1)

            # Marshall-Palmer relation: Z = 200 * R^1.6 => R = (Z / 200)^(1 / 1.6)
            z_factor = 10.0 ** (max_dbz / 10.0)
            est_rain_rate = round(float((z_factor / 200.0) ** (1.0 / 1.6)), 2)

        iso_time = datetime.fromtimestamp(frame_time, tz=timezone.utc).isoformat()

        return RadarTileReflectivity(
            source="RainViewer Global Doppler Radar Composite",
            radar_product="DWR_MAXZ_COMPOSITE",
            timestamp_iso=iso_time,
            unix_timestamp=frame_time,
            requested_coordinates=requested_coords,
            bounding_box=bounding_box,
            zoom_level=zoom,
            tile_x=tile_x,
            tile_y=tile_y,
            dimensions=[256, 256],
            total_tile_pixels=total_pixels,
            active_echo_pixels=active_count,
            echo_coverage_pct=coverage_pct,
            max_reflectivity_dbz=max_dbz,
            mean_reflectivity_dbz=mean_dbz,
            estimated_max_rain_rate_mm_hr=est_rain_rate,
            reflectivity_scale="5 to 75 dBZ (Marshall-Palmer Z=200*R^1.6)",
            tile_url=tile_url,
        )
