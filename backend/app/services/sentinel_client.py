"""Sentinel-2 STAC Catalog Client for Level-2A imagery discovery."""

import asyncio
from datetime import date, datetime, timedelta, timezone
import logging
from typing import Any, Dict, List, Optional, Tuple
import httpx

from backend.app.core.config import get_settings
from backend.app.core.errors import ExternalApiError, SatelliteDataUnavailableError
from backend.app.schemas.common import Coordinates, GeoBoundingBox
from backend.app.schemas.satellite import BandAssetMetadata, Sentinel2SceneMetadata

logger = logging.getLogger("rainfall_backend.services.sentinel_client")

# Expected Model 2 band mappings to STAC asset keys and native spatial resolutions
BAND_SPECIFICATIONS: Dict[str, Dict[str, Any]] = {
    "B2": {"stac_keys": ["blue", "B02", "b02"], "resolution_m": 10.0},
    "B3": {"stac_keys": ["green", "B03", "b03"], "resolution_m": 10.0},
    "B4": {"stac_keys": ["red", "B04", "b04"], "resolution_m": 10.0},
    "B8": {"stac_keys": ["nir", "B08", "b08"], "resolution_m": 10.0},
    "B11": {"stac_keys": ["swir16", "B11", "b11"], "resolution_m": 20.0},
    "B12": {"stac_keys": ["swir22", "B12", "b12"], "resolution_m": 20.0},
}


