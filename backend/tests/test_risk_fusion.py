"""Unit tests for Multi-Source Risk Fusion Service and Explainability Engine."""

import pytest

from backend.app.core.config import Settings
from backend.app.core.errors import InsufficientHistoricalDataError
from backend.app.schemas.common import Coordinates
from backend.app.schemas.risk import (
    NwpEvidence,
    RadarEvidence,
    RainfallEvidence,
    RiskLevel,
    SatelliteInundationEvidence,
)
from backend.app.services.risk_fusion_service import RiskFusionService


@pytest.fixture
def fusion_service():
    return RiskFusionService()


@pytest.fixture
def mock_coords():
    return Coordinates(latitude=19.0760, longitude=72.8777)


@pytest.fixture
def rainfall_evidence_low():
    return RainfallEvidence(
        heavy_rain_probability=0.15,
        heavy_rain_predicted=False,
        model_threshold=0.81,
        observation_date="2026-09-15",
        latest_precipitation_mm=5.0,
        historical_records_used=30,
        available=True,
    )


@pytest.fixture
def rainfall_evidence_high():
    return RainfallEvidence(
        heavy_rain_probability=0.92,
        heavy_rain_predicted=True,
        model_threshold=0.81,
        observation_date="2026-09-15",
        latest_precipitation_mm=75.0,
        historical_records_used=30,
        available=True,
    )


@pytest.fixture
def nwp_evidence_low():
    return NwpEvidence(
        forecast_precipitation_mm_hr=1.2,
        max_hourly_precipitation_mm_hr=4.5,
        accumulated_precipitation_mm=15.0,
        max_cape_j_kg=250.0,
        forecast_horizon_hours=24,
        forecast_start_time="2026-09-16T00:00:00Z",
        forecast_end_time="2026-09-17T00:00:00Z",
        available=True,
    )


@pytest.fixture
def nwp_evidence_severe():
    return NwpEvidence(
        forecast_precipitation_mm_hr=18.0,
        max_hourly_precipitation_mm_hr=42.0,  # exceeds 35 mm/hr cap
        accumulated_precipitation_mm=120.0,  # exceeds 100 mm cap
        max_cape_j_kg=1800.0,  # CAPE multiplier
        forecast_horizon_hours=24,
        forecast_start_time="2026-09-16T00:00:00Z",
        forecast_end_time="2026-09-17T00:00:00Z",
        available=True,
    )


@pytest.fixture
def radar_evidence_low():
    return RadarEvidence(
        max_reflectivity_dbz=18.0,
        mean_reflectivity_dbz=12.0,
        active_echo_percentage=5.0,
        estimated_peak_rain_rate_mm_hr=0.8,
        observation_timestamp="2026-09-16T10:00:00Z",
        available=True,
    )


@pytest.fixture
def radar_evidence_severe():
    return RadarEvidence(
        max_reflectivity_dbz=58.0,  # intense convective core (>55 dBZ cap)
        mean_reflectivity_dbz=38.0,
        active_echo_percentage=65.0,
        estimated_peak_rain_rate_mm_hr=62.0,  # exceeds 50 mm/hr cap
        observation_timestamp="2026-09-16T10:00:00Z",
        available=True,
    )


@pytest.fixture
def satellite_evidence_current():
    return SatelliteInundationEvidence(
        flooded_area_sq_km=8.5,
        valid_area_sq_km=100.0,
        flooded_percentage=8.5,
        polygon_count=14,
        scene_id="S2A_TEST_SCENE",
        scene_acquisition_datetime="2026-09-16T04:30:00Z",
        cloud_coverage_percentage=5.0,
        model_threshold=0.5,
        temporal_status="CURRENT",
        observation_age_hours=6.0,
        available=True,
    )


# ============================================================
# 1. INDIVIDUAL NORMALIZATION TESTS
# ============================================================


def test_normalize_rainfall_evidence(fusion_service, rainfall_evidence_low, rainfall_evidence_high):
    # Available evidence
    assert fusion_service.normalize_rainfall_evidence(rainfall_evidence_low) == 0.15
    assert fusion_service.normalize_rainfall_evidence(rainfall_evidence_high) == 0.92

    # Unavailable evidence
    unavail = rainfall_evidence_low.model_copy(update={"available": False})
    assert fusion_service.normalize_rainfall_evidence(unavail) == 0.0


