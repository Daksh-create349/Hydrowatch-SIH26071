"""Model inference prediction schemas and contracts."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from backend.app.schemas.common import Coordinates, GeoBoundingBox
from backend.app.schemas.weather import WeatherFeatureVector


# ============================================================
# MODEL 1 — HEAVY RAINFALL SCHEMAS
# ============================================================

class RainfallPredictionRequest(BaseModel):
    """Request payload for Model 1 (XGBoost Next-Day Heavy Rainfall)."""
    location: Optional[Coordinates] = Field(None, description="Target location coordinates (informational)")
    features: WeatherFeatureVector = Field(..., description="The 37 leakage-safe meteorological features")


class FeatureShapContribution(BaseModel):
    """Exact SHAP feature contribution for Explainable AI (XAI)."""
    feature_name: str = Field(..., description="Exact meteorological feature identifier")
    display_name: str = Field(..., description="Human-readable meteorological driver name")
    category: str = Field(..., description="Physical category: moisture, instability_pressure, antecedent_rainfall, temperature_wind, or climatology")
    observed_value: float = Field(..., description="Raw observed feature value")
    shap_value: float = Field(..., description="Exact Tree SHAP contribution value (log-odds impact)")
    impact: str = Field(..., description="'increases_risk', 'decreases_risk', or 'neutral'")
    percentage_contribution: float = Field(..., ge=0.0, le=100.0, description="Normalized relative impact percentage")
    description: str = Field(..., description="Physical atmospheric interpretation of this factor")


class RainfallXaiSummary(BaseModel):
    """Explainable AI (XAI) decomposition for Model 1 heavy rainfall prediction."""
    base_margin: float = Field(..., description="Model expected base rate log-odds")
    model_score_margin: float = Field(..., description="Final log-odds output before sigmoid")
    top_positive_drivers: List[FeatureShapContribution] = Field(default_factory=list, description="Top factors increasing heavy rain probability")
    top_negative_drivers: List[FeatureShapContribution] = Field(default_factory=list, description="Top factors suppressing heavy rain probability")
    all_contributions: List[FeatureShapContribution] = Field(default_factory=list, description="All 37 feature SHAP contributions sorted by magnitude")
    narrative: str = Field(..., description="Natural language scientific synthesis explaining why it rained this much")
    causality_chain: List[str] = Field(default_factory=list, description="Step-by-step physical causality mechanism")


class RainfallPredictionResponse(BaseModel):
    """Prediction output from Model 1 (XGBoost Next-Day Heavy Rainfall)."""
    model: str = Field(default="heavy_rainfall_xgboost_v2", description="Model identifier")
    probability: float = Field(..., ge=0.0, le=1.0, description="Predicted heavy rainfall probability [0.0, 1.0]")
    threshold: float = Field(..., ge=0.0, le=1.0, description="Applied decision threshold (frozen at 0.81)")
    heavy_rain: bool = Field(..., description="Binary classification (probability >= threshold)")
    prediction: str = Field(..., description="'heavy_rain' or 'no_heavy_rain'")
    feature_count: int = Field(default=37, description="Number of validated input features used")
    xai: Optional[RainfallXaiSummary] = Field(None, description="Explainable AI decomposition of prediction drivers")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Execution and debugging metadata")


class RainfallPrediction(BaseModel):
    """Domain model representing rainfall prediction result."""
    target_date: str = Field(..., description="Target forecast date (YYYY-MM-DD)")
    coordinates: Coordinates
    heavy_rain_probability: float = Field(..., ge=0.0, le=1.0, description="Predicted probability [0.0, 1.0]")
    is_heavy_rain: bool = Field(..., description="Binary classification based on decision threshold")
    decision_threshold: float = Field(default=0.81, ge=0.0, le=1.0, description="Applied probability threshold")
    model_version: str = Field(default="v2_xgboost")
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)


class RainfallPipelineRequest(BaseModel):
    """Request payload for real end-to-end weather ingestion + Model 1 prediction pipeline."""
    latitude: float = Field(..., ge=-90.0, le=90.0, description="Latitude in decimal degrees (-90 to 90)")
    longitude: float = Field(..., ge=-180.0, le=180.0, description="Longitude in decimal degrees (-180 to 180)")
    prediction_date: str = Field(..., description="Target prediction date in YYYY-MM-DD format")
    location_name: Optional[str] = Field(None, description="Optional descriptive location name")


class RainfallPipelineResponse(BaseModel):
    """Response payload for real end-to-end weather ingestion + Model 1 prediction pipeline."""
    status: str = Field(default="success", description="Pipeline execution status")
    prediction_date: str = Field(..., description="Target forecast date (YYYY-MM-DD)")
    observation_date: str = Field(..., description="Latest meteorological observation date used (D-1)")
    coordinates: Coordinates = Field(..., description="Target location coordinates")
    location_name: Optional[str] = Field(None, description="Location name if provided")
    heavy_rain_predicted: bool = Field(..., description="True if heavy rainfall predicted (prob >= threshold)")
    heavy_rain_probability: float = Field(..., ge=0.0, le=1.0, description="Predicted heavy rainfall probability [0.0, 1.0]")
    threshold: float = Field(default=0.81, description="Applied decision threshold (frozen at 0.81)")
    model_version: str = Field(default="heavy_rainfall_xgboost_v2", description="Model version")
    historical_records_used: int = Field(..., ge=30, description="Count of historical weather records used for lag features")
    features_computed: int = Field(default=37, description="Number of exact features computed")
    latest_weather: Dict[str, Any] = Field(..., description="Core meteorological variables on observation date (D-1)")
    xai: Optional[RainfallXaiSummary] = Field(None, description="Explainable AI decomposition of prediction drivers")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Pipeline timing and provenance metadata")


# ============================================================
# MODEL 2 — INUNDATION SEGMENTATION SCHEMAS
# ============================================================


class InundationRasterInput(BaseModel):
    """JSON array representation for Sentinel-2 6-band multispectral tile."""
    bands: List[List[List[float]]] = Field(
        ...,
        description="6-channel 2D raster array [6, H, W] corresponding to [B2, B3, B4, B8, B11, B12]",
    )
    bounding_box: Optional[GeoBoundingBox] = Field(None, description="Spatial extent if known")


class InundationPredictionResponse(BaseModel):
    """Prediction output from Model 2 (FloodUNet 6-band segmentation)."""
    model: str = Field(default="flood_unet_sentinel2_6band", description="Model identifier")
    dimensions: List[int] = Field(..., description="[height, width] of output mask")
    water_pixel_count: int = Field(..., ge=0, description="Count of pixels classified as water")
    total_valid_pixels: int = Field(..., gt=0, description="Total valid analyzed pixels")
    flooded_area_percentage: float = Field(..., ge=0.0, le=100.0, description="Percentage of valid pixels flooded")
    threshold: float = Field(default=0.5, description="Applied sigmoid segmentation threshold")
    device: str = Field(..., description="Hardware device used for inference (e.g. cpu, cuda, mps)")
    probability_mask: Optional[List[List[float]]] = Field(
        None, description="2D matrix of pixel water probabilities [H, W]"
    )
    binary_mask: Optional[List[List[int]]] = Field(
        None, description="2D binary mask [H, W] (1=water, 0=non-water)"
    )
    metadata: Dict[str, Any] = Field(default_factory=dict)


class InundationPrediction(BaseModel):
    """Domain model representing inundation prediction result."""
    scene_timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    bounding_box: GeoBoundingBox
    water_pixel_count: int = Field(..., ge=0)
    total_valid_pixels: int = Field(..., gt=0)
    flooded_area_percentage: float = Field(..., ge=0.0, le=100.0, description="Percentage of valid pixels flooded")
    estimated_flood_area_sq_km: Optional[float] = Field(None, ge=0.0)
    mask_raster_uri: Optional[str] = Field(None, description="URI or path to generated binary flood mask GeoTIFF")
    model_architecture: str = Field(default="FloodUNet")
    resolution_m: float = Field(default=10.0, description="Spatial resolution in meters")


class InundationPipelineRequest(BaseModel):
    """Request payload for real end-to-end Sentinel-2 -> Model 2 inundation prediction."""
    latitude: float = Field(..., ge=-90.0, le=90.0, description="Latitude in decimal degrees (-90 to 90)")
    longitude: float = Field(..., ge=-180.0, le=180.0, description="Longitude in decimal degrees (-180 to 180)")
    date: Optional[str] = Field(None, description="Target acquisition date in YYYY-MM-DD format (default: latest available)")
    max_cloud_percentage: Optional[float] = Field(default=25.0, ge=0.0, le=100.0, description="Maximum scene cloud cover percentage")
    min_polygon_area_sq_m: Optional[float] = Field(default=500.0, ge=0.0, description="Minimum polygon area to filter out single-pixel noise")
    location_name: Optional[str] = Field(None, description="Optional descriptive location name")


class InundationPipelineResponse(BaseModel):
    """Response payload for real end-to-end Sentinel-2 -> Model 2 inundation prediction."""
    status: str = Field(default="success", description="Pipeline execution status")
    requested_location: Coordinates = Field(..., description="Target query coordinates")
    location_name: Optional[str] = Field(None, description="Location name if provided")
    selected_scene: Dict[str, Any] = Field(..., description="Metadata of real Sentinel-2 scene analyzed")
    model_version: str = Field(default="flood_unet_sentinel2_6band", description="Model architecture")
    threshold: float = Field(default=0.5, description="Decision threshold applied to sigmoid probabilities")
    grid_resolution_m: float = Field(default=10.0, description="Common model grid resolution in meters")
    raster_dimensions: List[int] = Field(..., description="[height, width] of processed raster")
    valid_area_sq_km: float = Field(..., ge=0.0, description="Total valid surface area analyzed in square kilometers")
    flooded_area_sq_km: float = Field(..., ge=0.0, description="Total detected flooded surface area in square kilometers")
    flooded_percentage: float = Field(..., ge=0.0, le=100.0, description="Percentage of valid area inundated")
    polygon_count: int = Field(..., ge=0, description="Number of vector inundation polygons detected")
    geojson: Dict[str, Any] = Field(..., description="WGS84 GeoJSON FeatureCollection of inundation polygons")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Pipeline timing and provenance metadata")


# ============================================================
# MODEL HEALTH SCHEMAS
# ============================================================

class ModelHealthDetail(BaseModel):
    """Health and status metadata for an individual ML model."""
    loaded: bool
    path_configured: bool
    model_type: str
    checkpoint_path: str
    threshold: float
    device: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)


class ModelsHealthResponse(BaseModel):
    """Response payload for GET /api/v1/models/health."""
    status: str = Field("healthy", description="Overall models status")
    models: Dict[str, ModelHealthDetail]
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
