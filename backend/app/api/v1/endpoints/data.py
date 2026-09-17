"""Real external meteorological and remote sensing data endpoints."""

import logging
from fastapi import APIRouter, Query, status

from backend.app.schemas.common import Coordinates
from backend.app.schemas.nwp import NWPPointForecastResponse
from backend.app.schemas.radar import RadarDataResponse
from backend.app.services.nwp_service import NWPService
from backend.app.services.radar_service import RadarService

logger = logging.getLogger("rainfall_backend.api.v1.data")

router = APIRouter()


@router.get(
    "/nwp",
    response_model=NWPPointForecastResponse,
    status_code=status.HTTP_200_OK,
    summary="Real Numerical Weather Prediction (NWP) Forecast",
    description=(
        "Fetch real hourly atmospheric forecast from NOAA Global Forecast System (GFS 0.25° grid) "
        "via Open-Meteo API. Returns precipitation, temperature, humidity, pressure, wind, and CAPE."
    ),
)
async def get_nwp_forecast(
    latitude: float = Query(..., ge=-90.0, le=90.0, description="Latitude in decimal degrees (-90 to 90)"),
    longitude: float = Query(..., ge=-180.0, le=180.0, description="Longitude in decimal degrees (-180 to 180)"),
    forecast_days: int = Query(default=3, ge=1, le=16, description="Forecast horizon in days (1 to 16)"),
) -> NWPPointForecastResponse:
    """Query point-specific NWP forecast from NOAA GFS."""
    coords = Coordinates(latitude=latitude, longitude=longitude)
    logger.info("Serving NWP forecast request for (%f, %f), days=%d", latitude, longitude, forecast_days)
    service = NWPService()
    return await service.fetch_point_forecast(coords, forecast_days)


@router.get(
    "/radar",
    response_model=RadarDataResponse,
    status_code=status.HTTP_200_OK,
    summary="Real Doppler Weather Radar (DWR) Reflectivity",
    description=(
        "Fetch latest operational Doppler Weather Radar composite from RainViewer Radar Network. "
        "Calculates georeferenced bounding box, peak reflectivity in dBZ, active echo coverage, "
        "and estimated rainfall intensity via Marshall-Palmer Z-R relation."
    ),
)
async def get_radar_reflectivity(
    latitude: float = Query(..., ge=-90.0, le=90.0, description="Latitude in decimal degrees (-90 to 90)"),
    longitude: float = Query(..., ge=-180.0, le=180.0, description="Longitude in decimal degrees (-180 to 180)"),
    zoom: int = Query(default=6, ge=0, le=14, description="Web Mercator zoom level (0 to 14, default 6)"),
) -> RadarDataResponse:
    """Query live Doppler radar composite for geographic coordinates."""
    coords = Coordinates(latitude=latitude, longitude=longitude)
    logger.info("Serving Doppler radar request for (%f, %f), zoom=%d", latitude, longitude, zoom)
    service = RadarService()
    return await service.fetch_radar_composite(coords, zoom_level=zoom)
