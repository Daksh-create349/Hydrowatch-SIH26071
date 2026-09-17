"""Sentinel-2 Multispectral Imagery Service interface and pipeline orchestration."""

from datetime import date, datetime
from typing import Any, Dict, List, Optional

from backend.app.schemas.common import Coordinates, GeoBoundingBox
from backend.app.schemas.prediction import InundationPipelineResponse
from backend.app.schemas.satellite import SatelliteImageryMetadata, Sentinel2Bands
from backend.app.services.base import BaseService
from backend.app.services.model2_service import Model2Service
from backend.app.services.raster_processor import SentinelRasterProcessor
from backend.app.services.sentinel_client import Sentinel2CatalogClient


class SatelliteImageryService(BaseService):
    """
    Interface for acquiring and preprocessing Sentinel-2 multispectral imagery.
    Requires 6 bands for Model 2: B2, B3, B4, B8, B11, B12.
    Direct on-premise hardware feeds remain unconnected; public STAC & COG pipelines are live.
    """

    def __init__(self):
        super().__init__(
            name="SatelliteImageryService",
            description="Sentinel-2 6-band multispectral imagery ingestion and preprocessing",
        )
        self._is_connected = False

    def check_connection(self) -> bool:
        return False

    def search_scenes(
        self,
        bounding_box: GeoBoundingBox,
        start_date: datetime,
        end_date: datetime,
        max_cloud_cover: float = 30.0,
    ) -> List[SatelliteImageryMetadata]:
        """Query real satellite scenes matching spatial and temporal criteria."""
        raise NotImplementedError(
            "Satellite imagery catalog provider is not yet connected."
        )

    def download_and_extract_bands(
        self, scene_id: str, target_dir: Optional[str] = None
    ) -> Sentinel2Bands:
        """Download and prepare calibrated 6-band raster inputs for Model 2."""
        raise NotImplementedError(
            "Satellite band extraction pipeline is not yet connected. Fake imagery is strictly forbidden."
        )

    async def predict_inundation(
        self,
        latitude: float,
        longitude: float,
        target_date: Optional[date] = None,
        max_cloud_percentage: float = 25.0,
        min_polygon_area_sq_m: float = 500.0,
        location_name: Optional[str] = None,
    ) -> InundationPipelineResponse:
        """
        Execute full real Sentinel-2 to Model 2 Inundation Pipeline:
        1. Discover and select best real Sentinel-2 Level-2A scene from STAC catalog.
        2. Stream/fetch the 6 required bands [B2, B3, B4, B8, B11, B12] via COG HTTP Range requests.
        3. Resample 20m bands to 10m common grid using bilinear interpolation.
        4. Tile raster into 512x512 windows with 64px overlap and run real Model 2 FloodUNet inference.
        5. Reconstruct seamless probability mosaic and threshold at 0.5.
        6. Vectorize binary inundation mask into WGS84 GeoJSON polygons with holes.
        7. Compute geodesic surface area statistics.
        8. Return structured InundationPipelineResponse.
        """
        catalog_client = Sentinel2CatalogClient()
        raster_processor = SentinelRasterProcessor()
        model2_svc = Model2Service.get_instance()

        # 1. Select optimal real Sentinel-2 scene
        selected_scene = await catalog_client.select_best_scene(
            latitude=latitude,
            longitude=longitude,
            target_date=target_date,
            max_cloud_percentage=max_cloud_percentage,
        )

        # 2. Fetch and align 6 bands onto common 10m grid
        common_grid, grid_meta = await raster_processor.fetch_and_align_scene(
            scene=selected_scene,
            query_lat=latitude,
            query_lon=longitude,
        )

        # 3. Sliding window tiling and Model 2 inference
        prob_mosaic, binary_mask = raster_processor.tile_and_predict(
            raster_data=common_grid,
            model2_service=model2_svc,
            window_size=512,
            overlap=64,
        )

        # 4. Vectorize to GeoJSON polygons and compute geodesic statistics
        geojson_resp, stats = raster_processor.polygonize_mask(
            binary_mask=binary_mask,
            grid_metadata=grid_meta,
            scene_id=selected_scene.scene_id,
            acquisition_time=selected_scene.acquisition_datetime.isoformat(),
            min_area_sq_m=min_polygon_area_sq_m,
        )

        # 5. Assemble structured response
        return InundationPipelineResponse(
            status="success",
            requested_location=Coordinates(latitude=latitude, longitude=longitude),
            location_name=location_name,
            selected_scene=selected_scene.model_dump(),
            model_version="flood_unet_sentinel2_6band",
            threshold=model2_svc.threshold,
            grid_resolution_m=stats["grid_resolution_m"],
            raster_dimensions=stats["dimensions"],
            valid_area_sq_km=stats["valid_area_sq_km"],
            flooded_area_sq_km=stats["flooded_area_sq_km"],
            flooded_percentage=stats["flooded_percentage"],
            polygon_count=stats["polygon_count"],
            geojson=geojson_resp.model_dump(),
            metadata={
                "input_bands": ["B2", "B3", "B4", "B8", "B11", "B12"],
                "reflectance_scale": 10000.0,
                "tile_col": grid_meta.get("tile_col"),
                "tile_row": grid_meta.get("tile_row"),
                "utm_zone": grid_meta.get("utm_zone"),
                "crs": grid_meta.get("crs"),
                "raw_water_area_sq_km": stats.get("raw_water_area_sq_km"),
                "raw_polygon_count": stats.get("raw_polygon_count"),
                "excluded_permanent_water_sq_km": stats.get("excluded_permanent_water_sq_km"),
                "permanent_water_polygon_count": stats.get("permanent_water_polygon_count"),
                "water_label": stats.get("water_label"),
            },
        )
