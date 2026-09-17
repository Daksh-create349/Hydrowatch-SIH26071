"""Comprehensive tests for Model 1 (XGBoost) and Model 2 (FloodUNet) real inference."""

from pathlib import Path
import numpy as np
import pytest
from starlette.testclient import TestClient

from backend.app.core.errors import ModelNotLoadedError
from backend.app.schemas.common import Coordinates
from backend.app.schemas.weather import WeatherFeatureVector
from backend.app.services.model1_service import MODEL1_FEATURE_ORDER, Model1Service
from backend.app.services.model2_service import Model2Service


@pytest.fixture
def sample_37_features() -> WeatherFeatureVector:
    """Fixture with valid 37 meteorological features."""
    return WeatherFeatureVector(
        PRECTOTCORR=12.5,
        T2M=28.5,
        T2MDEW=24.1,
        RH2M=82.0,
        PS=100.5,
        WS2M=3.4,
        WS10M=5.2,
        ALLSKY_SFC_SW_DWN=18.2,
        rain_lag_1d=5.0,
        rain_lag_2d=2.0,
        rain_lag_3d=0.0,
        rain_lag_7d=15.0,
        rain_lag_14d=30.0,
        rain_sum_prev_3d=7.0,
        rain_sum_prev_7d=22.0,
        rain_sum_prev_14d=52.0,
        rain_sum_prev_30d=110.0,
        rain_mean_prev_7d=3.14,
        rain_max_prev_7d=12.0,
        T2M_lag_1d=28.0,
        T2MDEW_lag_1d=24.0,
        RH2M_lag_1d=80.0,
        PS_lag_1d=100.4,
        WS2M_lag_1d=3.1,
        WS10M_lag_1d=4.9,
        ALLSKY_SFC_SW_DWN_lag_1d=17.8,
        temperature_change_1d=0.5,
        humidity_change_1d=2.0,
        pressure_change_1d=0.1,
        wind_change_1d=0.3,
        month=7,
        month_sin=-0.5,
        month_cos=-0.866,
        doy_sin=0.12,
        doy_cos=0.99,
        latitude=19.0760,
        longitude=72.8777,
    )


# ============================================================
# MODEL 1 (XGBOOST) TESTS
# ============================================================

def test_model1_loads_real_model():
    """Verify Model 1 loads real JSON checkpoint."""
    svc = Model1Service.get_instance()
    svc.load()
    assert svc.is_loaded is True
    assert svc.has_model_artifact() is True
    health = svc.get_health_detail()
    assert health["loaded"] is True
    assert health["model_type"] == "xgboost"
    assert health["threshold"] == 0.81


def test_model1_missing_file_raises():
    """Verify Model 1 with non-existent file fails clearly."""
    bad_svc = Model1Service(model_path="non_existent_xgboost_file.json")
    with pytest.raises(FileNotFoundError):
        bad_svc.load(force_reload=True)


def test_model1_real_inference(sample_37_features: WeatherFeatureVector):
    """Verify Model 1 real inference produces probability in [0, 1] and applies threshold 0.81."""
    svc = Model1Service.get_instance()
    svc.load()

    resp = svc.predict(sample_37_features)
    assert resp.model == "heavy_rainfall_xgboost_v2"
    assert 0.0 <= resp.probability <= 1.0
    assert resp.threshold == 0.81
    assert resp.heavy_rain == (resp.probability >= 0.81)
    assert resp.prediction in ("heavy_rain", "no_heavy_rain")
    assert resp.feature_count == 37


def test_model1_feature_order_integrity():
    """Verify exact 37 feature names and length."""
    assert len(MODEL1_FEATURE_ORDER) == 37
    assert MODEL1_FEATURE_ORDER[0] == "PRECTOTCORR"
    assert MODEL1_FEATURE_ORDER[-2] == "latitude"
    assert MODEL1_FEATURE_ORDER[-1] == "longitude"


def test_model1_repeated_prediction_reuses_instance(sample_37_features: WeatherFeatureVector):
    """Verify repeated prediction reuses loaded booster without reload."""
    svc = Model1Service.get_instance()
    svc.load()
    booster_before = svc._booster
    resp1 = svc.predict(sample_37_features)
    resp2 = svc.predict(sample_37_features)
    assert svc._booster is booster_before
    assert resp1.probability == resp2.probability


# ============================================================
# MODEL 2 (FLOODUNET) TESTS
# ============================================================

def test_model2_loads_real_checkpoint():
    """Verify Model 2 loads real PyTorch .pth checkpoint."""
    svc = Model2Service.get_instance()
    svc.load()
    assert svc.is_loaded is True
    assert svc.has_model_artifact() is True
    health = svc.get_health_detail()
    assert health["loaded"] is True
    assert health["model_type"] == "pytorch_unet"
    assert health["threshold"] == 0.5


def test_model2_missing_checkpoint_raises():
    """Verify Model 2 with non-existent checkpoint raises FileNotFoundError."""
    bad_svc = Model2Service(model_path="non_existent_unet_model.pth")
    with pytest.raises(FileNotFoundError):
        bad_svc.load(force_reload=True)


