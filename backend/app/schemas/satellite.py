"""Satellite observation, precipitation, and imagery schemas."""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field
from backend.app.schemas.common import Coordinates, GeoBoundingBox


class SatellitePrecipitationObservation(BaseModel):
    """Satellite-derived precipitation estimate (e.g., GPM IMERG, INSAT-3D/3DR)."""
    satellite_name: str = Field(..., description="e.g., 'GPM-IMERG', 'INSAT-3DR'")
    timestamp: datetime = Field(..., description="Observation interval timestamp in UTC")
    coordinates: Optional[Coordinates] = None
    bounding_box: Optional[GeoBoundingBox] = None
    precipitation_rate_mm_hr: float = Field(..., ge=0.0)
    quality_flag: Optional[str] = None


class Sentinel2Bands(BaseModel):
    """
    Multispectral Sentinel-2 band identifiers required by Model 2 (FloodUNet).
    6 specific bands: B2, B3, B4, B8, B11, B12.
    """
    b2: Optional[str] = Field(None, description="Blue (Band 2) raster file path or URI")
    b3: Optional[str] = Field(None, description="Green (Band 3) raster file path or URI")
    b4: Optional[str] = Field(None, description="Red (Band 4) raster file path or URI")
    b8: Optional[str] = Field(None, description="Near-Infrared (Band 8) raster file path or URI")
    b11: Optional[str] = Field(None, description="SWIR-1 (Band 11) raster file path or URI")
    b12: Optional[str] = Field(None, description="SWIR-2 (Band 12) raster file path or URI")


class SatelliteImageryMetadata(BaseModel):
    """Metadata for multispectral satellite scene."""
    scene_id: str
    satellite: str = "Sentinel-2"
    acquisition_time: datetime
    bounding_box: GeoBoundingBox
    cloud_cover_percentage: float = Field(..., ge=0.0, le=100.0)
    bands: List[str] = Field(
        default=["B2", "B3", "B4", "B8", "B11", "B12"],
        description="Available multispectral bands",
    )
    reflectance_scale: float = Field(10000.0, description="Scale factor for surface reflectance")


# ============================================================
# NORMALIZED SENTINEL-2 STAC SCHEMAS
# ============================================================

class BandAssetMetadata(BaseModel):
    """Normalized metadata for a single Sentinel-2 multispectral band asset."""
    band_name: str = Field(..., description="Standard band code: B2, B3, B4, B8, B11, B12")
    stac_asset_key: str = Field(..., description="STAC asset key, e.g., 'blue', 'red', 'swir16'")
    asset_url: str = Field(..., description="Download or streaming URI for the raster asset")
    resolution_m: float = Field(..., description="Native ground sampling distance in meters (10.0 or 20.0)")
    crs: str = Field(default="EPSG:32642", description="Native coordinate reference system code")
    nodata: Optional[float] = Field(default=0.0, description="Nodata pixel value")
    dtype: str = Field(default="uint16", description="Raster data type")


class Sentinel2SceneMetadata(BaseModel):
    """Normalized metadata for a real discovered Sentinel-2 Level-2A scene."""
    scene_id: str = Field(..., description="Granule or product identifier, e.g. S2B_42QZF_20240201_0_L2A")
    collection: str = Field(default="sentinel-2-l2a", description="STAC collection identifier")
    acquisition_datetime: datetime = Field(..., description="Acquisition UTC timestamp")
    processing_level: str = Field(default="Level-2A", description="Product processing level (BOA reflectance)")
    cloud_coverage: float = Field(..., ge=0.0, le=100.0, description="Scene or granule cloud cover percentage")
    bounding_box: GeoBoundingBox = Field(..., description="Geographic bounding box [min_lat, max_lat, min_lon, max_lon]")
    crs: str = Field(..., description="Projected coordinate system, e.g. 'EPSG:32642'")
    source: str = Field(default="Earth Search AWS / Element 84", description="Catalog and archive provider")
    selection_reason: Optional[str] = Field(None, description="Deterministic rationale for scene selection")
    thumbnail_url: Optional[str] = Field(None, description="Direct URL to real Sentinel-2 optical RGB thumbnail")
    band_assets: dict[str, BandAssetMetadata] = Field(
        default_factory=dict,
        description="Mapping of band name (B2, B3, B4, B8, B11, B12) to asset metadata",
    )


# ============================================================
# GEOSPATIAL VECTORIZATION & GEOJSON SCHEMAS
# ============================================================

class InundationPolygonProperties(BaseModel):
    """Metadata properties attached to an individual inundation polygon."""
    flooded_area_sq_m: float = Field(..., ge=0.0, description="Geodesic surface area of polygon in square meters")
    perimeter_m: float = Field(..., ge=0.0, description="Perimeter length in meters")
    scene_id: str = Field(..., description="Parent Sentinel-2 scene identifier")
    acquisition_time: str = Field(..., description="Acquisition ISO datetime string")
    source: str = Field(default="Sentinel-2 L2A", description="Satellite data source")
    model_version: str = Field(default="FloodUNet_v1", description="Model architecture and version")
    water_type: str = Field(default="inundation", description="Water classification: 'inundation', 'inland_water', or 'coastal_ocean'")
    is_permanent_water: bool = Field(default=False, description="True if identified as permanent ocean or coastal water body")


class InundationPolygonGeometry(BaseModel):
    """GeoJSON Polygon geometry [exterior_ring, interior_ring1, ...]. Coordinates are [lon, lat]."""
    type: str = Field(default="Polygon", description="GeoJSON geometry type")
    coordinates: List[List[List[float]]] = Field(
        ...,
        description="Coordinates array: outer ring followed by optional interior hole rings",
    )


class InundationGeoJsonFeature(BaseModel):
    """Standard GeoJSON Feature containing inundation polygon and properties."""
    type: str = Field(default="Feature")
    geometry: InundationPolygonGeometry
    properties: InundationPolygonProperties


class InundationGeoJsonResponse(BaseModel):
    """Standard GeoJSON FeatureCollection of predicted inundation polygons."""
    type: str = Field(default="FeatureCollection")
    features: List[InundationGeoJsonFeature] = Field(default_factory=list)

