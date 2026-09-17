"""Doppler Weather Radar observation schemas and data contracts."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from backend.app.schemas.common import Coordinates, GeoBoundingBox


class RadarFrameMetadata(BaseModel):
    """Metadata for a single radar scan frame in temporal catalog."""
    time: int = Field(..., description="Unix epoch timestamp in seconds")
    timestamp_iso: str = Field(..., description="ISO 8601 formatted UTC timestamp")
    path: str = Field(..., description="Relative API path to radar tile dataset")
    frame_type: str = Field(default="past", description="'past' observation or 'nowcast' extrapolation")


class RadarTileReflectivity(BaseModel):
    """Normalized Doppler Weather Radar tile reflectivity summary and georeferencing."""
    source: str = Field(default="RainViewer Global Doppler Radar Composite", description="Radar data provider")
    radar_product: str = Field(default="DWR_MAXZ_COMPOSITE", description="Radar product name")
    timestamp_iso: str = Field(..., description="Scan acquisition timestamp (ISO 8601 UTC)")
    unix_timestamp: int = Field(..., description="Unix timestamp of radar scan")
    requested_coordinates: Coordinates = Field(..., description="Point of interest coordinates")
    bounding_box: GeoBoundingBox = Field(..., description="Geographic bounding box of radar tile")
    zoom_level: int = Field(..., ge=0, le=16, description="Web Mercator zoom level")
    tile_x: int = Field(..., ge=0, description="Slippy map tile column index X")
    tile_y: int = Field(..., ge=0, description="Slippy map tile row index Y")
    dimensions: List[int] = Field(default=[256, 256], description="[height, width] of tile in pixels")
    total_tile_pixels: int = Field(default=65536, description="Total pixels in tile")
    active_echo_pixels: int = Field(..., ge=0, description="Pixels with detectable precipitation echoes (dBZ >= 5)")
    echo_coverage_pct: float = Field(..., ge=0.0, le=100.0, description="Precipitation echo spatial coverage percentage")
    max_reflectivity_dbz: float = Field(..., description="Peak observed radar reflectivity in dBZ")
    mean_reflectivity_dbz: float = Field(..., description="Average reflectivity across active echo pixels (dBZ)")
    estimated_max_rain_rate_mm_hr: float = Field(..., ge=0.0, description="Estimated peak rainfall rate using Marshall-Palmer Z-R relation")
    reflectivity_scale: str = Field(default="5 to 75 dBZ (Marshall-Palmer Z=200*R^1.6)", description="Z-R conversion calibration")
    tile_url: str = Field(..., description="Direct HTTPS URI to radar raster tile")


class RadarDataResponse(BaseModel):
    """Normalized response payload for Doppler radar queries."""
    status: str = Field(default="success", description="Query status")
    source: str = Field(default="RainViewer Global Doppler Radar Composite", description="Radar data provider")
    latest_scan: RadarTileReflectivity = Field(..., description="Most recent georeferenced radar scan")
    available_frames_count: int = Field(..., ge=0, description="Total active scan frames in catalog")
    recent_scans: List[RadarFrameMetadata] = Field(default_factory=list, description="Chronological list of recent scan frames")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Radar network provenance metadata")


class RadarObservation(BaseModel):
    """Observation from a Doppler Weather Radar (DWR) station (foundation schema)."""
    radar_station_id: str = Field(..., description="IMD radar station code, e.g., 'MUMBAI_DWR'")
    timestamp: datetime = Field(..., description="Scan acquisition timestamp in UTC")
    station_coordinates: Coordinates
    max_reflectivity_dbz: Optional[float] = Field(None, description="Maximum reflectivity in dBZ")
    estimated_rainfall_intensity_mm_hr: Optional[float] = Field(None, ge=0.0)
    radial_velocity_max_ms: Optional[float] = None
    scan_elevation_angle_deg: Optional[float] = None


class RadarReflectivityGrid(BaseModel):
    """Gridded radar reflectivity product (e.g. CAPPI / MAX-Z composite)."""
    radar_station_id: str
    timestamp: datetime
    bounding_box: GeoBoundingBox
    grid_resolution_km: float = Field(..., gt=0.0)
    grid_shape: List[int] = Field(..., description="[height, width]")
    max_dbz: float
    data_uri: Optional[str] = None
