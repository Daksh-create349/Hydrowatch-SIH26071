"""Tests for application settings and configuration."""

from pathlib import Path
from backend.app.core.config import Settings


def test_default_settings():
    """Verify default settings instantiation."""
    settings = Settings()
    assert settings.ENVIRONMENT in ("development", "production", "testing")
    assert settings.API_PREFIX == "/api/v1"
    assert settings.LOG_LEVEL in ("DEBUG", "INFO", "WARNING", "ERROR")
    assert isinstance(settings.ALLOWED_ORIGINS, list)
    assert len(settings.ALLOWED_ORIGINS) >= 1


def test_allowed_origins_string_parsing():
    """Verify comma-separated ALLOWED_ORIGINS string is properly converted to list."""
    settings = Settings(ALLOWED_ORIGINS="http://example.com, https://app.example.com")
    assert isinstance(settings.ALLOWED_ORIGINS, list)
    assert "http://example.com" in settings.ALLOWED_ORIGINS
    assert "https://app.example.com" in settings.ALLOWED_ORIGINS


def test_model_path_resolution(tmp_path: Path):
    """Verify model path resolution logic."""
    model_file = tmp_path / "custom_model.json"
    model_file.touch()

    settings = Settings(MODEL1_PATH="custom_model.json")
    resolved = settings.resolve_model1_path(base_dir=tmp_path)
    assert resolved == model_file
    assert resolved.exists()