class Sentinel2CatalogClient:
    """
    Client for querying the public STAC catalog (Element 84 Earth Search)
    to discover Sentinel-2 Level-2A surface-reflectance imagery.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        collection: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
        max_retries: Optional[int] = None,
        http_client: Optional[httpx.AsyncClient] = None,
    ):
        settings = get_settings()
        self.base_url = (base_url or settings.SENTINEL_STAC_URL).rstrip("/")
        self.collection = collection or settings.SENTINEL_COLLECTION
        self.timeout = timeout_seconds or settings.SENTINEL_TIMEOUT_SECONDS
        self.max_retries = max_retries or settings.SENTINEL_MAX_RETRIES
        self._http_client = http_client

    async def search_scenes(
        self,
        latitude: float,
        longitude: float,
        target_date: Optional[date] = None,
        date_window_days: int = 30,
        max_cloud_percentage: float = 25.0,
        limit: int = 10,
    ) -> List[Sentinel2SceneMetadata]:
        """
        Search STAC catalog for scenes intersecting coordinates within temporal window.
        """
        search_endpoint = f"{self.base_url}/search"

        # Determine temporal search interval [start, end]
        if target_date is not None:
            dt_target = datetime(target_date.year, target_date.month, target_date.day, tzinfo=timezone.utc)
            dt_start = dt_target - timedelta(days=date_window_days)
            dt_end = dt_target + timedelta(days=5)  # slight future buffer if target is historical
        else:
            # Default to latest 30 days from now
            dt_end = datetime.now(timezone.utc)
            dt_start = dt_end - timedelta(days=date_window_days)

        start_str = dt_start.strftime("%Y-%m-%dT00:00:00Z")
        end_str = dt_end.strftime("%Y-%m-%dT23:59:59Z")
        datetime_param = f"{start_str}/{end_str}"

        # Bounding box search around query point (+- 0.05 degrees ~ 5.5 km)
        delta = 0.05
        bbox = [
            round(longitude - delta, 4),
            round(latitude - delta, 4),
            round(longitude + delta, 4),
            round(latitude + delta, 4),
        ]

        payload: Dict[str, Any] = {
            "collections": [self.collection],
            "bbox": bbox,
            "datetime": datetime_param,
            "limit": limit,
            "query": {
                "eo:cloud_cover": {"lte": max_cloud_percentage}
            },
        }

        logger.info(
            "Querying STAC API %s for (%f, %f) in [%s, %s] with max cloud %.1f%%",
            search_endpoint,
            latitude,
            longitude,
            start_str,
            end_str,
            max_cloud_percentage,
        )

        response_data = await self._post_with_retry(search_endpoint, payload)
        features = response_data.get("features", [])
        if not features:
            logger.info("STAC search returned 0 features for coordinates (%f, %f)", latitude, longitude)
            return []

        parsed_scenes: List[Sentinel2SceneMetadata] = []
        for feat in features:
            parsed = self._parse_stac_feature(feat, latitude, longitude)
            if parsed is not None:
                parsed_scenes.append(parsed)

        return parsed_scenes

    async def select_best_scene(
        self,
        latitude: float,
        longitude: float,
        target_date: Optional[date] = None,
        max_cloud_percentage: float = 25.0,
    ) -> Sentinel2SceneMetadata:
        """
        Deterministic scene selection:
        1. Query candidates intersecting coordinates.
        2. Filter out scenes missing ANY of the 6 required bands.
        3. Prioritize:
           - Temporal closeness to target_date (or most recent if no target).
           - Lowest cloud coverage.
        4. Return selected scene with structured selection_reason.
        """
        candidates = await self.search_scenes(
            latitude=latitude,
            longitude=longitude,
            target_date=target_date,
            max_cloud_percentage=max_cloud_percentage,
        )

        if not candidates:
            raise SatelliteDataUnavailableError(
                f"No Sentinel-2 L2A scenes found intersecting ({latitude}, {longitude}) "
                f"with cloud cover <= {max_cloud_percentage}%.",
                details={
                    "latitude": latitude,
                    "longitude": longitude,
                    "target_date": str(target_date) if target_date else "latest",
                    "max_cloud_percentage": max_cloud_percentage,
                },
            )

        # Filter strictly for 6 required bands
        required_bands = set(BAND_SPECIFICATIONS.keys())
        valid_candidates: List[Sentinel2SceneMetadata] = []
        for sc in candidates:
            available_bands = set(sc.band_assets.keys())
            if required_bands.issubset(available_bands):
                valid_candidates.append(sc)
            else:
                missing = sorted(list(required_bands - available_bands))
                logger.warning(
                    "Scene %s rejected: missing required bands %s",
                    sc.scene_id,
                    missing,
                )

        if not valid_candidates:
            raise SatelliteDataUnavailableError(
                f"Found {len(candidates)} candidate scenes but none contained all 6 required bands "
                f"[B2, B3, B4, B8, B11, B12].",
                details={"candidate_count": len(candidates)},
            )

        # Deterministic ranking:
        # Score based on (temporal_distance_days, cloud_coverage)
        ref_dt = (
            datetime(target_date.year, target_date.month, target_date.day, tzinfo=timezone.utc)
            if target_date
            else datetime.now(timezone.utc)
        )

        def ranking_key(scene: Sentinel2SceneMetadata) -> Tuple[float, float]:
            time_delta = abs((scene.acquisition_datetime - ref_dt).total_seconds()) / 86400.0
            return (round(time_delta, 1), round(scene.cloud_coverage, 2))

        valid_candidates.sort(key=ranking_key)
        best = valid_candidates[0]

        days_diff = abs((best.acquisition_datetime - ref_dt).total_seconds()) / 86400.0
        best.selection_reason = (
            f"Deterministically selected from {len(valid_candidates)} candidates: "
            f"closest to target ({days_diff:.1f} days delta), lowest cloud coverage "
            f"({best.cloud_coverage:.1f}%), verified all 6 required bands [B2, B3, B4, B8, B11, B12]."
        )

        logger.info(
            "Selected scene %s (cloud=%.1f%%, crs=%s): %s",
            best.scene_id,
            best.cloud_coverage,
            best.crs,
            best.selection_reason,
        )
        return best

    def _parse_stac_feature(
        self, feat: Dict[str, Any], query_lat: float, query_lon: float
    ) -> Optional[Sentinel2SceneMetadata]:
        """Parse raw GeoJSON STAC Feature into Sentinel2SceneMetadata."""
        scene_id = feat.get("id")
        if not scene_id:
            return None

        props = feat.get("properties", {})
        dt_str = props.get("datetime")
        if not dt_str:
            return None

        try:
            acq_dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        except ValueError:
            return None

        cloud_cov = float(props.get("eo:cloud_cover", 100.0))

        # CRS
        proj_epsg = props.get("proj:epsg")
        crs_code = f"EPSG:{proj_epsg}" if proj_epsg else "EPSG:32642"

        # Bounding box: STAC standard is [min_lon, min_lat, max_lon, max_lat]
        raw_bbox = feat.get("bbox")
        if not raw_bbox or len(raw_bbox) < 4:
            return None

        min_lon, min_lat, max_lon, max_lat = (
            float(raw_bbox[0]),
            float(raw_bbox[1]),
            float(raw_bbox[2]),
            float(raw_bbox[3]),
        )

        # Validate spatial intersection
        if not (min_lat <= query_lat <= max_lat and min_lon <= query_lon <= max_lon):
            return None

        geo_bbox = GeoBoundingBox(
            min_lat=min_lat,
            max_lat=max_lat,
            min_lon=min_lon,
            max_lon=max_lon,
        )

        assets = feat.get("assets", {})
        band_assets: Dict[str, BandAssetMetadata] = {}

        for b_name, b_spec in BAND_SPECIFICATIONS.items():
            matched_key = None
            matched_asset = None
            for key_candidate in b_spec["stac_keys"]:
                if key_candidate in assets:
                    matched_key = key_candidate
                    matched_asset = assets[key_candidate]
                    break

            if matched_asset and "href" in matched_asset:
                band_assets[b_name] = BandAssetMetadata(
                    band_name=b_name,
                    stac_asset_key=matched_key,
                    asset_url=matched_asset["href"],
                    resolution_m=b_spec["resolution_m"],
                    crs=crs_code,
                    nodata=0.0,
                    dtype="uint16",
                )

        thumbnail_url = None
        if "thumbnail" in assets and "href" in assets["thumbnail"]:
            thumbnail_url = assets["thumbnail"]["href"]
        elif "rendered_preview" in assets and "href" in assets["rendered_preview"]:
            thumbnail_url = assets["rendered_preview"]["href"]

        return Sentinel2SceneMetadata(
            scene_id=scene_id,
            collection=self.collection,
            acquisition_datetime=acq_dt,
            processing_level="Level-2A",
            cloud_coverage=cloud_cov,
            bounding_box=geo_bbox,
            crs=crs_code,
            source="Earth Search AWS / Element 84",
            selection_reason=None,
            thumbnail_url=thumbnail_url,
            band_assets=band_assets,
        )

    async def _post_with_retry(self, url: str, json_payload: Dict[str, Any]) -> Dict[str, Any]:
        """HTTP POST with exponential backoff on transient errors."""
        last_exception = None

        for attempt in range(1, self.max_retries + 1):
            try:
                if self._http_client is not None:
                    resp = await self._http_client.post(url, json=json_payload)
                else:
                    async with httpx.AsyncClient(timeout=self.timeout) as client:
                        resp = await client.post(url, json=json_payload)

                if resp.status_code == 200:
                    return resp.json()
                elif resp.status_code in (429, 500, 502, 503, 504):
                    logger.warning(
                        "STAC query attempt %d/%d failed with HTTP %d: %s",
                        attempt,
                        self.max_retries,
                        resp.status_code,
                        resp.text[:200],
                    )
                else:
                    raise ExternalApiError(
                        service_name="Sentinel2STAC",
                        message=f"STAC API error HTTP {resp.status_code}: {resp.text[:200]}",
                        status_code=resp.status_code,
                    )
            except (httpx.RequestError, httpx.TimeoutException) as exc:
                logger.warning("STAC query network failure attempt %d/%d: %s", attempt, self.max_retries, str(exc))
                last_exception = exc

            if attempt < self.max_retries:
                await asyncio.sleep(1.0 * (2 ** (attempt - 1)))

        raise ExternalApiError(
            service_name="Sentinel2STAC",
            message=f"STAC catalog unavailable after {self.max_retries} attempts: {last_exception}",
            status_code=502,
        )
