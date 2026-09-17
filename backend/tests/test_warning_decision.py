"""Unit tests for deterministic Warning Decision Service and Trigger Evaluator."""

from datetime import datetime, timezone
import pytest

from backend.app.schemas.common import Coordinates
from backend.app.schemas.risk import (
    FusionMetadata,
    PrototypeWarningCandidate,
    RiskAssessmentResponse,
    RiskLevel,
    RiskScoreDetail,
    SourceExplanation,
)
from backend.app.schemas.warning import WarningStatus, WarningUrgency
from backend.app.services.warning_service import WarningService


@pytest.fixture
def warning_service():
    return WarningService()


@pytest.fixture
def base_risk_response():
    """Helper fixture providing representative baseline RiskAssessmentResponse."""
    return RiskAssessmentResponse(
        status="success",
        requested_location=Coordinates(latitude=19.0760, longitude=72.8777),
        location_name="Mumbai Test Point",
        risk=RiskScoreDetail(
            score=0.15,
            level=RiskLevel.LOW,
            thresholds={"low_max": 0.30, "moderate_max": 0.60, "high_max": 0.80},
        ),
        evidence={
            "rainfall_model": {
                "heavy_rain_probability": 0.12,
                "heavy_rain_predicted": False,
                "model_threshold": 0.81,
                "observation_date": "2026-09-15",
                "latest_precipitation_mm": 5.0,
                "historical_records_used": 30,
                "available": True,
            },
            "nwp": {
                "forecast_precipitation_mm_hr": 1.0,
                "max_hourly_precipitation_mm_hr": 3.5,
                "accumulated_precipitation_mm": 12.0,
                "max_cape_j_kg": 250.0,
                "forecast_horizon_hours": 24,
                "forecast_start_time": "2026-09-16T00:00:00Z",
                "forecast_end_time": "2026-09-17T00:00:00Z",
                "source_model": "GFS_0.25 via Open-Meteo",
                "available": True,
            },
            "radar": {
                "max_reflectivity_dbz": 22.0,
                "mean_reflectivity_dbz": 12.0,
                "active_echo_percentage": 4.5,
                "estimated_peak_rain_rate_mm_hr": 1.2,
                "observation_timestamp": "2026-09-16T10:00:00Z",
                "source": "RainViewer Global Doppler Radar Composite",
                "available": True,
            },
            "satellite_inundation": {
                "flooded_area_sq_km": 1.2,
                "valid_area_sq_km": 100.0,
                "flooded_percentage": 1.2,
                "polygon_count": 4,
                "scene_id": "S2A_TEST_SCENE",
                "scene_acquisition_datetime": "2026-09-16T04:30:00Z",
                "cloud_coverage_percentage": 5.0,
                "model_threshold": 0.5,
                "temporal_status": "CURRENT",
                "observation_age_hours": 6.0,
                "source": "Sentinel-2 L2A via Element 84 Earth Search",
                "available": True,
            },
        },
        fusion=FusionMetadata(
            policy_applied="FULL_EVIDENCE",
            original_weights={"heavy_rainfall_model": 0.35, "nwp_forecast": 0.25, "radar_nowcast": 0.20, "satellite_inundation": 0.20},
            effective_weights={"heavy_rainfall_model": 0.35, "nwp_forecast": 0.25, "radar_nowcast": 0.20, "satellite_inundation": 0.20},
            available_sources=["heavy_rainfall_model", "nwp_forecast", "radar_nowcast", "satellite_inundation"],
            unavailable_sources=[],
            freshness={},
        ),
        explanations=[],
        prototype_warning_assessment=PrototypeWarningCandidate(
            risk_level=RiskLevel.LOW,
            urgency="NONE",
            trigger_reasons=["Normal baseline conditions."],
            recommended_monitoring="Routine.",
        ),
        generated_at="2026-09-16T10:30:00Z",
    )


# ============================================================
# 1. STATE MACHINE MAPPINGS
# ============================================================


def test_warning_state_low_risk(warning_service, base_risk_response):
    resp = warning_service.evaluate_warning(base_risk_response)
    dec = resp.warning
    assert dec.status == WarningStatus.NO_ALERT
    assert dec.urgency == WarningUrgency.NONE
    assert dec.risk_level == RiskLevel.LOW
    assert dec.prototype_only is True
    assert dec.official_warning_issued is False


def test_warning_state_moderate_risk(warning_service, base_risk_response):
    mod_resp = base_risk_response.model_copy(deep=True)
    mod_resp.risk = RiskScoreDetail(
        score=0.45,
        level=RiskLevel.MODERATE,
        thresholds={"low_max": 0.30, "moderate_max": 0.60, "high_max": 0.80},
    )
    resp = warning_service.evaluate_warning(mod_resp)
    dec = resp.warning
    assert dec.status == WarningStatus.MONITOR
    assert dec.urgency == WarningUrgency.MONITOR
    assert dec.triggered is True


