"""Deterministic Early Warning and Advisory Decision Engine."""

from datetime import datetime, timedelta, timezone
import hashlib
import logging
from typing import Any, Dict, List, Optional

from backend.app.core.config import Settings, get_settings
from backend.app.schemas.common import Location
from backend.app.schemas.risk import RiskAssessment, RiskAssessmentResponse, RiskLevel
from backend.app.schemas.warning import (
    EvidenceFreshness,
    PhysicalTrigger,
    WarningAlert,
    WarningDecision,
    WarningDecisionResponse,
    WarningProvenance,
    WarningStatus,
    WarningUrgency,
)
from backend.app.services.base import BaseService

logger = logging.getLogger("rainfall_backend.services.warning")


class WarningService(BaseService):
    """
    Deterministic warning decision layer for SIH 2026 Problem Statement 26071.
    Translates multi-source risk assessment into structured, machine-readable
    warning states, operational urgencies, physical trigger reasons, freshness
    disclosures, and audit provenance.
    Explicitly non-official: strictly labeled prototype_only=True and
    official_warning_issued=False.
    """

    def __init__(self, settings: Optional[Settings] = None):
        super().__init__(
            name="WarningService",
            description="Deterministic flood warning decision engine and trigger evaluation",
        )
        self.settings = settings or get_settings()
        self._is_connected = False

    def check_connection(self) -> bool:
        """Service connection status (dedicated broadcast feed not active)."""
        return False

    def generate_warnings(
        self, location: Location, risk_assessment: RiskAssessment
    ) -> List[WarningAlert]:
        """
        Baseline interface for direct evacuation alert generation.
        Preserved to satisfy baseline test contracts.
        """
        raise NotImplementedError(
            "Warning generation engine is not yet connected. Fake alerts are strictly forbidden."
        )

    def evaluate_warning(
        self,
        risk_response: RiskAssessmentResponse,
    ) -> WarningDecisionResponse:
        """
        Evaluate deterministic warning decision from multi-source risk assessment:
        1. Evaluate concrete physical triggers against configured thresholds
        2. Execute deterministic state machine (NO_ALERT, MONITOR, PREPARE, ACTION, INSUFFICIENT_DATA)
        3. Identify any material discrepancies between physical bursts and composite score
        4. Compute defensible forward temporal validity based on active streams
        5. Disclose evidence freshness (current, stale, historical)
        6. Assemble full mathematical and model provenance
        """
        evidence_dict = risk_response.evidence or {}
        fusion_meta = risk_response.fusion
        available_sources = fusion_meta.available_sources

        # ------------------------------------------------------------
        # 1. Evaluate Physical / Evidence Triggers
        # ------------------------------------------------------------
        triggers: List[PhysicalTrigger] = []
        trigger_reasons: List[str] = []

        rf_ev = evidence_dict.get("rainfall_model")
        if rf_ev and rf_ev.get("available"):
            # Trigger 1a: Model 1 Heavy Rainfall Probability
            prob = float(rf_ev.get("heavy_rain_probability", 0.0))
            prob_thresh = float(self.settings.TRIGGER_RAINFALL_PROBABILITY)
            prob_trig = prob >= prob_thresh
            triggers.append(
                PhysicalTrigger(
                    source="heavy_rainfall_model",
                    metric="heavy_rain_probability",
                    observed_value=round(prob, 4),
                    threshold=prob_thresh,
                    triggered=prob_trig,
                    unit="probability",
                    timestamp=rf_ev.get("observation_date"),
                    description=(
                        f"Model 1 heavy rainfall probability ({prob:.4f}) vs threshold ({prob_thresh:.2f})."
                    ),
                )
            )
            if prob_trig:
                trigger_reasons.append(
                    f"Model 1 heavy-rainfall ML probability ({prob:.4f}) meets decision threshold ({prob_thresh:.2f})."
                )

            # Trigger 1b: Prior-Day Observed Rainfall
            precip = float(rf_ev.get("latest_precipitation_mm", 0.0))
            precip_thresh = float(self.settings.TRIGGER_RAINFALL_OBSERVED_MM)
            precip_trig = precip >= precip_thresh
            triggers.append(
                PhysicalTrigger(
                    source="heavy_rainfall_model",
                    metric="observed_precipitation_mm",
                    observed_value=round(precip, 2),
                    threshold=precip_thresh,
                    triggered=precip_trig,
                    unit="mm/day",
                    timestamp=rf_ev.get("observation_date"),
                    description=(
                        f"Observed rainfall on {rf_ev.get('observation_date')} ({precip:.1f} mm) vs threshold ({precip_thresh:.1f} mm)."
                    ),
                )
            )
            if precip_trig:
                trigger_reasons.append(
                    f"Prior-day observed precipitation reached {precip:.1f} mm (IMD heavy-rainfall threshold: {precip_thresh:.1f} mm)."
                )

        nwp_ev = evidence_dict.get("nwp")
        if nwp_ev and nwp_ev.get("available"):
            # Trigger 2a: NWP Peak Hourly Rainfall Rate
            rate = float(nwp_ev.get("max_hourly_precipitation_mm_hr", 0.0))
            rate_thresh = float(self.settings.TRIGGER_NWP_HOURLY_PRECIP_MM_HR)
            rate_trig = rate >= rate_thresh
            triggers.append(
                PhysicalTrigger(
                    source="nwp_forecast",
                    metric="max_hourly_precipitation_mm_hr",
                    observed_value=round(rate, 2),
                    threshold=rate_thresh,
                    triggered=rate_trig,
                    unit="mm/hr",
                    timestamp=nwp_ev.get("forecast_start_time"),
                    description=(
                        f"Peak NWP forecast rainfall intensity ({rate:.1f} mm/hr) vs threshold ({rate_thresh:.1f} mm/hr)."
                    ),
                )
            )
            if rate_trig:
                trigger_reasons.append(
                    f"NOAA GFS NWP forecasts peak rainfall rate of {rate:.1f} mm/hr (threshold: {rate_thresh:.1f} mm/hr)."
                )

            # Trigger 2b: NWP Accumulated Precipitation
            accum = float(nwp_ev.get("accumulated_precipitation_mm", 0.0))
            accum_thresh = float(self.settings.TRIGGER_NWP_ACCUMULATED_PRECIP_MM)
            accum_trig = accum >= accum_thresh
            triggers.append(
                PhysicalTrigger(
                    source="nwp_forecast",
                    metric="accumulated_precipitation_mm",
                    observed_value=round(accum, 2),
                    threshold=accum_thresh,
                    triggered=accum_trig,
                    unit="mm",
                    timestamp=nwp_ev.get("forecast_start_time"),
                    description=(
                        f"Accumulated NWP forecast rainfall ({accum:.1f} mm) vs threshold ({accum_thresh:.1f} mm)."
                    ),
                )
            )
            if accum_trig:
                trigger_reasons.append(
                    f"NOAA GFS NWP predicts accumulated rainfall of {accum:.1f} mm over forecast horizon."
                )

        radar_ev = evidence_dict.get("radar")
        if radar_ev and radar_ev.get("available"):
            # Trigger 3a: Doppler Radar Peak Reflectivity
            dbz = float(radar_ev.get("max_reflectivity_dbz", 0.0))
            dbz_thresh = float(self.settings.TRIGGER_RADAR_MAX_DBZ)
            dbz_trig = dbz >= dbz_thresh
            triggers.append(
                PhysicalTrigger(
                    source="radar_nowcast",
                    metric="max_reflectivity_dbz",
                    observed_value=round(dbz, 1),
                    threshold=dbz_thresh,
                    triggered=dbz_trig,
                    unit="dBZ",
                    timestamp=radar_ev.get("observation_timestamp"),
                    description=(
                        f"Peak Doppler radar reflectivity ({dbz:.1f} dBZ) vs convective threshold ({dbz_thresh:.1f} dBZ)."
                    ),
                )
            )
            if dbz_trig:
                trigger_reasons.append(
                    f"Doppler radar reflectivity reached {dbz:.1f} dBZ (severe convective threshold: {dbz_thresh:.1f} dBZ)."
                )

            # Trigger 3b: Radar Marshall-Palmer Rain Rate
            radar_rate = float(radar_ev.get("estimated_peak_rain_rate_mm_hr", 0.0))
            radar_rate_thresh = float(self.settings.TRIGGER_RADAR_RAIN_RATE_MM_HR)
            radar_rate_trig = radar_rate >= radar_rate_thresh
            triggers.append(
                PhysicalTrigger(
                    source="radar_nowcast",
                    metric="estimated_peak_rain_rate_mm_hr",
                    observed_value=round(radar_rate, 2),
                    threshold=radar_rate_thresh,
                    triggered=radar_rate_trig,
                    unit="mm/hr",
                    timestamp=radar_ev.get("observation_timestamp"),
                    description=(
                        f"Estimated radar rain rate ({radar_rate:.1f} mm/hr) vs threshold ({radar_rate_thresh:.1f} mm/hr)."
                    ),
                )
            )
            if radar_rate_trig:
                trigger_reasons.append(
                    f"Radar Marshall-Palmer nowcast indicates peak rain rate of {radar_rate:.1f} mm/hr."
                )

        sat_ev = evidence_dict.get("satellite_inundation")
        if sat_ev and sat_ev.get("available"):
            # Trigger 4a: Sentinel-2 Inundation Coverage Percentage
            pct = float(sat_ev.get("flooded_percentage", 0.0))
            pct_thresh = float(self.settings.TRIGGER_INUNDATION_FLOODED_PCT)
            pct_trig = pct >= pct_thresh
            triggers.append(
                PhysicalTrigger(
                    source="satellite_inundation",
                    metric="flooded_percentage",
                    observed_value=round(pct, 2),
                    threshold=pct_thresh,
                    triggered=pct_trig,
                    unit="%",
                    timestamp=sat_ev.get("scene_acquisition_datetime"),
                    description=(
                        f"Ground surface water coverage ({pct:.1f}%) vs threshold ({pct_thresh:.1f}%)."
                    ),
                )
            )
            if pct_trig:
                trigger_reasons.append(
                    f"Sentinel-2 inundation segmentation detected {pct:.1f}% surface water coverage ({sat_ev.get('flooded_area_sq_km', 0.0):.2f} km²)."
                )

            # Trigger 4b: Flooded Surface Area in km²
            area = float(sat_ev.get("flooded_area_sq_km", 0.0))
            area_thresh = float(self.settings.TRIGGER_INUNDATION_AREA_SQ_KM)
            area_trig = area >= area_thresh
            triggers.append(
                PhysicalTrigger(
                    source="satellite_inundation",
                    metric="flooded_area_sq_km",
                    observed_value=round(area, 2),
                    threshold=area_thresh,
                    triggered=area_trig,
                    unit="km²",
                    timestamp=sat_ev.get("scene_acquisition_datetime"),
                    description=(
                        f"Inundated area extent ({area:.2f} km²) vs threshold ({area_thresh:.1f} km²)."
                    ),
                )
            )
            if area_trig:
                trigger_reasons.append(
                    f"Satellite detected {area:.2f} km² inundated surface across {sat_ev.get('polygon_count', 0)} vector polygons."
                )

        if not trigger_reasons:
            trigger_reasons.append("Environmental variables within normal baseline operational limits.")

        # ------------------------------------------------------------
        # 2. Deterministic State Machine Mapping
        # ------------------------------------------------------------
        if fusion_meta.policy_applied == "INSUFFICIENT_EVIDENCE" or len(available_sources) < 2:
            status = WarningStatus.INSUFFICIENT_DATA
            urgency = WarningUrgency.NONE
            warning_triggered = False
            valid_until = None
            validity_reason = "Insufficient multi-source environmental data (<2 sources available) to evaluate warning status."
            escalation_notes = None
        else:
            comp_level = risk_response.risk.level
            if comp_level == RiskLevel.LOW:
                status = WarningStatus.NO_ALERT
                urgency = WarningUrgency.NONE
            elif comp_level == RiskLevel.MODERATE:
                status = WarningStatus.MONITOR
                urgency = WarningUrgency.MONITOR
            elif comp_level == RiskLevel.HIGH:
                status = WarningStatus.PREPARE
                urgency = WarningUrgency.PREPARE
            else:  # EXTREME
                status = WarningStatus.ACTION
                urgency = WarningUrgency.ACTION

            warning_triggered = (status != WarningStatus.NO_ALERT) or any(t.triggered for t in triggers)

            # Check for material discrepancy: strong physical burst with lower composite score
            escalation_notes = None
            has_severe_radar = any(
                t.source == "radar_nowcast"
                and t.triggered
                and (
                    (t.metric == "max_reflectivity_dbz" and t.observed_value >= 50.0)
                    or (t.metric == "estimated_peak_rain_rate_mm_hr" and t.observed_value >= 40.0)
                )
                for t in triggers
            )
            has_severe_nwp = any(
                t.source == "nwp_forecast"
                and t.triggered
                and t.metric == "max_hourly_precipitation_mm_hr"
                and t.observed_value >= 35.0
                for t in triggers
            )

            if (has_severe_radar or has_severe_nwp) and status in [WarningStatus.NO_ALERT, WarningStatus.MONITOR]:
                burst_type = "Doppler radar reflectivity (>= 50 dBZ)" if has_severe_radar else "NWP precipitation rate (>= 35 mm/hr)"
                escalation_notes = (
                    f"DISCREPANCY DISCLOSURE: Physical observation indicates intense burst ({burst_type}), "
                    f"while composite risk score ({risk_response.risk.score:.4f}) remains at {status.value} "
                    f"due to multi-source weight damping. Heightened situational vigilance recommended."
                )

            # ------------------------------------------------------------
            # 3. Temporal Validity Evaluation
            # ------------------------------------------------------------
            valid_until = None
            validity_reason = ""

            # Radar nowcast is primary validity governor if available
            if radar_ev and radar_ev.get("available") and radar_ev.get("observation_timestamp"):
                try:
                    ts_str = radar_ev["observation_timestamp"]
                    radar_dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                    val_dt = radar_dt + timedelta(hours=self.settings.WARNING_VALIDITY_RADAR_HOURS)
                    valid_until = val_dt.isoformat()
                    validity_reason = (
                        f"Governed by Doppler radar nowcast window ({self.settings.WARNING_VALIDITY_RADAR_HOURS:.0f}h validity "
                        f"from scan acquisition {radar_ev['observation_timestamp']})."
                    )
                except Exception:
                    valid_until = None

            # Next fallback: NWP forecast cycle
            if not valid_until and nwp_ev and nwp_ev.get("available"):
                try:
                    ts_str = nwp_ev.get("forecast_start_time") or risk_response.generated_at
                    nwp_dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                    val_dt = nwp_dt + timedelta(hours=self.settings.WARNING_VALIDITY_NWP_HOURS)
                    valid_until = val_dt.isoformat()
                    validity_reason = (
                        f"Governed by NOAA GFS synoptic NWP forecast cycle ({self.settings.WARNING_VALIDITY_NWP_HOURS:.0f}h window)."
                    )
                except Exception:
                    valid_until = None

            # Fallback if only historical satellite or undated data
            if not valid_until:
                valid_until = None
                validity_reason = (
                    "Assessment relies primarily on historical or undated observation streams; "
                    "forward temporal validity cannot be defensibly established."
                )

        # ------------------------------------------------------------
        # 4. Evidence Freshness & Staleness Disclosure
        # ------------------------------------------------------------
        current_sources: List[str] = []
        stale_sources: List[str] = []
        historical_sources: List[str] = []
        source_timestamps: Dict[str, Optional[str]] = {}

        for src in available_sources:
            if src == "heavy_rainfall_model" and rf_ev:
                ts = rf_ev.get("observation_date")
                source_timestamps["heavy_rainfall_model"] = ts
                current_sources.append("heavy_rainfall_model")
            elif src == "nwp_forecast" and nwp_ev:
                ts = nwp_ev.get("forecast_start_time")
                source_timestamps["nwp_forecast"] = ts
                current_sources.append("nwp_forecast")
            elif src == "radar_nowcast" and radar_ev:
                ts = radar_ev.get("observation_timestamp")
                source_timestamps["radar_nowcast"] = ts
                current_sources.append("radar_nowcast")
            elif src == "satellite_inundation" and sat_ev:
                ts = sat_ev.get("scene_acquisition_datetime")
                source_timestamps["satellite_inundation"] = ts
                temp_status = sat_ev.get("temporal_status", "HISTORICAL")
                if temp_status == "CURRENT":
                    current_sources.append("satellite_inundation")
                elif temp_status == "RECENT":
                    stale_sources.append("satellite_inundation")
                else:
                    historical_sources.append("satellite_inundation")

        satellite_is_hist = (
            sat_ev is not None
            and sat_ev.get("available", False)
            and sat_ev.get("temporal_status") == "HISTORICAL"
        )

        freshness = EvidenceFreshness(
            current_sources=current_sources,
            stale_sources=stale_sources,
            historical_sources=historical_sources,
            source_timestamps=source_timestamps,
            satellite_is_historical=satellite_is_hist,
        )

        # ------------------------------------------------------------
        # 5. Full Mathematical and Model Provenance
        # ------------------------------------------------------------
        det_hash = hashlib.sha256(
            f"{risk_response.requested_location.latitude:.4f}:{risk_response.requested_location.longitude:.4f}:{risk_response.risk.score:.4f}".encode()
        ).hexdigest()[:16]

        provenance = WarningProvenance(
            risk_assessment_id=f"risk_eval_{det_hash}",
            model_versions={
                "heavy_rainfall_model": "heavy_rainfall_xgboost_v2",
                "flood_inundation_model": "flood_unet_sentinel2_6band",
            },
            source_providers={
                "heavy_rainfall_model": "NASA POWER Daily Meteorology API",
                "nwp_forecast": "NOAA GFS 0.25° via Open-Meteo GFS Seamless",
                "radar_nowcast": "RainViewer Global Doppler Radar Composite Network",
                "satellite_inundation": "Sentinel-2 L2A via Element 84 Earth Search STAC",
            },
            source_timestamps=source_timestamps,
            configured_thresholds={
                "rainfall_probability": self.settings.TRIGGER_RAINFALL_PROBABILITY,
                "rainfall_observed_mm": self.settings.TRIGGER_RAINFALL_OBSERVED_MM,
                "nwp_max_hourly_mm_hr": self.settings.TRIGGER_NWP_HOURLY_PRECIP_MM_HR,
                "nwp_accumulated_mm": self.settings.TRIGGER_NWP_ACCUMULATED_PRECIP_MM,
                "radar_max_dbz": self.settings.TRIGGER_RADAR_MAX_DBZ,
                "radar_rain_rate_mm_hr": self.settings.TRIGGER_RADAR_RAIN_RATE_MM_HR,
                "inundation_flooded_percentage": self.settings.TRIGGER_INUNDATION_FLOODED_PCT,
                "inundation_flooded_area_sq_km": self.settings.TRIGGER_INUNDATION_AREA_SQ_KM,
            },
            configured_risk_weights=fusion_meta.effective_weights,
            rules_version=self.settings.WARNING_RULES_VERSION,
        )

        # ------------------------------------------------------------
        # 6. Assemble Warning Decision
        # ------------------------------------------------------------
        decision = WarningDecision(
            status=status,
            risk_level=risk_response.risk.level,
            urgency=urgency,
            triggered=warning_triggered,
            trigger_reasons=trigger_reasons,
            triggers=triggers,
            generated_at=risk_response.generated_at,
            valid_until=valid_until,
            validity_reason=validity_reason,
            prototype_only=True,
            official_warning_issued=False,
            disclaimer=(
                "EXPERIMENTAL PROTOTYPE ASSESSMENT FOR SIH 2026 PS 26071. "
                "NOT AN OFFICIAL IMD GOVERNMENT WARNING. NOT SANCTIONED FOR OFFICIAL EMERGENCY BROADCAST."
            ),
            escalation_notes=escalation_notes,
        )

        return WarningDecisionResponse(
            status="success",
            requested_location=risk_response.requested_location,
            location_name=risk_response.location_name,
            risk=risk_response.risk,
            warning=decision,
            evidence_freshness=freshness,
            source_provenance=provenance,
            supporting_evidence=evidence_dict,
        )
