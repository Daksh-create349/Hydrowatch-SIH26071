"""Application configuration via Pydantic Settings."""

from functools import lru_cache
from pathlib import Path
from typing import List, Union

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration for backend application."""

    # Project metadata
    PROJECT_NAME: str = "SIH 2026 - Heavy Rainfall & Inundation Prediction System"
    APP_VERSION: str = "0.1.0"
    ENVIRONMENT: str = "development"
    API_PREFIX: str = "/api/v1"
    LOG_LEVEL: str = "INFO"

    # ML Model Checkpoints & Inference
    MODEL1_PATH: str = "models/best_heavy_rain_xgboost_v2.json"
    MODEL2_PATH: str = "models/best_model.pth"
    MODEL1_THRESHOLD: float = 0.81  # Frozen validation-selected decision threshold
    MODEL2_THRESHOLD: float = 0.5   # Standard segmentation probability threshold
    MODEL2_DEVICE: str = "auto"     # "auto", "cpu", "cuda", or "mps"

    # NASA POWER Meteorological API
    NASA_POWER_BASE_URL: str = "https://power.larc.nasa.gov/api/temporal/daily/point"
    NASA_POWER_COMMUNITY: str = "AG"
    NASA_POWER_TIMEOUT_SECONDS: float = 30.0
    NASA_POWER_MAX_RETRIES: int = 3

    # Numerical Weather Prediction (NWP) - Open-Meteo GFS API
    NWP_BASE_URL: str = "https://api.open-meteo.com/v1/forecast"
    NWP_MODEL: str = "gfs_seamless"
    NWP_TIMEOUT_SECONDS: float = 30.0
    NWP_MAX_RETRIES: int = 3

    # Doppler Weather Radar (DWR) - RainViewer Global Radar Composite API
    RADAR_BASE_URL: str = "https://api.rainviewer.com/public/weather-maps.json"
    RADAR_TILE_BASE_URL: str = "https://tilecache.rainviewer.com"
    RADAR_TIMEOUT_SECONDS: float = 30.0
    RADAR_MAX_RETRIES: int = 3

    # Sentinel-2 Multispectral Imagery - Earth Search STAC API
    SENTINEL_STAC_URL: str = "https://earth-search.aws.element84.com/v1"
    SENTINEL_COLLECTION: str = "sentinel-2-l2a"
    SENTINEL_TIMEOUT_SECONDS: float = 30.0
    SENTINEL_MAX_RETRIES: int = 3
    SENTINEL_DEFAULT_MAX_CLOUD_PERCENTAGE: float = 25.0
    SENTINEL_MIN_POLYGON_AREA_SQ_M: float = 500.0  # Min area for inundation vector polygon filter

    # Multi-Source Risk Fusion Weights (Must sum to 1.0)
    RISK_WEIGHT_RAINFALL: float = 0.35
    RISK_WEIGHT_NWP: float = 0.25
    RISK_WEIGHT_RADAR: float = 0.20
    RISK_WEIGHT_INUNDATION: float = 0.20

    # Risk Level Boundaries (Prototype decision thresholds, not official IMD)
    RISK_LOW_MAX: float = 0.30
    RISK_MODERATE_MAX: float = 0.60
    RISK_HIGH_MAX: float = 0.80

    # Satellite Staleness Limits (hours)
    SATELLITE_CURRENT_MAX_AGE_HOURS: float = 48.0
    SATELLITE_RECENT_MAX_AGE_HOURS: float = 168.0  # 7 days

    # Warning & Physical Trigger Thresholds (Prototype decision rules)
    TRIGGER_RAINFALL_PROBABILITY: float = 0.81
    TRIGGER_RAINFALL_OBSERVED_MM: float = 64.5  # IMD heavy rain definition (64.5 mm/day)
    TRIGGER_NWP_HOURLY_PRECIP_MM_HR: float = 20.0  # Intense convective downpour
    TRIGGER_NWP_ACCUMULATED_PRECIP_MM: float = 70.0  # Very heavy accumulation
    TRIGGER_RADAR_MAX_DBZ: float = 45.0  # Severe convective echo core
    TRIGGER_RADAR_RAIN_RATE_MM_HR: float = 30.0  # High instantaneous rainfall rate
    TRIGGER_INUNDATION_FLOODED_PCT: float = 10.0  # Significant ground ponding percentage
    TRIGGER_INUNDATION_AREA_SQ_KM: float = 5.0  # Significant flooded surface area
    WARNING_VALIDITY_RADAR_HOURS: float = 3.0  # Fast nowcast validity
    WARNING_VALIDITY_NWP_HOURS: float = 12.0  # Synoptic NWP validity
    WARNING_RULES_VERSION: str = "v1.0_prototype_sih2026"

    # Data Storage & Cache
    DATA_CACHE_DIR: str = "data_cache"

    # Security & CORS
    ALLOWED_ORIGINS: Union[List[str], str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ]

    @model_validator(mode="after")
    def validate_risk_weights_and_boundaries(self) -> "Settings":
        total_weight = (
            self.RISK_WEIGHT_RAINFALL
            + self.RISK_WEIGHT_NWP
            + self.RISK_WEIGHT_RADAR
            + self.RISK_WEIGHT_INUNDATION
        )
        if abs(total_weight - 1.0) > 1e-4:
            raise ValueError(f"Risk weights must sum to 1.0, got {total_weight:.4f}")

        if not (0.0 < self.RISK_LOW_MAX < self.RISK_MODERATE_MAX < self.RISK_HIGH_MAX < 1.0):
            raise ValueError(
                f"Risk boundaries must satisfy 0.0 < LOW ({self.RISK_LOW_MAX}) < "
                f"MODERATE ({self.RISK_MODERATE_MAX}) < HIGH ({self.RISK_HIGH_MAX}) < 1.0"
            )
        return self

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def parse_allowed_origins(cls, value: Union[str, List[str]]) -> List[str]:
        if isinstance(value, str):
            # Split comma-separated string if provided via environment variable
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() == "production"

    def resolve_model1_path(self, base_dir: Path | None = None) -> Path:
        """Resolve Model 1 path relative to project root or absolute."""
        p = Path(self.MODEL1_PATH)
        if p.is_absolute() and p.is_file():
            return p
        base = base_dir or Path.cwd()
        for candidate in [
            base / p,
            base / "models" / p.name,
            base.parent / "models" / p.name,
            base.parent / p.name,
            base / p.name,
        ]:
            if candidate.is_file():
                return candidate.resolve()
        return (base / p).resolve()

    def resolve_model2_path(self, base_dir: Path | None = None) -> Path:
        """Resolve Model 2 path relative to project root or absolute."""
        p = Path(self.MODEL2_PATH)
        if p.is_absolute() and p.is_file():
            return p
        base = base_dir or Path.cwd()
        for candidate in [
            base / p,
            base / "models" / p.name,
            base.parent / "models" / p.name,
            base.parent / p.name,
            base / p.name,
        ]:
            if candidate.is_file():
                return candidate.resolve()
        return (base / p).resolve()


@lru_cache()
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()