def test_normalize_nwp_evidence(fusion_service, nwp_evidence_low, nwp_evidence_severe):
    score_low = fusion_service.normalize_nwp_evidence(nwp_evidence_low)
    assert 0.0 < score_low < 0.20

    score_severe = fusion_service.normalize_nwp_evidence(nwp_evidence_severe)
    assert score_severe == 1.0  # Capped at 1.0 even with CAPE multiplier

    unavail = nwp_evidence_low.model_copy(update={"available": False})
    assert fusion_service.normalize_nwp_evidence(unavail) == 0.0


def test_normalize_radar_evidence(fusion_service, radar_evidence_low, radar_evidence_severe):
    # Under 20 dBZ should produce minimal or zero score
    score_low = fusion_service.normalize_radar_evidence(radar_evidence_low)
    assert score_low < 0.05

    score_severe = fusion_service.normalize_radar_evidence(radar_evidence_severe)
    assert score_severe == 1.0  # High reflectivity + rain rate caps at 1.0

    unavail = radar_evidence_low.model_copy(update={"available": False})
    assert fusion_service.normalize_radar_evidence(unavail) == 0.0


def test_normalize_inundation_temporal_discounting(fusion_service, satellite_evidence_current):
    # Current (<48h) uses 1.0 multiplier
    score_current = fusion_service.normalize_inundation_evidence(satellite_evidence_current)
    assert score_current > 0.0

    # Recent (48-168h) uses 0.75 multiplier
    recent_ev = satellite_evidence_current.model_copy(update={"temporal_status": "RECENT"})
    score_recent = fusion_service.normalize_inundation_evidence(recent_ev)
    assert pytest.approx(score_recent, abs=1e-4) == score_current * 0.75

    # Historical (>168h) uses 0.50 multiplier
    hist_ev = satellite_evidence_current.model_copy(update={"temporal_status": "HISTORICAL"})
    score_hist = fusion_service.normalize_inundation_evidence(hist_ev)
    assert pytest.approx(score_hist, abs=1e-4) == score_current * 0.50


# ============================================================
# 2. MISSING-SOURCE POLICY & WEIGHT RENORMALIZATION TESTS
# ============================================================


def test_fuse_evidence_all_four_sources(
    fusion_service,
    mock_coords,
    rainfall_evidence_low,
    nwp_evidence_low,
    radar_evidence_low,
    satellite_evidence_current,
):
    response = fusion_service.fuse_evidence(
        location=mock_coords,
        rainfall_evidence=rainfall_evidence_low,
        nwp_evidence=nwp_evidence_low,
        radar_evidence=radar_evidence_low,
        satellite_evidence=satellite_evidence_current,
        location_name="Mumbai Test Site",
    )

    assert response.status == "success"
    assert response.fusion.policy_applied == "FULL_EVIDENCE"
    assert len(response.fusion.available_sources) == 4
    assert len(response.fusion.unavailable_sources) == 0

    # Configured static weights match effective weights
    assert response.fusion.effective_weights["heavy_rainfall_model"] == 0.35
    assert response.fusion.effective_weights["nwp_forecast"] == 0.25
    assert response.fusion.effective_weights["radar_nowcast"] == 0.20
    assert response.fusion.effective_weights["satellite_inundation"] == 0.20

    # Weights sum to 1.0
    assert pytest.approx(sum(response.fusion.effective_weights.values()), abs=1e-4) == 1.0
    assert response.risk.level in [RiskLevel.LOW, RiskLevel.MODERATE]


def test_fuse_evidence_three_sources_renormalization(
    fusion_service,
    mock_coords,
    rainfall_evidence_low,
    nwp_evidence_low,
    radar_evidence_low,
):
    # Satellite inundation is missing
    response = fusion_service.fuse_evidence(
        location=mock_coords,
        rainfall_evidence=rainfall_evidence_low,
        nwp_evidence=nwp_evidence_low,
        radar_evidence=radar_evidence_low,
        satellite_evidence=None,
    )

    assert response.fusion.policy_applied == "PARTIAL_EVIDENCE"
    assert "satellite_inundation" in response.fusion.unavailable_sources
    assert len(response.fusion.available_sources) == 3

    eff = response.fusion.effective_weights
    assert eff["satellite_inundation"] == 0.0
    assert pytest.approx(sum(eff.values()), abs=1e-4) == 1.0
    # Original ratio of rainfall:nwp:radar was 0.35:0.25:0.20 -> total 0.80
    # Renormalized: 0.35/0.8 = 0.4375, 0.25/0.8 = 0.3125, 0.20/0.8 = 0.25
    assert eff["heavy_rainfall_model"] > 0.35
    assert eff["nwp_forecast"] > 0.25
    assert eff["radar_nowcast"] > 0.20


