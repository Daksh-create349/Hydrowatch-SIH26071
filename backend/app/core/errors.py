"""Custom domain exceptions and FastAPI exception handlers."""

import logging
from typing import Any, Dict, Optional

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("rainfall_backend.errors")


class AppException(Exception):
    """Base exception for application domain errors."""

    def __init__(
        self,
        message: str,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        code: str = "INTERNAL_ERROR",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code
        self.details = details or {}


class ServiceUnavailableError(AppException):
    """Raised when an external service or internal subsystem is not ready or unconnected."""

    def __init__(
        self,
        message: str = "Service is not connected or currently unavailable",
        service_name: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        d = details or {}
        if service_name:
            d["service_name"] = service_name
        super().__init__(
            message=message,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code="SERVICE_UNAVAILABLE",
            details=d,
        )


class ModelNotLoadedError(AppException):
    """Raised when an ML model artifact is missing or failed to initialize."""

    def __init__(
        self,
        model_name: str,
        path: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        d = details or {}
        d["model_name"] = model_name
        if path:
            d["configured_path"] = path
        super().__init__(
            message=f"Model '{model_name}' is not loaded or file is missing",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code="MODEL_NOT_LOADED",
            details=d,
        )


class EntityNotFoundError(AppException):
    """Raised when a requested resource is not found."""

    def __init__(self, entity_name: str, identifier: Any):
        super().__init__(
            message=f"{entity_name} with identifier '{identifier}' not found",
            status_code=status.HTTP_404_NOT_FOUND,
            code="NOT_FOUND",
            details={"entity": entity_name, "identifier": str(identifier)},
        )


class ExternalApiError(AppException):
    """Raised when an upstream external API fails, returns bad payload, or times out."""

    def __init__(
        self,
        service_name: str,
        message: str,
        status_code: int = status.HTTP_502_BAD_GATEWAY,
        details: Optional[Dict[str, Any]] = None,
    ):
        d = details or {}
        d["service_name"] = service_name
        super().__init__(
            message=message,
            status_code=status_code,
            code="EXTERNAL_API_ERROR",
            details=d,
        )


class InsufficientHistoricalDataError(AppException):
    """Raised when weather history lacks required lookback window."""

    def __init__(
        self,
        message: str,
        required_days: int,
        available_days: int,
        details: Optional[Dict[str, Any]] = None,
    ):
        d = details or {}
        d["required_days"] = required_days
        d["available_days"] = available_days
        super().__init__(
            message=message,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code="INSUFFICIENT_HISTORICAL_DATA",
            details=d,
        )


class WeatherObservationValidationError(AppException):
    """Raised when received meteorological data is corrupt, non-finite, or missing required variables."""

    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code="WEATHER_DATA_INVALID",
            details=details or {},
        )


class SatelliteDataUnavailableError(AppException):
    """Raised when no suitable satellite scene matches criteria or imagery is unavailable."""

    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            status_code=status.HTTP_404_NOT_FOUND,
            code="SATELLITE_DATA_UNAVAILABLE",
            details=details or {},
        )


class SatelliteBandReadError(AppException):
    """Raised when satellite band asset cannot be downloaded, parsed, or resampled."""

    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            status_code=status.HTTP_502_BAD_GATEWAY,
            code="SATELLITE_BAND_READ_ERROR",
            details=details or {},
        )



def setup_exception_handlers(app: FastAPI) -> None:
    """Register centralized exception handlers on the FastAPI instance."""

    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
        logger.warning("Application error: %s (code=%s, status=%d)", exc.message, exc.code, exc.status_code)
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details,
                },
                "success": False,
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        logger.info("Validation error on %s: %s", request.url.path, exc.errors())
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Request payload failed schema validation",
                    "details": {"errors": exc.errors()},
                },
                "success": False,
            },
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        logger.info("HTTP exception on %s: %d - %s", request.url.path, exc.status_code, exc.detail)
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": "HTTP_ERROR",
                    "message": str(exc.detail),
                    "details": {},
                },
                "success": False,
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled server exception: %s", str(exc))
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": {
                    "code": "INTERNAL_SERVER_ERROR",
                    "message": "An unexpected server error occurred.",
                    "details": {},
                },
                "success": False,
            },
        )
