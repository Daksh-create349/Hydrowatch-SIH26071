"""Tests for Sentinel-2 STAC Catalog Client and Scene Selection."""

from datetime import date
from typing import Any, Dict
import httpx
import pytest

from backend.app.core.errors import ExternalApiError, SatelliteDataUnavailableError
from backend.app.services.sentinel_client import Sentinel2CatalogClient


def make_mock_stac_feature(
    scene_id: str,
    dt_str: str,
    cloud_cover: float,
    bbox: list,
    missing_band: str = None,
) -> Dict[str, Any]:
    """Helper to build realistic STAC item features."""
    assets = {
        "blue": {"href": f"https://mock-s3.com/{scene_id}/B02.tif"},
        "green": {"href": f"https://mock-s3.com/{scene_id}/B03.tif"},
        "red": {"href": f"https://mock-s3.com/{scene_id}/B04.tif"},
        "nir": {"href": f"https://mock-s3.com/{scene_id}/B08.tif"},
        "swir16": {"href": f"https://mock-s3.com/{scene_id}/B11.tif"},
        "swir22": {"href": f"https://mock-s3.com/{scene_id}/B12.tif"},
    }
    if missing_band:
        band_key_map = {"B2": "blue", "B3": "green", "B4": "red", "B8": "nir", "B11": "swir16", "B12": "swir22"}
        assets.pop(band_key_map.get(missing_band, missing_band), None)

    return {
        "id": scene_id,
        "type": "Feature",
        "bbox": bbox,
        "properties": {
            "datetime": dt_str,
            "eo:cloud_cover": cloud_cover,
            "proj:epsg": 32642,
        },
        "assets": assets,
    }


@pytest.mark.anyio
async def test_stac_client_search_and_parse_valid():
    """Verify STAC search query parses scenes and extracts 6 required bands."""
    mock_feat = make_mock_stac_feature(
        scene_id="S2B_TEST_SCENE_01",
        dt_str="2024-02-01T06:00:00Z",
        cloud_cover=12.5,
        bbox=[72.5, 18.5, 73.5, 19.5],
    )

    def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"type": "FeatureCollection", "features": [mock_feat]})

    transport = httpx.MockTransport(mock_handler)
    async_client = httpx.AsyncClient(transport=transport)
    client = Sentinel2CatalogClient(
        base_url="https://stac.example.com",
        http_client=async_client,
    )

    scenes = await client.search_scenes(
        latitude=19.0,
        longitude=72.8,
        target_date=date(2024, 2, 1),
        max_cloud_percentage=20.0,
    )

    assert len(scenes) == 1
    sc = scenes[0]
    assert sc.scene_id == "S2B_TEST_SCENE_01"
    assert sc.cloud_coverage == 12.5
    assert sc.crs == "EPSG:32642"
    assert len(sc.band_assets) == 6
    for b in ["B2", "B3", "B4", "B8", "B11", "B12"]:
        assert b in sc.band_assets
        assert sc.band_assets[b].asset_url.startswith("https://mock-s3.com/")


@pytest.mark.anyio
async def test_stac_client_no_scenes_found_raises():
    """Verify empty STAC result raises SatelliteDataUnavailableError in select_best_scene."""
    def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"type": "FeatureCollection", "features": []})

    transport = httpx.MockTransport(mock_handler)
    async_client = httpx.AsyncClient(transport=transport)
    client = Sentinel2CatalogClient(
        base_url="https://stac.example.com",
        http_client=async_client,
    )

    with pytest.raises(SatelliteDataUnavailableError) as exc_info:
        await client.select_best_scene(
            latitude=19.0,
            longitude=72.8,
            target_date=date(2024, 2, 1),
        )
    assert "No Sentinel-2 L2A scenes found" in str(exc_info.value)


