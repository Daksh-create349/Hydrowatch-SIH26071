"""FastAPI application entry point."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from backend.app.api.v1.endpoints.health import get_health
from backend.app.api.v1.router import api_v1_router
from backend.app.core.config import get_settings
from backend.app.core.errors import setup_exception_handlers
from backend.app.core.logging import setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan context manager for application startup and shutdown events."""
    settings = get_settings()
    logger = setup_logging(settings.LOG_LEVEL)
    logger.info("Initializing backend application: %s (v%s)", settings.PROJECT_NAME, settings.APP_VERSION)
    logger.info("Operating environment: %s", settings.ENVIRONMENT)
    logger.info("CORS allowed origins configured: %s", settings.ALLOWED_ORIGINS)

    # Preload ML models during application startup
    try:
        from backend.app.services.model1_service import Model1Service
        m1 = Model1Service.get_instance()
        m1.load()
        logger.info("Model 1 (XGBoost) successfully loaded during startup.")
    except Exception as exc:
        logger.warning("Model 1 was not loaded during startup: %s", exc)

    try:
        from backend.app.services.model2_service import Model2Service
        m2 = Model2Service.get_instance()
        m2.load()
        logger.info("Model 2 (FloodUNet) successfully loaded during startup.")
    except Exception as exc:
        logger.warning("Model 2 was not loaded during startup: %s", exc)

    yield
    logger.info("Shutting down backend application.")


def create_app() -> FastAPI:
    """Application factory for FastAPI instance."""
    settings = get_settings()

    app = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.APP_VERSION,
        description=(
            "AI/ML-Based Integrated Heavy Rainfall Early Warning and Inundation Prediction System "
            "using Satellite, Radar, Observational Weather and Numerical Weather Prediction Model Data. "
            "(SIH 2026 Problem Statement 26071 - MoES / IMD)"
        ),
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # CORS configuration
    origins = settings.ALLOWED_ORIGINS
    if isinstance(origins, str):
        origins = [orig.strip() for orig in origins.split(",") if orig.strip()]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    # Register centralized exception handlers
    setup_exception_handlers(app)

    # Top-level direct /health convenience route
    app.add_api_route(
        "/health",
        get_health,
        methods=["GET"],
        tags=["System Health"],
        summary="Direct System Health Check",
    )

    # Versioned API routes (/api/v1/...)
    app.include_router(api_v1_router, prefix=settings.API_PREFIX)

    @app.get("/", include_in_schema=False)
    async def root_redirect():
        """Redirect root requests to interactive documentation."""
        return RedirectResponse(url="/docs")

    return app


app = create_app()
