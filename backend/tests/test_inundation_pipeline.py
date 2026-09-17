"""End-to-end API pipeline tests for POST /api/v1/predict/inundation."""

from unittest.mock import AsyncMock, patch
import numpy as np
import pytest
from starlette.testclient import TestClient

from backend.app.core.errors import ExternalApiError, SatelliteDataUnavailableError
from backend.app.main import create_app
from backend.app.schemas.common import GeoBoundingBox
from backend.app.schemas.satellite import BandAssetMetadata, Sentinel2SceneMetadata
from backend.app.services.raster_processor import latlon_to_utm


@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)


def make_mock_scene() -> Sentinel2SceneMetadata:
    """Construct mock Sentinel2SceneMetadata for testing pipeline."""
    return Sentinel2SceneMetadata(
        scene_id="S2B_42QZF_20240201_0_L2A",
        collection="sentinel-2-l2a",
        acquisition_datetime="2024-02-01T05:53:53Z",
        processing_level="Level-2A",
        cloud_coverage=14.2,
        bounding_box=GeoBoundingBox(min_lat=18.5, max_lat=19.5, min_lon=72.5, max_lon=73.5),
        crs="EPSG:32642",
        source="Earth Search AWS / Element 84",
        selection_reason="Deterministically selected: lowest cloud cover and verified 6 bands",
        band_assets={
            b: BandAssetMetadata(
                band_name=b,
                stac_asset_key=b.lower(),
                asset_url=f"https://mock-s3/{b}.tif",
                resolution_m=10.0 if b in ("B2", "B3", "B4", "B8") else 20.0,
                crs="EPSG:32642",
            )
            for b in ["B2", "B3", "B4", "B8", "B11", "B12"]
        },
    )


def test_predict_inundation_invalid_coordinates(client: TestClient):
    """Verify out-of-range coordinates are rejected with 422."""
    resp = client.post(
        "/api/v1/predict/inundation",
        json={"latitude": 195.0, "longitude": 72.8777},
    )
    assert resp.status_code == 422
    data = resp.json()
    assert data["success"] is False
    assert data["error"]["code"] == "VALIDATION_ERROR"


def test_predict_inundation_invalid_date_format(client: TestClient):
    """Verify invalid date string format is rejected with 422."""
    resp = client.post(
        "/api/v1/predict/inundation",
        json={"latitude": 19.0760, "longitude": 72.8777, "date": "01-02-2024"},
    )
    assert resp.status_code == 422
    data = resp.json()
    assert data["success"] is False
    assert "Invalid date format" in data["error"]["message"]


def test_predict_inundation_no_scene_found_returns_404(client: TestClient):
    """Verify SatelliteDataUnavailableError maps to HTTP 404."""
    with patch(
        "backend.app.services.sentinel_client.Sentinel2CatalogClient.select_best_scene",
        side_effect=SatelliteDataUnavailableError("No Sentinel-2 L2A scenes found matching criteria."),
    ):
        resp = client.post(
            "/api/v1/predict/inundation",
            json={"latitude": 19.0760, "longitude": 72.8777, "date": "2024-02-01"},
        )
        assert resp.status_code == 404
        data = resp.json()
        assert data["success"] is False
        assert data["error"]["code"] == "SATELLITE_DATA_UNAVAILABLE"


def test_predict_inundation_upstream_failure_returns_502(client: TestClient):
    """Verify upstream catalog network/500 failure maps to HTTP 502."""
    with patch(
        "backend.app.services.sentinel_client.Sentinel2CatalogClient.select_best_scene",
        side_effect=ExternalApiError(service_name="Sentinel2STAC", message="Gateway timeout"),
    ):
        resp = client.post(
            "/api/v1/predict/inundation",
            json={"latitude": 19.0760, "longitude": 72.8777},
        )
        assert resp.status_code == 502
        data = resp.json()
        assert data["success"] is False
        assert data["error"]["code"] == "EXTERNAL_API_ERROR"


def test_predict_inundation_pipeline_success_with_real_model2(client: TestClient):
    """
    Verify complete end-to-end inundation prediction pipeline:
    - Mock STAC scene selection and COG raster download
    - Run REAL Model 2 FloodUNet checkpoint inference
    - Vectorize mask to GeoJSON
    - Assert all response fields match contract
    """
    mock_scene = make_mock_scene()
    easting, northing, zone = latlon_to_utm(19.0760, 72.8777, zone=42, north=True)

    grid_meta = {
        "origin_x": easting,
        "origin_y": northing,
        "pixel_scale_m": 10.0,
        "utm_zone": zone,
        "utm_north": True,
        "crs": "EPSG:32642",
        "width": 512,
        "height": 512,
        "tile_row": 3,
        "tile_col": 4,
    }

    # Realistic 6-band input simulating water body in center
    # Surface water typically has low NIR (B8) and high Blue (B2)
    synthetic_bands = np.full((6, 512, 512), fill_value=1200.0, dtype=np.float32)
    # Add a water-like spectral feature in center: low B8, B11, B12, moderate B2, B3
    synthetic_bands[3, 200:300, 200:300] = 200.0   # B8 near-IR drop
    synthetic_bands[4, 200:300, 200:300] = 100.0   # B11 SWIR drop
    synthetic_bands[5, 200:300, 200:300] = 80.0    # B12 SWIR drop

    with patch(
        "backend.app.services.sentinel_client.Sentinel2CatalogClient.select_best_scene",
        new=AsyncMock(return_value=mock_scene),
    ), patch(
        "backend.app.services.raster_processor.SentinelRasterProcessor.fetch_and_align_scene",
        new=AsyncMock(return_value=(synthetic_bands, grid_meta)),
    ):
        resp = client.post(
            "/api/v1/predict/inundation",
            json={
                "latitude": 19.0760,
                "longitude": 72.8777,
                "date": "2024-02-01",
                "max_cloud_percentage": 20.0,
                "min_polygon_area_sq_m": 500.0,
                "location_name": "Mumbai Mithi River Basin",
            },
        )

        assert resp.status_code == 200
        data = resp.json()

        assert data["status"] == "success"
        assert data["requested_location"]["latitude"] == 19.0760
        assert data["requested_location"]["longitude"] == 72.8777
        assert data["location_name"] == "Mumbai Mithi River Basin"
        assert data["selected_scene"]["scene_id"] == "S2B_42QZF_20240201_0_L2A"
        assert data["model_version"] == "flood_unet_sentinel2_6band"
        assert data["threshold"] == 0.5
        assert data["grid_resolution_m"] == 10.0
        assert data["raster_dimensions"] == [512, 512]
        assert data["valid_area_sq_km"] > 0.0
        assert data["flooded_area_sq_km"] >= 0.0
        assert 0.0 <= data["flooded_percentage"] <= 100.0
        assert isinstance(data["polygon_count"], int)
        assert data["geojson"]["type"] == "FeatureCollection"
        assert isinstance(data["geojson"]["features"], list)

        # Provenance metadata
        meta = data["metadata"]
        assert meta["input_bands"] == ["B2", "B3", "B4", "B8", "B11", "B12"]
        assert meta["reflectance_scale"] == 10000.0