@pytest.mark.anyio
async def test_stac_client_scene_missing_required_band_rejected():
    """Verify scenes missing any of the 6 required bands are rejected."""
    feat_missing_b12 = make_mock_stac_feature(
        scene_id="S2B_MISSING_B12",
        dt_str="2024-02-01T06:00:00Z",
        cloud_cover=5.0,
        bbox=[72.5, 18.5, 73.5, 19.5],
        missing_band="B12",
    )

    def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"type": "FeatureCollection", "features": [feat_missing_b12]})

    transport = httpx.MockTransport(mock_handler)
    async_client = httpx.AsyncClient(transport=transport)
    client = Sentinel2CatalogClient(
        base_url="https://stac.example.com",
        http_client=async_client,
    )

    with pytest.raises(SatelliteDataUnavailableError) as exc_info:
        await client.select_best_scene(
            latitude=19.0,
            longitude=72.8,
            target_date=date(2024, 2, 1),
        )
    assert "none contained all 6 required bands" in str(exc_info.value)


@pytest.mark.anyio
async def test_stac_client_deterministic_selection_prioritizes_date_and_cloud():
    """Verify deterministic ranking chooses the closest date and lowest cloud cover."""
    feat_near_low_cloud = make_mock_stac_feature(
        scene_id="S2B_BEST_SCENE",
        dt_str="2024-02-01T06:00:00Z",  # exact day
        cloud_cover=8.2,
        bbox=[72.5, 18.5, 73.5, 19.5],
    )
    feat_near_high_cloud = make_mock_stac_feature(
        scene_id="S2B_HIGH_CLOUD",
        dt_str="2024-02-01T06:00:00Z",  # exact day
        cloud_cover=19.5,
        bbox=[72.5, 18.5, 73.5, 19.5],
    )
    feat_far_zero_cloud = make_mock_stac_feature(
        scene_id="S2B_FAR_AWAY",
        dt_str="2024-01-15T06:00:00Z",  # 17 days earlier
        cloud_cover=0.0,
        bbox=[72.5, 18.5, 73.5, 19.5],
    )

    def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "type": "FeatureCollection",
                "features": [feat_far_zero_cloud, feat_near_high_cloud, feat_near_low_cloud],
            },
        )

    transport = httpx.MockTransport(mock_handler)
    async_client = httpx.AsyncClient(transport=transport)
    client = Sentinel2CatalogClient(
        base_url="https://stac.example.com",
        http_client=async_client,
    )

    selected = await client.select_best_scene(
        latitude=19.0,
        longitude=72.8,
        target_date=date(2024, 2, 1),
    )

    assert selected.scene_id == "S2B_BEST_SCENE"
    assert selected.cloud_coverage == 8.2
    assert "Deterministically selected" in selected.selection_reason
    assert "closest to target" in selected.selection_reason


@pytest.mark.anyio
async def test_stac_client_spatial_intersection_filter():
    """Verify scenes whose bounding box does not contain the query point are excluded."""
    feat_outside = make_mock_stac_feature(
        scene_id="S2B_OUTSIDE",
        dt_str="2024-02-01T06:00:00Z",
        cloud_cover=5.0,
        bbox=[80.0, 25.0, 81.0, 26.0],
    )

    def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"type": "FeatureCollection", "features": [feat_outside]})

    transport = httpx.MockTransport(mock_handler)
    async_client = httpx.AsyncClient(transport=transport)
    client = Sentinel2CatalogClient(
        base_url="https://stac.example.com",
        http_client=async_client,
    )

    scenes = await client.search_scenes(
        latitude=19.0,
        longitude=72.8,
        target_date=date(2024, 2, 1),
    )
    assert len(scenes) == 0


@pytest.mark.anyio
async def test_stac_client_http_500_retries_and_raises():
    """Verify transient 500 error triggers retries and eventually raises ExternalApiError."""
    def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="Internal Server Error")

    transport = httpx.MockTransport(mock_handler)
    async_client = httpx.AsyncClient(transport=transport)
    client = Sentinel2CatalogClient(
        base_url="https://stac.example.com",
        timeout_seconds=2.0,
        max_retries=2,
        http_client=async_client,
    )

    with pytest.raises(ExternalApiError) as exc_info:
        await client.search_scenes(
            latitude=19.0,
            longitude=72.8,
            target_date=date(2024, 2, 1),
        )
    assert "STAC catalog unavailable" in str(exc_info.value)
