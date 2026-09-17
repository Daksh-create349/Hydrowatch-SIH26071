"""Pytest fixtures and test configuration."""

import os
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

try:
    import xgboost as _xgb  # Pre-initialize XGBoost before PyTorch in pytest process
except ImportError:
    pass

import pytest
from starlette.testclient import TestClient

from backend.app.core.config import Settings, get_settings
from backend.app.main import create_app


@pytest.fixture(scope="session")
def test_settings() -> Settings:
    """Return test settings with deterministic configuration."""
    return Settings(
        ENVIRONMENT="testing",
        API_PREFIX="/api/v1",
        LOG_LEVEL="WARNING",
        MODEL1_PATH="best_heavy_rain_xgboost_v2.json",
        MODEL2_PATH="best_model.pth",
        ALLOWED_ORIGINS=["http://testserver"],
    )


@pytest.fixture
def client(test_settings: Settings) -> TestClient:
    """Provide TestClient with overridden settings."""
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: test_settings
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
