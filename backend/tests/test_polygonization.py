"""Tests for binary mask vectorization, contour polygonization, and geodesic area calculation."""

import numpy as np
import pytest

from backend.app.services.raster_processor import (
    SentinelRasterProcessor,
    latlon_to_utm,
    utm_to_latlon,
)


@pytest.fixture
def sample_grid_meta():
    """Sample UTM zone 42N grid metadata centered near Mumbai."""
    # Top-left tiepoint around 19.10 N, 72.85 E in UTM 42N
    easting, northing, zone = latlon_to_utm(19.10, 72.85, zone=42, north=True)
    return {
        "origin_x": easting,
        "origin_y": northing,
        "pixel_scale_m": 10.0,
        "utm_zone": zone,
        "utm_north": True,
        "crs": "EPSG:32642",
        "width": 500,
        "height": 500,
    }


def test_utm_latlon_roundtrip_precision():
    """Verify UTM forward and inverse transformation maintains millimeter-level precision."""
    test_lat = 19.0760
    test_lon = 72.8777
    zone = 42

    e, n, z = latlon_to_utm(test_lat, test_lon, zone=zone, north=True)
    lat_back, lon_back = utm_to_latlon(e, n, zone=zone, north=True)

    assert abs(lat_back - test_lat) < 1e-6
    assert abs(lon_back - test_lon) < 1e-6


def test_polygonize_empty_mask(sample_grid_meta):
    """Verify completely dry scene produces 0 polygons and 0.0% flooded area."""
    processor = SentinelRasterProcessor()
    mask = np.zeros((500, 500), dtype=np.uint8)

    geojson_resp, stats = processor.polygonize_mask(
        binary_mask=mask,
        grid_metadata=sample_grid_meta,
        scene_id="S2B_DRY_SCENE",
        acquisition_time="2024-02-01T06:00:00Z",
    )

    assert len(geojson_resp.features) == 0
    assert stats["polygon_count"] == 0
    assert stats["flooded_pixels"] == 0
    assert stats["flooded_area_sq_km"] == 0.0
    assert stats["flooded_percentage"] == 0.0
    assert stats["valid_area_sq_km"] == round((500 * 500 * 100.0) / 1e6, 3)


def test_polygonize_single_region(sample_grid_meta):
    """Verify single contiguous flood region generates 1 valid closed GeoJSON polygon."""
    processor = SentinelRasterProcessor()
    mask = np.zeros((200, 200), dtype=np.uint8)
    # 50x50 pixels = 2500 pixels = 250,000 m² = 0.25 km²
    mask[50:100, 50:100] = 1

    geojson_resp, stats = processor.polygonize_mask(
        binary_mask=mask,
        grid_metadata=sample_grid_meta,
        scene_id="S2B_SINGLE_REGION",
        acquisition_time="2024-02-01T06:00:00Z",
    )

    assert len(geojson_resp.features) == 1
    feat = geojson_resp.features[0]
    assert feat.geometry.type == "Polygon"
    rings = feat.geometry.coordinates
    assert len(rings) == 1  # 1 exterior ring, no holes
    ext_ring = rings[0]
    # Ring must be closed
    assert ext_ring[0] == ext_ring[-1]
    # Coordinates must be valid WGS84 lon/lat
    for pt in ext_ring:
        assert 70.0 <= pt[0] <= 75.0  # Lon
        assert 18.0 <= pt[1] <= 20.0  # Lat

    assert feat.properties.scene_id == "S2B_SINGLE_REGION"
    assert feat.properties.flooded_area_sq_m > 200000.0  # ~250,000 m²
    assert stats["flooded_pixels"] == 2500
    assert stats["flooded_area_sq_km"] == 0.25


def test_polygonize_water_with_island_hole(sample_grid_meta):
    """Verify flood region with unflooded island generates exterior and interior rings."""
    processor = SentinelRasterProcessor()
    mask = np.zeros((200, 200), dtype=np.uint8)
    # Outer water body: 100x100 pixels
    mask[20:120, 20:120] = 1
    # Dry island hole: 30x30 pixels (900 pixels = 90,000 m² > 500 m² filter)
    mask[50:80, 50:80] = 0

    geojson_resp, stats = processor.polygonize_mask(
        binary_mask=mask,
        grid_metadata=sample_grid_meta,
        scene_id="S2B_ISLAND_SCENE",
        acquisition_time="2024-02-01T06:00:00Z",
    )

    assert len(geojson_resp.features) == 1
    feat = geojson_resp.features[0]
    rings = feat.geometry.coordinates
    assert len(rings) == 2  # Exterior ring + 1 interior hole
    ext_ring = rings[0]
    hole_ring = rings[1]
    assert ext_ring[0] == ext_ring[-1]
    assert hole_ring[0] == hole_ring[-1]