def test_fuse_evidence_two_sources_renormalization(
    fusion_service,
    mock_coords,
    rainfall_evidence_high,
    nwp_evidence_severe,
):
    # Only rainfall and NWP available
    response = fusion_service.fuse_evidence(
        location=mock_coords,
        rainfall_evidence=rainfall_evidence_high,
        nwp_evidence=nwp_evidence_severe,
        radar_evidence=None,
        satellite_evidence=None,
    )

    assert response.fusion.policy_applied == "PARTIAL_EVIDENCE"
    assert len(response.fusion.available_sources) == 2
    assert "radar_nowcast" in response.fusion.unavailable_sources
    assert "satellite_inundation" in response.fusion.unavailable_sources

    eff = response.fusion.effective_weights
    assert eff["radar_nowcast"] == 0.0
    assert eff["satellite_inundation"] == 0.0
    assert pytest.approx(sum(eff.values()), abs=1e-4) == 1.0
    # Original ratio: 0.35 : 0.25 (total 0.60)
    # Renormalized: 0.35 / 0.60 ≈ 0.5833, 0.25 / 0.60 ≈ 0.4167
    assert eff["heavy_rainfall_model"] > 0.55
    assert eff["nwp_forecast"] > 0.40


def test_fuse_evidence_insufficient_sources_raises_422(
    fusion_service,
    mock_coords,
    rainfall_evidence_low,
):
    # Only 1 source available -> strictly forbidden
    with pytest.raises(InsufficientHistoricalDataError) as exc_info:
        fusion_service.fuse_evidence(
            location=mock_coords,
            rainfall_evidence=rainfall_evidence_low,
            nwp_evidence=None,
            radar_evidence=None,
            satellite_evidence=None,
        )
    assert "Insufficient multi-source evidence" in str(exc_info.value)
    assert exc_info.value.status_code == 422


# ============================================================
# 3. EXPLAINABILITY DECOMPOSITION & MATHEMATICAL INTEGRITY
# ============================================================


def test_mathematical_explainability_sum(
    fusion_service,
    mock_coords,
    rainfall_evidence_high,
    nwp_evidence_severe,
    radar_evidence_severe,
    satellite_evidence_current,
):
    response = fusion_service.fuse_evidence(
        location=mock_coords,
        rainfall_evidence=rainfall_evidence_high,
        nwp_evidence=nwp_evidence_severe,
        radar_evidence=radar_evidence_severe,
        satellite_evidence=satellite_evidence_current,
    )

    # Verify each explanation's contribution = effective_weight * normalized_score
    total_contribution = 0.0
    for exp in response.explanations:
        expected_contrib = round(exp.effective_weight * exp.normalized_score, 4)
        assert pytest.approx(exp.contribution, abs=1e-3) == expected_contrib
        total_contribution += exp.contribution

    # Sum of contributions matches composite risk score
    assert pytest.approx(response.risk.score, abs=1e-3) == total_contribution
    assert response.risk.score > 0.80
    assert response.risk.level == RiskLevel.EXTREME


# ============================================================
# 4. PROTOTYPE WARNING CANDIDATE AND DISCLAIMERS
# ============================================================


def test_prototype_warning_candidate_triggers_and_disclaimer(
    fusion_service,
    mock_coords,
    rainfall_evidence_high,
    nwp_evidence_severe,
    radar_evidence_severe,
    satellite_evidence_current,
):
    response = fusion_service.fuse_evidence(
        location=mock_coords,
        rainfall_evidence=rainfall_evidence_high,
        nwp_evidence=nwp_evidence_severe,
        radar_evidence=radar_evidence_severe,
        satellite_evidence=satellite_evidence_current,
    )

    candidate = response.prototype_warning_assessment
    assert candidate.risk_level == RiskLevel.EXTREME
    assert candidate.urgency in ["ACTION", "PREPARE"]
    assert len(candidate.trigger_reasons) >= 2
    assert "NOT AN OFFICIAL IMD GOVERNMENT WEATHER WARNING" in candidate.disclaimer
