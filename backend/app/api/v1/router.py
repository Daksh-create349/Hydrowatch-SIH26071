from fastapi import APIRouter
from backend.app.api.v1.endpoints import data, health, models, prediction

api_v1_router = APIRouter()

# Register endpoint routers
api_v1_router.include_router(health.router, tags=["System Health"])
api_v1_router.include_router(models.router, prefix="/models", tags=["ML Model Inference"])
api_v1_router.include_router(prediction.router, prefix="/predict", tags=["Rainfall & Inundation Prediction"])
api_v1_router.include_router(data.router, prefix="/data", tags=["Meteorological & Radar Feeds"])


