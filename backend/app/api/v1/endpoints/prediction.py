"""Prediction pipeline API endpoints."""

from datetime import datetime
import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, status

from backend.app.core.errors import WeatherObservationValidationError
from backend.app.schemas.common import Coordinates
from backend.app.schemas.prediction import (
    InundationPipelineRequest,
    InundationPipelineResponse,
    RainfallPipelineRequest,
    RainfallPipelineResponse,
)
from backend.app.schemas.risk import (
    RiskAssessmentRequest,
    RiskAssessmentResponse,
)
from backend.app.schemas.unified import (
    UnifiedPredictionRequest,
    UnifiedPredictionResponse,
)
from backend.app.schemas.warning import (
    WarningAssessmentRequest,
    WarningDecisionResponse,
)
from backend.app.services.risk_assessment_service import RiskAssessmentService
from backend.app.services.unified_prediction_service import UnifiedPredictionService
from backend.app.services.warning_service import WarningService
from backend.app.services.weather_service import WeatherObservationService

logger = logging.getLogger("rainfall_backend.api.v1.prediction")

router = APIRouter()


@router.post(
    "/rainfall",
    response_model=RainfallPipelineResponse,
    status_code=status.HTTP_200_OK,
    summary="Real Next-Day Heavy Rainfall Prediction Pipeline",
    description=(
        "Fetch real meteorological observations from NASA POWER Daily API for the past 30+ days, "
        "construct the exact 37 Model 1 features without future leakage, and infer heavy rainfall "
        "probability using the trained XGBoost model."
    ),
)
async def predict_rainfall_pipeline(request: RainfallPipelineRequest) -> RainfallPipelineResponse:
    """
    End-to-end heavy rainfall prediction workflow:
    1. Validate coordinates and target prediction date
    2. Query NASA POWER Daily Point API for historical records
    3. Build exact 37 features (D-1 observation, lags, rolling stats, cyclical encodings)
    4. Run real Model 1 XGBoost inference
    5. Return complete prediction payload
    """
    try:
        parsed_date = datetime.strptime(request.prediction_date, "%Y-%m-%d").date()
    except ValueError as err:
        raise WeatherObservationValidationError(
            f"Invalid prediction_date format: '{request.prediction_date}'. Expected 'YYYY-MM-DD'."
        ) from err

    coords = Coordinates(latitude=request.latitude, longitude=request.longitude)

    logger.info(
        "Initiating rainfall prediction pipeline for (%f, %f) on date %s",
        coords.latitude,
        coords.longitude,
        parsed_date,
    )

    weather_service = WeatherObservationService()

    return await weather_service.predict_rainfall(
        coordinates=coords,
        prediction_date=parsed_date,
        location_name=request.location_name,
    )


@router.post(
    "/inundation",
    response_model=InundationPipelineResponse,
    status_code=status.HTTP_200_OK,
    summary="Real Sentinel-2 to Model 2 Flood Inundation Pipeline",
    description=(
        "Discover real Sentinel-2 Level-2A imagery from Element 84 Earth Search STAC catalog, "
        "download and align the 6 required spectral bands onto a common 10m grid, run Model 2 "
        "PyTorch FloodUNet inference using 512x512 windowing, reconstruct a seamless probability mosaic, "
        "vectorize the binary inundation mask into WGS84 GeoJSON polygons, and return geodesic area statistics."
    ),
)
async def predict_inundation_pipeline(request: InundationPipelineRequest) -> InundationPipelineResponse:
    """
    End-to-end satellite inundation prediction pipeline:
    1. Validate coordinates and optional acquisition date
    2. Query Earth Search STAC catalog and select optimal real scene
    3. Stream/extract 6 bands (B2, B3, B4, B8, B11, B12)
    4. Resample 20m bands to 10m common grid
    5. Windowed Model 2 PyTorch FloodUNet inference (threshold 0.5)
    6. Vectorize into WGS84 GeoJSON polygons with holes and filter noise
    7. Calculate geodesic surface area statistics
    """
    from backend.app.schemas.prediction import InundationPipelineRequest, InundationPipelineResponse
    from backend.app.services.satellite_imagery_service import SatelliteImageryService

    parsed_date = None
    if request.date:
        try:
            parsed_date = datetime.strptime(request.date, "%Y-%m-%d").date()
        except ValueError as err:
            raise WeatherObservationValidationError(
                f"Invalid date format: '{request.date}'. Expected 'YYYY-MM-DD'."
            ) from err

    logger.info(
        "Initiating Sentinel-2 inundation prediction pipeline for (%f, %f), date=%s, max_cloud=%.1f%%",
        request.latitude,
        request.longitude,
        parsed_date,
        request.max_cloud_percentage,
    )

    satellite_service = SatelliteImageryService()
    return await satellite_service.predict_inundation(
        latitude=request.latitude,
        longitude=request.longitude,
        target_date=parsed_date,
        max_cloud_percentage=request.max_cloud_percentage,
        min_polygon_area_sq_m=request.min_polygon_area_sq_m,
        location_name=request.location_name,
    )


