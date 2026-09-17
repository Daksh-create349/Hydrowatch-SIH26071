"""Unit tests for RainViewer Doppler Weather Radar client and service."""

import io
import numpy as np
from PIL import Image
import pytest
import httpx

from backend.app.core.errors import ExternalApiError, WeatherObservationValidationError
from backend.app.schemas.common import Coordinates
from backend.app.services.cache import cache
from backend.app.services.radar_client import (
    RainViewerRadarClient,
    coordinates_to_tile,
    tile_to_bounding_box,
)
from backend.app.services.radar_service import RadarService


def generate_mock_radar_png(has_echoes: bool = True) -> bytes:
    """Generate in-memory 256x256 RGBA PNG tile."""
    arr = np.zeros((256, 256, 4), dtype=np.uint8)
    if has_echoes:
        # Create a synthetic circular storm cell with reflectivity
        y, x = np.ogrid[:256, :256]
        mask = (x - 128) ** 2 + (y - 128) ** 2 <= 50 ** 2
        arr[mask, 0] = 255  # Red
        arr[mask, 1] = 128  # Orange
        arr[mask, 2] = 0
        arr[mask, 3] = 255  # Alpha (solid echo)
    img = Image.fromarray(arr, mode="RGBA")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_radar_tile_math_mumbai():
    """Verify Slippy map tile calculation for Mumbai coordinates at zoom 6."""
    lat, lon = 19.0760, 72.8777
    x, y = coordinates_to_tile(lat, lon, zoom=6)
    assert x == 44
    assert y == 28

    bbox = tile_to_bounding_box(x, y, zoom=6)
    assert bbox.min_lon <= lon <= bbox.max_lon
    assert bbox.min_lat <= lat <= bbox.max_lat


def test_radar_decode_tile_with_echoes():
    """Verify radar decoder computes active echoes, dBZ, and Marshall-Palmer rain rate."""
    client = RainViewerRadarClient()
    coords = Coordinates(latitude=19.0760, longitude=72.8777)
    bbox = tile_to_bounding_box(44, 28, zoom=6)
    png_bytes = generate_mock_radar_png(has_echoes=True)

    summary = client._decode_radar_tile(
        tile_bytes=png_bytes,
        tile_url="https://tilecache.rainviewer.com/test.png",
        requested_coords=coords,
        bounding_box=bbox,
        zoom=6,
        tile_x=44,
        tile_y=28,
        frame_time=1789564800,
    )

    assert summary.active_echo_pixels > 0
    assert summary.echo_coverage_pct > 0.0
    assert summary.max_reflectivity_dbz >= 5.0
    assert summary.estimated_max_rain_rate_mm_hr > 0.0
    assert summary.dimensions == [256, 256]


def test_radar_decode_tile_clear_sky():
    """Verify radar decoder handles clear air / zero echoes."""
    client = RainViewerRadarClient()
    coords = Coordinates(latitude=19.0760, longitude=72.8777)
    bbox = tile_to_bounding_box(44, 28, zoom=6)
    png_bytes = generate_mock_radar_png(has_echoes=False)

    summary = client._decode_radar_tile(
        tile_bytes=png_bytes,
        tile_url="https://tilecache.rainviewer.com/test.png",
        requested_coords=coords,
        bounding_box=bbox,
        zoom=6,
        tile_x=44,
        tile_y=28,
        frame_time=1789564800,
    )

    assert summary.active_echo_pixels == 0
    assert summary.echo_coverage_pct == 0.0
    assert summary.max_reflectivity_dbz == 0.0
    assert summary.estimated_max_rain_rate_mm_hr == 0.0


def test_radar_decode_corrupt_bytes_raises():
    """Verify error raised on invalid non-PNG tile bytes."""
    client = RainViewerRadarClient()
    coords = Coordinates(latitude=19.0760, longitude=72.8777)
    bbox = tile_to_bounding_box(44, 28, zoom=6)

    with pytest.raises(WeatherObservationValidationError):
        client._decode_radar_tile(
            tile_bytes=b"not-a-valid-image",
            tile_url="https://tilecache.rainviewer.com/corrupt.png",
            requested_coords=coords,
            bounding_box=bbox,
            zoom=6,
            tile_x=44,
            tile_y=28,
            frame_time=1789564800,
        )


@pytest.mark.anyio
async def test_radar_service_end_to_end_mock():
    """Verify complete radar service workflow with mocked catalog and tile responses."""
    mock_catalog = {
        "host": "https://tilecache.rainviewer.com",
        "radar": {
            "past": [
                {"time": 1789564000, "path": "/v2/radar/frame1"},
                {"time": 1789564600, "path": "/v2/radar/frame2"},
            ]
        },
    }
    png_bytes = generate_mock_radar_png(has_echoes=True)

    def mock_handler(request: httpx.Request) -> httpx.Response:
        if "weather-maps.json" in str(request.url):
            return httpx.Response(200, json=mock_catalog)
        return httpx.Response(200, content=png_bytes, headers={"Content-Type": "image/png"})

    transport = httpx.MockTransport(mock_handler)
    async_client = httpx.AsyncClient(transport=transport)
    client = RainViewerRadarClient(http_client=async_client)
    service = RadarService(radar_client=client)

    cache.clear()
    coords = Coordinates(latitude=19.0760, longitude=72.8777)
    resp = await service.fetch_radar_composite(coords, zoom_level=6)

    assert resp.status == "success"
    assert resp.available_frames_count == 2
    assert resp.latest_scan.unix_timestamp == 1789564600
    assert resp.latest_scan.active_echo_pixels > 0