def test_polygonize_noise_filtering(sample_grid_meta):
    """Verify single-pixel or tiny noise regions below min_area_sq_m are discarded."""
    processor = SentinelRasterProcessor()
    mask = np.zeros((100, 100), dtype=np.uint8)
    # 2x2 pixels = 4 pixels = 400 m² (< 500 m² threshold)
    mask[10:12, 10:12] = 1
    # 10x10 pixels = 100 pixels = 10,000 m² (> 500 m² threshold)
    mask[40:50, 40:50] = 1

    geojson_resp, stats = processor.polygonize_mask(
        binary_mask=mask,
        grid_metadata=sample_grid_meta,
        scene_id="S2B_NOISE_TEST",
        acquisition_time="2024-02-01T06:00:00Z",
        min_area_sq_m=500.0,
    )

    # Only the 10x10 polygon should be preserved; 2x2 noise filtered out
    assert len(geojson_resp.features) == 1
    assert geojson_resp.features[0].properties.flooded_area_sq_m >= 8000.0


def test_coastal_ocean_polygon_excluded_from_user_facing_geojson(sample_grid_meta):
    """Verify massive tile-border ocean polygon is excluded while inland water is preserved."""
    processor = SentinelRasterProcessor()
    # 1024x1024 scene
    meta_1024 = dict(sample_grid_meta)
    meta_1024["width"] = 1024
    meta_1024["height"] = 1024

    mask = np.zeros((1024, 1024), dtype=np.uint8)
    # 1. Massive coastal ocean covering eastern half and touching right/top/bottom edges:
    # 1024 rows x 500 cols = 512,000 pixels = 51.2 km² (like Bay of Bengal in Chennai)
    mask[0:1024, 524:1024] = 1

    # 2. Inland lake in western half:
    # 50x50 pixels = 2500 pixels = 0.25 km²
    mask[200:250, 200:250] = 1

    geojson_resp, stats = processor.polygonize_mask(
        binary_mask=mask,
        grid_metadata=meta_1024,
        scene_id="S2B_COASTAL_SCENE",
        acquisition_time="2024-02-01T06:00:00Z",
    )

    # Ocean must be excluded from user-facing features
    assert len(geojson_resp.features) == 1
    feat = geojson_resp.features[0]
    assert feat.properties.is_permanent_water is False
    assert feat.properties.water_type in ("inland_water", "inundation")
    assert feat.properties.flooded_area_sq_m > 200000.0

    # User-facing flooded area reflects inland water, NOT the 51.2 km² ocean
    assert abs(stats["flooded_area_sq_km"] - 0.24) < 0.02
    assert stats["polygon_count"] == 1

    # Internal metadata preserves raw water mask and ocean exclusion
    assert stats["raw_polygon_count"] == 2
    assert stats["permanent_water_polygon_count"] == 1
    assert stats["excluded_permanent_water_sq_km"] >= 50.0
    assert stats["raw_water_area_sq_km"] >= 51.0
    assert "Excluded" in stats["water_label"]


def test_inland_water_body_preserved(sample_grid_meta):
    """Verify large inland lake (like Khadakwasla in Pune) is preserved without border ocean exclusion."""
    processor = SentinelRasterProcessor()
    mask = np.zeros((500, 500), dtype=np.uint8)
    # 120x120 pixels = 14,400 pixels = 1.44 km² in center of scene
    mask[150:270, 150:270] = 1

    geojson_resp, stats = processor.polygonize_mask(
        binary_mask=mask,
        grid_metadata=sample_grid_meta,
        scene_id="S2B_PUNE_RESERVOIR",
        acquisition_time="2024-02-01T06:00:00Z",
    )

    assert len(geojson_resp.features) == 1
    feat = geojson_resp.features[0]
    assert feat.properties.is_permanent_water is False
    assert feat.properties.water_type == "inland_water"
    assert stats["flooded_area_sq_km"] == 1.44
    assert stats["excluded_permanent_water_sq_km"] == 0.0
    assert stats["permanent_water_polygon_count"] == 0
