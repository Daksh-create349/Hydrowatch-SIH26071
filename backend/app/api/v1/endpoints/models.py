"""Model inference and health API endpoints."""

import logging
from typing import Optional
from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
import numpy as np

from backend.app.schemas.prediction import (
    InundationPredictionResponse,
    InundationRasterInput,
    ModelHealthDetail,
    ModelsHealthResponse,
    RainfallPredictionRequest,
    RainfallPredictionResponse,
)
from backend.app.services.model1_service import Model1Service
from backend.app.services.model2_service import Model2Service

logger = logging.getLogger("rainfall_backend.api.v1.models")

router = APIRouter()


@router.get(
    "/health",
    response_model=ModelsHealthResponse,
    summary="ML Models Health & Status",
    description="Inspect real in-memory load state, configured path, and execution device for Model 1 & 2.",
)
def get_models_health() -> ModelsHealthResponse:
    m1 = Model1Service.get_instance()
    m2 = Model2Service.get_instance()

    h1 = m1.get_health_detail()
    h2 = m2.get_health_detail()

    overall_healthy = h1["loaded"] and h2["loaded"]

    return ModelsHealthResponse(
        status="healthy" if overall_healthy else "degraded",
        models={
            "model1_heavy_rain_xgboost": ModelHealthDetail(
                loaded=h1["loaded"],
                path_configured=h1["path_configured"],
                model_type=h1["model_type"],
                checkpoint_path=h1["checkpoint_path"],
                threshold=h1["threshold"],
                device=h1["device"],
                details=h1["details"],
            ),
            "model2_flood_unet": ModelHealthDetail(
                loaded=h2["loaded"],
                path_configured=h2["path_configured"],
                model_type=h2["model_type"],
                checkpoint_path=h2["checkpoint_path"],
                threshold=h2["threshold"],
                device=h2["device"],
                details=h2["details"],
            ),
        },
    )


@router.post(
    "/rainfall/predict",
    response_model=RainfallPredictionResponse,
    summary="Predict Next-Day Heavy Rainfall",
    description="Execute real Model 1 (XGBoost) inference with 37 leakage-safe meteorological features.",
)
def predict_rainfall(request: RainfallPredictionRequest) -> RainfallPredictionResponse:
    m1 = Model1Service.get_instance()
    return m1.predict(features=request.features, location=request.location)


@router.post(
    "/inundation/predict",
    response_model=InundationPredictionResponse,
    summary="Predict Flood Inundation Segmentation (JSON array)",
    description="Execute real Model 2 (FloodUNet) segmentation on a 6-band Sentinel-2 array [6, H, W].",
)
def predict_inundation_json(payload: InundationRasterInput) -> InundationPredictionResponse:
    m2 = Model2Service.get_instance()
    try:
        arr = np.array(payload.bands, dtype=np.float32)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid array structure for bands: {exc}",
        )

    if arr.ndim != 3 or arr.shape[0] != 6:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Expected shape [6, H, W] for 6 Sentinel-2 bands, got {arr.shape}",
        )

    return m2.predict(raster_data=arr, bounding_box=payload.bounding_box)


@router.post(
    "/inundation/predict-raster",
    response_model=InundationPredictionResponse,
    summary="Predict Flood Inundation Segmentation (Raster file upload)",
    description="Upload a 6-band GeoTIFF or NumPy (.npy) file [6, H, W] for real flood segmentation.",
)
async def predict_inundation_file(
    file: UploadFile = File(..., description="6-band raster (.npy or .tif)"),
    return_masks: bool = Form(default=True),
) -> InundationPredictionResponse:
    m2 = Model2Service.get_instance()

    filename = (file.filename or "").lower()
    content = await file.read()

    if filename.endswith(".npy"):
        try:
            import io
            arr = np.load(io.BytesIO(content))
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Failed to decode NumPy raster: {exc}",
            )
    elif filename.endswith((".tif", ".tiff")):
        try:
            import io
            import tifffile
            arr = tifffile.imread(io.BytesIO(content))
            # If shape is (H, W, 6), transpose to (6, H, W)
            if arr.ndim == 3 and arr.shape[2] == 6:
                arr = np.transpose(arr, (2, 0, 1))
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Failed to decode GeoTIFF raster: {exc}",
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Unsupported file format. Please upload .npy or .tif/.tiff with 6 bands.",
        )

    if arr.ndim != 3 or arr.shape[0] != 6:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Expected 6 bands [B2, B3, B4, B8, B11, B12] as first dimension, got shape {arr.shape}",
        )

    return m2.predict(raster_data=arr, return_masks=return_masks)