@router.post(
    "/risk",
    response_model=RiskAssessmentResponse,
    status_code=status.HTTP_200_OK,
    summary="Real Multi-Source Flood-Risk Assessment & Fusion",
    description=(
        "Concurrently ingest real environmental data across 4 independent sources: Model 1 XGBoost "
        "heavy rainfall prediction (NASA POWER), NOAA GFS NWP forecast (Open-Meteo), RainViewer "
        "Doppler radar nowcast, and Sentinel-2 Level-2A inundation segmentation (Model 2 FloodUNet). "
        "Applies deterministic risk fusion, dynamic weight renormalization under missing-source "
        "policy, temporal freshness discounting, mathematical explainability decomposition, and "
        "prototype warning candidate generation."
    ),
)
async def assess_multi_source_risk(request: RiskAssessmentRequest) -> RiskAssessmentResponse:
    """
    End-to-end multi-source flood risk assessment workflow:
    1. Validate coordinates and optional target prediction date
    2. Concurrently ingest real observations/forecasts from NASA, NOAA GFS, RainViewer, and Sentinel-2
    3. Run Model 1 heavy rainfall inference and Model 2 FloodUNet segmentation
    4. Apply missing-source policy: renormalize weights if >=2 sources available, 422 if <2
    5. Compute normalized scores, composite risk, and explainability breakdown
    6. Derive prototype warning candidate with triggers, urgency, and disclaimer
    """
    parsed_date = None
    if request.prediction_date:
        try:
            parsed_date = datetime.strptime(request.prediction_date, "%Y-%m-%d").date()
        except ValueError as err:
            raise WeatherObservationValidationError(
                f"Invalid prediction_date format: '{request.prediction_date}'. Expected 'YYYY-MM-DD'."
            ) from err

    logger.info(
        "Initiating multi-source risk assessment for (%f, %f), target_date=%s, nwp_horizon=%dh",
        request.latitude,
        request.longitude,
        parsed_date,
        request.nwp_horizon_hours or 24,
    )

    risk_service = RiskAssessmentService()
    return await risk_service.assess_risk(
        latitude=request.latitude,
        longitude=request.longitude,
        prediction_date=parsed_date,
        nwp_horizon_hours=request.nwp_horizon_hours or 24,
        satellite_max_cloud=request.satellite_max_cloud if request.satellite_max_cloud is not None else 25.0,
        location_name=request.location_name,
    )