def test_model2_preprocessing_nan_and_scale():
    """Verify training preprocessing: /10000.0, non-finite to 0, clip [0, 1]."""
    svc = Model2Service.get_instance()
    raw = np.array([
        [[np.nan, 20000.0], [-500.0, 5000.0]],  # B2
        [[1000.0, 1000.0], [1000.0, 1000.0]],   # B3
        [[1000.0, 1000.0], [1000.0, 1000.0]],   # B4
        [[1000.0, 1000.0], [1000.0, 1000.0]],   # B8
        [[1000.0, 1000.0], [1000.0, 1000.0]],   # B11
        [[1000.0, 1000.0], [1000.0, 1000.0]],   # B12
    ], dtype=np.float32)

    tensor = svc.preprocess_tensor(raw)
    assert tensor.shape == (1, 6, 2, 2)
    # nan -> 0.0
    assert tensor[0, 0, 0, 0].item() == 0.0
    # 20000.0 / 10000.0 = 2.0 -> clipped to 1.0
    assert tensor[0, 0, 0, 1].item() == 1.0
    # -500.0 / 10000.0 = -0.05 -> clipped to 0.0
    assert tensor[0, 0, 1, 0].item() == 0.0
    # 5000.0 / 10000.0 = 0.5
    assert tensor[0, 0, 1, 1].item() == 0.5


def test_model2_channel_count_enforcement():
    """Verify arrays without exactly 6 channels are rejected."""
    svc = Model2Service.get_instance()
    # 5 channels instead of 6
    bad_arr = np.zeros((5, 64, 64), dtype=np.float32)
    with pytest.raises(ValueError) as exc:
        svc.preprocess_tensor(bad_arr)
    assert "Expected 6 input bands" in str(exc.value)


def test_model2_inference_deterministic_and_eval_mode():
    """Verify inference is deterministic and model remains in eval mode."""
    svc = Model2Service.get_instance()
    svc.load()
    assert svc._model.training is False

    # Small 6-channel tile (6, 32, 32)
    dummy_tile = np.full((6, 32, 32), 2000.0, dtype=np.float32)
    resp1 = svc.predict(dummy_tile)
    resp2 = svc.predict(dummy_tile)

    assert resp1.dimensions == [32, 32]
    assert resp1.water_pixel_count == resp2.water_pixel_count
    assert resp1.flooded_area_percentage == resp2.flooded_area_percentage
    assert resp1.probability_mask == resp2.probability_mask
    assert svc._model.training is False


# ============================================================
# API ENDPOINT TESTS
# ============================================================

def test_api_models_health(client: TestClient):
    """Verify GET /api/v1/models/health returns 200 with both models loaded."""
    response = client.get("/api/v1/models/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ("healthy", "degraded")
    assert "model1_heavy_rain_xgboost" in data["models"]
    assert "model2_flood_unet" in data["models"]
    m1 = data["models"]["model1_heavy_rain_xgboost"]
    assert m1["loaded"] is True
    assert m1["model_type"] == "xgboost"
    m2 = data["models"]["model2_flood_unet"]
    assert m2["loaded"] is True
    assert m2["model_type"] == "pytorch_unet"


def test_api_rainfall_predict(client: TestClient, sample_37_features: WeatherFeatureVector):
    """Verify POST /api/v1/models/rainfall/predict returns real prediction."""
    payload = {
        "location": {"latitude": 19.0760, "longitude": 72.8777},
        "features": sample_37_features.model_dump(),
    }
    response = client.post("/api/v1/models/rainfall/predict", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["model"] == "heavy_rainfall_xgboost_v2"
    assert "probability" in data
    assert 0.0 <= data["probability"] <= 1.0
    assert data["threshold"] == 0.81
    assert data["heavy_rain"] == (data["probability"] >= 0.81)


def test_api_rainfall_predict_missing_feature(client: TestClient, sample_37_features: WeatherFeatureVector):
    """Verify missing required meteorological feature produces 422 Unprocessable Entity."""
    feat_dict = sample_37_features.model_dump()
    del feat_dict["PRECTOTCORR"]
    payload = {"features": feat_dict}
    response = client.post("/api/v1/models/rainfall/predict", json=payload)
    assert response.status_code == 422


def test_api_inundation_predict_json(client: TestClient):
    """Verify POST /api/v1/models/inundation/predict produces valid segmentation."""
    # Create small 6-channel raster [6, 16, 16]
    small_tile = [[[1500.0] * 16 for _ in range(16)] for _ in range(6)]
    payload = {"bands": small_tile}
    response = client.post("/api/v1/models/inundation/predict", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["model"] == "flood_unet_sentinel2_6band"
    assert data["dimensions"] == [16, 16]
    assert data["total_valid_pixels"] == 256
    assert 0 <= data["water_pixel_count"] <= 256
    assert len(data["probability_mask"]) == 16
    assert len(data["binary_mask"]) == 16


def test_api_inundation_predict_bad_shape(client: TestClient):
    """Verify array with incorrect channel count returns 422."""
    # 4 channels instead of 6
    bad_tile = [[[1000.0] * 8 for _ in range(8)] for _ in range(4)]
    payload = {"bands": bad_tile}
    response = client.post("/api/v1/models/inundation/predict", json=payload)
    assert response.status_code == 422