def test_warning_state_high_risk(warning_service, base_risk_response):
    high_resp = base_risk_response.model_copy(deep=True)
    high_resp.risk = RiskScoreDetail(
        score=0.72,
        level=RiskLevel.HIGH,
        thresholds={"low_max": 0.30, "moderate_max": 0.60, "high_max": 0.80},
    )
    resp = warning_service.evaluate_warning(high_resp)
    dec = resp.warning
    assert dec.status == WarningStatus.PREPARE
    assert dec.urgency == WarningUrgency.PREPARE
    assert dec.triggered is True


def test_warning_state_extreme_risk(warning_service, base_risk_response):
    ext_resp = base_risk_response.model_copy(deep=True)
    ext_resp.risk = RiskScoreDetail(
        score=0.89,
        level=RiskLevel.EXTREME,
        thresholds={"low_max": 0.30, "moderate_max": 0.60, "high_max": 0.80},
    )
    resp = warning_service.evaluate_warning(ext_resp)
    dec = resp.warning
    assert dec.status == WarningStatus.ACTION
    assert dec.urgency == WarningUrgency.ACTION
    assert dec.triggered is True


def test_warning_state_insufficient_data(warning_service, base_risk_response):
    insuf_resp = base_risk_response.model_copy(deep=True)
    insuf_resp.fusion.policy_applied = "INSUFFICIENT_EVIDENCE"
    insuf_resp.fusion.available_sources = ["radar_nowcast"]  # Only 1 source

    resp = warning_service.evaluate_warning(insuf_resp)
    dec = resp.warning
    assert dec.status == WarningStatus.INSUFFICIENT_DATA
    assert dec.urgency == WarningUrgency.NONE
    assert dec.triggered is False
    assert dec.valid_until is None
    assert "Insufficient multi-source environmental data" in dec.validity_reason


# ============================================================
# 2. PHYSICAL TRIGGER EVALUATION
# ============================================================


def test_physical_trigger_rainfall_prob(warning_service, base_risk_response):
    rf_resp = base_risk_response.model_copy(deep=True)
    rf_resp.evidence["rainfall_model"]["heavy_rain_probability"] = 0.92  # >= 0.81 threshold

    resp = warning_service.evaluate_warning(rf_resp)
    dec = resp.warning
    prob_trig = next(t for t in dec.triggers if t.metric == "heavy_rain_probability")
    assert prob_trig.triggered is True
    assert prob_trig.observed_value == 0.92
    assert prob_trig.threshold == 0.81
    assert any("probability (0.9200) meets decision threshold" in r for r in dec.trigger_reasons)


def test_physical_trigger_rainfall_observed(warning_service, base_risk_response):
    rf_resp = base_risk_response.model_copy(deep=True)
    rf_resp.evidence["rainfall_model"]["latest_precipitation_mm"] = 72.5  # >= 64.5 mm threshold

    resp = warning_service.evaluate_warning(rf_resp)
    dec = resp.warning
    precip_trig = next(t for t in dec.triggers if t.metric == "observed_precipitation_mm")
    assert precip_trig.triggered is True
    assert precip_trig.observed_value == 72.5
    assert any("72.5 mm" in r for r in dec.trigger_reasons)


def test_physical_trigger_nwp_rate_and_accum(warning_service, base_risk_response):
    nwp_resp = base_risk_response.model_copy(deep=True)
    nwp_resp.evidence["nwp"]["max_hourly_precipitation_mm_hr"] = 28.5  # >= 20.0
    nwp_resp.evidence["nwp"]["accumulated_precipitation_mm"] = 85.0    # >= 70.0

    resp = warning_service.evaluate_warning(nwp_resp)
    dec = resp.warning
    rate_trig = next(t for t in dec.triggers if t.metric == "max_hourly_precipitation_mm_hr")
    accum_trig = next(t for t in dec.triggers if t.metric == "accumulated_precipitation_mm")
    assert rate_trig.triggered is True
    assert accum_trig.triggered is True
    assert any("28.5 mm/hr" in r for r in dec.trigger_reasons)
    assert any("85.0 mm" in r for r in dec.trigger_reasons)


def test_physical_trigger_radar_dbz_and_rain_rate(warning_service, base_risk_response):
    rad_resp = base_risk_response.model_copy(deep=True)
    rad_resp.evidence["radar"]["max_reflectivity_dbz"] = 48.8            # >= 45.0 dBZ
    rad_resp.evidence["radar"]["estimated_peak_rain_rate_mm_hr"] = 38.5  # >= 30.0 mm/hr

    resp = warning_service.evaluate_warning(rad_resp)
    dec = resp.warning
    dbz_trig = next(t for t in dec.triggers if t.metric == "max_reflectivity_dbz")
    rate_trig = next(t for t in dec.triggers if t.metric == "estimated_peak_rain_rate_mm_hr")
    assert dbz_trig.triggered is True
    assert rate_trig.triggered is True
    assert any("48.8 dBZ" in r for r in dec.trigger_reasons)