@router.post(
    "/warning",
    response_model=WarningDecisionResponse,
    status_code=status.HTTP_200_OK,
    summary="Deterministic Multi-Source Flood Warning Decision & Trigger Evaluation",
    description=(
        "Concurrently ingest and evaluate multi-source environmental risk (Model 1 XGBoost, "
        "NOAA GFS NWP, RainViewer Doppler radar, and Sentinel-2 / Model 2 FloodUNet) and derive a "
        "machine-readable warning decision. Computes concrete physical trigger metrics, deterministic "
        "operational states (NO_ALERT, MONITOR, PREPARE, ACTION, INSUFFICIENT_DATA), data freshness, "
        "forward temporal validity, physical burst discrepancy disclosures, and model provenance. "
        "Strictly labeled as prototype_only."
    ),
)
async def evaluate_warning_decision(request: WarningAssessmentRequest) -> WarningDecisionResponse:
    """
    End-to-end deterministic warning decision workflow:
    1. Validate coordinates and optional prediction date
    2. Concurrently evaluate multi-source risk via RiskAssessmentService
    3. Evaluate concrete physical triggers (rainfall, NWP, radar, inundation)
    4. Execute state machine mapping (NO_ALERT, MONITOR, PREPARE, ACTION, INSUFFICIENT_DATA)
    5. Evaluate data freshness, staleness discounts, and forward temporal validity
    6. Derive provenance metadata and structured explainable trigger reasons
    """
    parsed_date = None
    if request.prediction_date:
        try:
            parsed_date = datetime.strptime(request.prediction_date, "%Y-%m-%d").date()
        except ValueError as err:
            raise WeatherObservationValidationError(
                f"Invalid prediction_date format: '{request.prediction_date}'. Expected 'YYYY-MM-DD'."
            ) from err

    logger.info(
        "Initiating warning decision evaluation for (%f, %f), target_date=%s, nwp_horizon=%dh",
        request.latitude,
        request.longitude,
        parsed_date,
        request.nwp_horizon_hours or 24,
    )

    risk_service = RiskAssessmentService()
    risk_response = await risk_service.assess_risk(
        latitude=request.latitude,
        longitude=request.longitude,
        prediction_date=parsed_date,
        nwp_horizon_hours=request.nwp_horizon_hours or 24,
        satellite_max_cloud=request.satellite_max_cloud if request.satellite_max_cloud is not None else 25.0,
        location_name=request.location_name,
    )

    warning_service = WarningService()
    return warning_service.evaluate_warning(risk_response)


@router.post(
    "",
    response_model=UnifiedPredictionResponse,
    status_code=status.HTTP_200_OK,
    summary="Unified End-to-End Flood Risk & Early Warning Prediction Pipeline",
    description=(
        "Unified orchestrator endpoint for the integrated heavy rainfall early warning and inundation "
        "prediction system (SIH 2026 Problem Statement 26071). Concurrently collects real environmental "
        "evidence across 4 independent sources: Model 1 XGBoost heavy rainfall probability (NASA POWER), "
        "NOAA GFS NWP forecast (Open-Meteo), RainViewer Doppler radar nowcast, and Sentinel-2 Level-2A "
        "inundation segmentation (Model 2 PyTorch FloodUNet). Executes deterministic risk fusion, "
        "dynamic missing-source weight renormalization, physical trigger evaluations, forward temporal "
        "validity calculation, and returns full vector GeoJSON inundation polygons, source health statuses, "
        "execution latencies, and audit provenance. Strictly labeled as prototype_only."
    ),
)
@router.post(
    "/",
    response_model=UnifiedPredictionResponse,
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
async def unified_prediction_pipeline(request: UnifiedPredictionRequest) -> UnifiedPredictionResponse:
    """
    Unified end-to-end multi-source flood prediction pipeline:
    1. Validate geographic coordinates, prediction date, and satellite parameters
    2. Concurrently ingest real data across Weather, NWP, Radar, and Satellite
    3. Run Model 1 XGBoost inference and Model 2 PyTorch FloodUNet segmentation
    4. Execute multi-source risk fusion with dynamic missing-source policy (>=2 sources required)
    5. Evaluate deterministic physical triggers and state machine warning decision
    6. Return frontend-ready payload with metrics, GeoJSON polygons, latency breakdown, and provenance
    """
    logger.info(
        "Initiating unified prediction pipeline for (%f, %f), prediction_date=%s, nwp_horizon=%dh",
        request.latitude,
        request.longitude,
        request.prediction_date,
        request.nwp_horizon_hours or 24,
    )

    unified_service = UnifiedPredictionService()
    return await unified_service.predict(request)



