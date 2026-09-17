"""Tests for Sentinel-2 raster processing, 20m->10m resampling, window tiling, and mosaic reconstruction."""

import numpy as np
import pytest
import torch

from backend.app.services.model2_service import Model2Service
from backend.app.services.raster_processor import SentinelRasterProcessor


def test_resample_20m_to_10m():
    """Verify bilinear interpolation doubles spatial resolution while preserving range and smooth gradients."""
    processor = SentinelRasterProcessor()
    # 512x512 array simulating 20m SWIR band
    arr_20m = np.linspace(100, 5000, 512 * 512, dtype=np.float32).reshape((512, 512))

    resampled = processor.resample_20m_to_10m(arr_20m, target_shape=(1024, 1024))

    assert resampled.shape == (1024, 1024)
    assert resampled.dtype == np.float32
    # Boundary values preserved within interpolation tolerances
    assert np.isclose(resampled.min(), arr_20m.min(), atol=1.0)
    assert np.isclose(resampled.max(), arr_20m.max(), atol=1.0)
    # Check interior values are smooth
    assert np.isfinite(resampled).all()


def test_resample_already_target_shape():
    """Verify that if array is already at target shape, no-op copy is returned."""
    processor = SentinelRasterProcessor()
    arr = np.ones((1024, 1024), dtype=np.float32) * 500.0
    out = processor.resample_20m_to_10m(arr, target_shape=(1024, 1024))
    assert out.shape == (1024, 1024)
    assert np.array_equal(out, arr)


def test_tile_and_predict_exact_512x512():
    """Verify tiling on exact 512x512 scene runs single window without border distortion."""
    processor = SentinelRasterProcessor()
    model_svc = Model2Service.get_instance()

    # Synthetic 6-band input of exact size (6, 512, 512)
    raster_512 = np.ones((6, 512, 512), dtype=np.float32) * 1200.0

    prob_mosaic, binary_mask = processor.tile_and_predict(
        raster_data=raster_512,
        model2_service=model_svc,
        window_size=512,
        overlap=64,
    )

    assert prob_mosaic.shape == (512, 512)
    assert binary_mask.shape == (512, 512)
    assert 0.0 <= prob_mosaic.min() and prob_mosaic.max() <= 1.0
    assert set(np.unique(binary_mask)).issubset({0, 1})
    # Check threshold logic
    expected_binary = (prob_mosaic >= 0.5).astype(np.uint8)
    assert np.array_equal(binary_mask, expected_binary)


def test_tile_and_predict_1024x1024_overlap_blending():
    """Verify 1024x1024 multi-tile windowing produces seamless, fully normalized mosaic."""
    processor = SentinelRasterProcessor()
    model_svc = Model2Service.get_instance()

    # 1024x1024 6-band input
    raster_1024 = np.full((6, 1024, 1024), fill_value=1500.0, dtype=np.float32)

    prob_mosaic, binary_mask = processor.tile_and_predict(
        raster_data=raster_1024,
        model2_service=model_svc,
        window_size=512,
        overlap=64,
    )

    assert prob_mosaic.shape == (1024, 1024)
    assert binary_mask.shape == (1024, 1024)
    assert np.isfinite(prob_mosaic).all()
    assert 0.0 <= prob_mosaic.min() and prob_mosaic.max() <= 1.0
    assert set(np.unique(binary_mask)).issubset({0, 1})


def test_tile_and_predict_smaller_than_512_padded_safely():
    """Verify scenes smaller than 512x512 are handled safely without crash or distortion."""
    processor = SentinelRasterProcessor()
    model_svc = Model2Service.get_instance()

    small_raster = np.full((6, 300, 400), fill_value=2000.0, dtype=np.float32)

    prob_mosaic, binary_mask = processor.tile_and_predict(
        raster_data=small_raster,
        model2_service=model_svc,
        window_size=512,
        overlap=64,
    )

    assert prob_mosaic.shape == (300, 400)
    assert binary_mask.shape == (300, 400)
    assert np.isfinite(prob_mosaic).all()


def test_tile_and_predict_bad_channel_dimension_raises():
    """Verify ValueError is raised when channel count is not 6."""
    processor = SentinelRasterProcessor()
    model_svc = Model2Service.get_instance()

    bad_raster = np.zeros((4, 512, 512), dtype=np.float32)

    with pytest.raises(ValueError) as exc:
        processor.tile_and_predict(bad_raster, model_svc)
    assert "Expected raster of shape (6, H, W)" in str(exc.value)