def test_physical_trigger_satellite_inundation(warning_service, base_risk_response):
    sat_resp = base_risk_response.model_copy(deep=True)
    sat_resp.evidence["satellite_inundation"]["flooded_percentage"] = 15.5  # >= 10.0%
    sat_resp.evidence["satellite_inundation"]["flooded_area_sq_km"] = 8.2   # >= 5.0 km²

    resp = warning_service.evaluate_warning(sat_resp)
    dec = resp.warning
    pct_trig = next(t for t in dec.triggers if t.metric == "flooded_percentage")
    area_trig = next(t for t in dec.triggers if t.metric == "flooded_area_sq_km")
    assert pct_trig.triggered is True
    assert area_trig.triggered is True
    assert any("15.5%" in r for r in dec.trigger_reasons)


# ============================================================
# 3. DISCREPANCY & ESCALATION NOTES
# ============================================================


def test_physical_burst_discrepancy_escalation(warning_service, base_risk_response):
    # Radar indicates intense convective core (54 dBZ >= 50 dBZ burst threshold),
    # but overall composite score is LOW (0.25) due to other calm streams
    burst_resp = base_risk_response.model_copy(deep=True)
    burst_resp.risk = RiskScoreDetail(
        score=0.25,
        level=RiskLevel.LOW,
        thresholds={"low_max": 0.30, "moderate_max": 0.60, "high_max": 0.80},
    )
    burst_resp.evidence["radar"]["max_reflectivity_dbz"] = 54.0

    resp = warning_service.evaluate_warning(burst_resp)
    dec = resp.warning
    # Status stays NO_ALERT per composite score rule
    assert dec.status == WarningStatus.NO_ALERT
    # Discrepancy is explicitly disclosed in escalation_notes
    assert dec.escalation_notes is not None
    assert "DISCREPANCY DISCLOSURE" in dec.escalation_notes
    assert "Doppler radar reflectivity" in dec.escalation_notes


# ============================================================
# 4. TEMPORAL VALIDITY & FRESHNESS
# ============================================================


def test_temporal_validity_radar_governed(warning_service, base_risk_response):
    # Active radar observation timestamp: 2026-09-16T10:00:00Z
    resp = warning_service.evaluate_warning(base_risk_response)
    dec = resp.warning
    assert dec.valid_until is not None
    # 3 hours forward from 10:00 -> 13:00
    assert "2026-09-16T13:00:00" in dec.valid_until
    assert "Doppler radar nowcast window (3h validity" in dec.validity_reason


def test_temporal_validity_nwp_fallback(warning_service, base_risk_response):
    # Radar unavailable -> falls back to NWP forecast cycle (12h window)
    no_radar = base_risk_response.model_copy(deep=True)
    no_radar.evidence["radar"]["available"] = False
    no_radar.fusion.available_sources = ["heavy_rainfall_model", "nwp_forecast", "satellite_inundation"]

    resp = warning_service.evaluate_warning(no_radar)
    dec = resp.warning
    assert dec.valid_until is not None
    # 12 hours forward from 00:00 -> 12:00
    assert "2026-09-16T12:00:00" in dec.valid_until
    assert "NOAA GFS synoptic NWP forecast cycle (12h window)" in dec.validity_reason


def test_temporal_validity_historical_satellite_indefensible(warning_service, base_risk_response):
    # Radar and NWP unavailable -> only Model 1 observation and historical satellite
    hist_resp = base_risk_response.model_copy(deep=True)
    hist_resp.evidence["radar"]["available"] = False
    hist_resp.evidence["nwp"]["available"] = False
    hist_resp.evidence["satellite_inundation"]["temporal_status"] = "HISTORICAL"
    hist_resp.fusion.available_sources = ["heavy_rainfall_model", "satellite_inundation"]

    resp = warning_service.evaluate_warning(hist_resp)
    dec = resp.warning
    assert dec.valid_until is None
    assert "forward temporal validity cannot be defensibly established" in dec.validity_reason
    assert resp.evidence_freshness.satellite_is_historical is True
    assert "satellite_inundation" in resp.evidence_freshness.historical_sources


# ============================================================
# 5. DETERMINISM & PROVENANCE
# ============================================================


def test_warning_decision_deterministic_and_idempotent(warning_service, base_risk_response):
    # Evaluate twice with identical input
    resp1 = warning_service.evaluate_warning(base_risk_response)
    resp2 = warning_service.evaluate_warning(base_risk_response)

    assert resp1.warning.status == resp2.warning.status
    assert resp1.warning.risk_level == resp2.warning.risk_level
    assert resp1.warning.urgency == resp2.warning.urgency
    assert resp1.warning.triggered == resp2.warning.triggered
    assert resp1.warning.trigger_reasons == resp2.warning.trigger_reasons
    assert resp1.warning.valid_until == resp2.warning.valid_until
    assert resp1.warning.validity_reason == resp2.warning.validity_reason
    assert resp1.source_provenance.risk_assessment_id == resp2.source_provenance.risk_assessment_id
    assert resp1.source_provenance.model_versions == resp2.source_provenance.model_versions
