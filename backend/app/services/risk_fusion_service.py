"""Spatial Multi-Source Risk Fusion Engine and Explainability Service."""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional, Tuple

from backend.app.core.config import get_settings
from backend.app.core.errors import InsufficientHistoricalDataError
from backend.app.schemas.common import Coordinates, Location
from backend.app.schemas.prediction import InundationPrediction, RainfallPrediction
from backend.app.schemas.risk import (
    FusionMetadata,
    NwpEvidence,
    PrototypeWarningCandidate,
    RadarEvidence,
    RainfallEvidence,
    RiskAssessment,
    RiskAssessmentResponse,
    RiskLevel,
    RiskScoreDetail,
    SatelliteInundationEvidence,
    SourceExplanation,
)
from backend.app.services.base import BaseService

logger = logging.getLogger("rainfall_backend.services.risk_fusion")


class RiskFusionService(BaseService):
    """
    Multi-source environmental risk fusion engine.
    Fuses Model 1 (heavy rainfall XGBoost), Open-Meteo NOAA GFS NWP forecast,
    RainViewer Doppler radar nowcasts, and Sentinel-2 / Model 2 inundation evidence.
    Enforces deterministic normalized scoring, dynamic missing-source weight
    renormalization, temporal freshness labeling, and mathematical explainability.
    """

    def __init__(self):
        super().__init__(
            name="RiskFusionService",
            description="Multi-source environmental risk fusion and explainable assessment",
        )
        self._is_connected = False
        self.settings = get_settings()

    def check_connection(self) -> bool:
        """Baseline service connection check."""
        return False

    def assess_risk(
        self,
        location: Location,
        rainfall_prediction: RainfallPrediction,
        inundation_prediction: InundationPrediction,
    ) -> RiskAssessment:
        """Legacy baseline interface. Preserved to satisfy baseline test contracts."""
        raise NotImplementedError(
            "Risk fusion engine is not yet connected. Fake risk scores are strictly forbidden."
        )

    # ============================================================
    # NORMALIZATION FUNCTIONS (0.0 to 1.0)
    # ============================================================

    def normalize_rainfall_evidence(self, evidence: RainfallEvidence) -> float:
        """
        Normalize Model 1 XGBoost heavy rainfall probability to [0.0, 1.0].
        Physical basis: calibrated binary probability of next-day heavy rainfall (>64.5 mm).
        """
        if not evidence.available:
            return 0.0
        prob = float(evidence.heavy_rain_probability)
        if not (prob == prob and prob != float("inf") and prob != float("-inf")):
            return 0.0
        return max(0.0, min(1.0, prob))

    def normalize_nwp_evidence(self, evidence: NwpEvidence) -> float:
        """
        Normalize NOAA GFS numerical weather forecast to [0.0, 1.0].
        Physical basis: IMD rainfall intensity classifications:
        - Peak hourly rate: 35.0 mm/hr represents very heavy convective downpour.
        - Accumulated 24h precipitation: 100.0 mm represents regional flash flood potential.
        - CAPE convective instability: values > 1000 J/kg scale convective risk up to 15%.
        """
        if not evidence.available:
            return 0.0

        peak_rate = max(0.0, float(evidence.max_hourly_precipitation_mm_hr))
        accum_rain = max(0.0, float(evidence.accumulated_precipitation_mm))

        peak_score = min(1.0, peak_rate / 35.0)
        accum_score = min(1.0, accum_rain / 100.0)

        # 70% peak intensity weight + 30% volume accumulation weight
        base_score = 0.7 * peak_score + 0.3 * accum_score

        # CAPE multiplier for convective severe storm instability
        cape_factor = 1.0
        if evidence.max_cape_j_kg and evidence.max_cape_j_kg > 1000.0:
            excess = min(2000.0, evidence.max_cape_j_kg - 1000.0)
            cape_factor = 1.0 + 0.15 * (excess / 2000.0)

        return max(0.0, min(1.0, base_score * cape_factor))

    def normalize_radar_evidence(self, evidence: RadarEvidence) -> float:
        """
        Normalize Doppler Weather Radar composite reflectivity to [0.0, 1.0].
        Physical basis:
        - Reflectivity below 20 dBZ indicates clear air / non-precipitating clouds (0.0).
        - 20 to 55 dBZ spans light showers to severe thunderstorm cores.
        - Above 55 dBZ indicates extreme convective core / hail (1.0).
        - Marshall-Palmer estimated peak rainfall rate scaled against 50.0 mm/hr.
        """
        if not evidence.available:
            return 0.0

        max_dbz = max(0.0, float(evidence.max_reflectivity_dbz))
        peak_rate = max(0.0, float(evidence.estimated_peak_rain_rate_mm_hr))

        if max_dbz < 20.0:
            dbz_score = 0.0
        else:
            dbz_score = min(1.0, (max_dbz - 20.0) / 35.0)

        rate_score = min(1.0, peak_rate / 50.0)

        # 60% reflectivity + 40% rain rate
        return max(0.0, min(1.0, 0.6 * dbz_score + 0.4 * rate_score))

    def normalize_inundation_evidence(self, evidence: SatelliteInundationEvidence) -> float:
        """
        Normalize Sentinel-2 / Model 2 inundation evidence to [0.0, 1.0].
        Physical basis:
        - Flooded percentage: 30.0% of analyzed valid area inundated represents catastrophic flooding (1.0).
        - Temporal staleness discount:
          * CURRENT (<48h): 1.0 factor (active flooding).
          * RECENT (48-168h): 0.75 factor (recent antecedent saturation / ponding).
          * HISTORICAL (>168h): 0.50 factor (geomorphic terrain depression / baseline water bodies).
        """
        if not evidence.available:
            return 0.0

        flood_pct = max(0.0, float(evidence.flooded_percentage))
        raw_score = min(1.0, flood_pct / 30.0)

        # Staleness factor
        status = (evidence.temporal_status or "CURRENT").upper()
        if status == "CURRENT":
            factor = 1.0
        elif status == "RECENT":
            factor = 0.75
        else:  # HISTORICAL
            factor = 0.50

        return max(0.0, min(1.0, raw_score * factor))

    # ============================================================
    # MULTI-SOURCE FUSION & POLICY APPLICATION
    # ============================================================

    def fuse_evidence(
        self,
        location: Coordinates,
        rainfall_evidence: Optional[RainfallEvidence] = None,
        nwp_evidence: Optional[NwpEvidence] = None,
        radar_evidence: Optional[RadarEvidence] = None,
        satellite_evidence: Optional[SatelliteInundationEvidence] = None,
        location_name: Optional[str] = None,
    ) -> RiskAssessmentResponse:
        """
        Execute deterministic multi-source risk fusion:
        1. Evaluate availability of 4 evidence streams.
        2. Apply Missing-Source Policy (renormalize weights or raise if <2 sources).
        3. Compute normalized scores and effective contributions.
        4. Categorize composite risk level against configured boundaries.
        5. Generate mathematical explainability objects.
        6. Derive prototype warning candidate with triggers and urgency.
        """
        # Baseline static weights from configuration
        original_weights: Dict[str, float] = {
            "heavy_rainfall_model": self.settings.RISK_WEIGHT_RAINFALL,
            "nwp_forecast": self.settings.RISK_WEIGHT_NWP,
            "radar_nowcast": self.settings.RISK_WEIGHT_RADAR,
            "satellite_inundation": self.settings.RISK_WEIGHT_INUNDATION,
        }

        # Track stream availability
        streams: Dict[str, Tuple[bool, Any, float]] = {
            "heavy_rainfall_model": (
                rainfall_evidence is not None and rainfall_evidence.available,
                rainfall_evidence,
                self.normalize_rainfall_evidence(rainfall_evidence) if rainfall_evidence else 0.0,
            ),
            "nwp_forecast": (
                nwp_evidence is not None and nwp_evidence.available,
                nwp_evidence,
                self.normalize_nwp_evidence(nwp_evidence) if nwp_evidence else 0.0,
            ),
            "radar_nowcast": (
                radar_evidence is not None and radar_evidence.available,
                radar_evidence,
                self.normalize_radar_evidence(radar_evidence) if radar_evidence else 0.0,
            ),
            "satellite_inundation": (
                satellite_evidence is not None and satellite_evidence.available,
                satellite_evidence,
                self.normalize_inundation_evidence(satellite_evidence) if satellite_evidence else 0.0,
            ),
        }

        available_sources = [k for k, (avail, _, _) in streams.items() if avail]
        unavailable_sources = [k for k, (avail, _, _) in streams.items() if not avail]

        # Missing-Source Policy enforcement
        if len(available_sources) < 2:
            raise InsufficientHistoricalDataError(
                message=(
                    f"Insufficient multi-source evidence: only {len(available_sources)}/4 sources "
                    f"available ({available_sources}). Minimum 2 required for risk fusion."
                ),
                required_days=2,
                available_days=len(available_sources),
                details={
                    "available_sources": available_sources,
                    "unavailable_sources": unavailable_sources,
                },
            )
        elif len(available_sources) == 4:
            policy_applied = "FULL_EVIDENCE"
            effective_weights = dict(original_weights)
        else:
            policy_applied = "PARTIAL_EVIDENCE"
            total_avail_weight = sum(original_weights[k] for k in available_sources)
            effective_weights = {
                k: round(original_weights[k] / total_avail_weight, 4) if k in available_sources else 0.0
                for k in original_weights
            }
            # Normalize rounding drift so sum is exactly 1.0
            diff = 1.0 - sum(effective_weights[k] for k in available_sources)
            first_avail = available_sources[0]
            effective_weights[first_avail] = round(effective_weights[first_avail] + diff, 4)

        # Compute composite risk score
        composite_score = 0.0
        explanations: List[SourceExplanation] = []
        trigger_reasons: List[str] = []

        # 1. Model 1 Explanation
        is_avail, obj, norm_s = streams["heavy_rainfall_model"]
        w_eff = effective_weights["heavy_rainfall_model"]
        contrib = round(w_eff * norm_s, 4)
        composite_score += contrib
        ts_rf = rainfall_evidence.observation_date if rainfall_evidence else None
        explanations.append(
            SourceExplanation(
                source="heavy_rainfall_model",
                name="Model 1 (Next-Day Heavy Rainfall XGBoost)",
                description=(
                    f"Predicted heavy rainfall probability: {rainfall_evidence.heavy_rain_probability:.4f} "
                    f"(decision threshold: {rainfall_evidence.model_threshold})."
                    if rainfall_evidence and is_avail
                    else "Observational weather / Model 1 prediction unavailable."
                ),
                raw_value=rainfall_evidence.heavy_rain_probability if rainfall_evidence and is_avail else None,
                normalized_score=round(norm_s, 4),
                original_weight=original_weights["heavy_rainfall_model"],
                effective_weight=w_eff,
                contribution=contrib,
                timestamp=ts_rf,
                status="available" if is_avail else "unavailable",
            )
        )
        if rainfall_evidence and is_avail and rainfall_evidence.heavy_rain_predicted:
            trigger_reasons.append(
                f"Model 1 heavy rainfall probability ({rainfall_evidence.heavy_rain_probability:.2%}) "
                f"exceeds decision threshold ({rainfall_evidence.model_threshold})."
            )

        # 2. NWP Explanation
        is_avail, obj, norm_s = streams["nwp_forecast"]
        w_eff = effective_weights["nwp_forecast"]
        contrib = round(w_eff * norm_s, 4)
        composite_score += contrib
        ts_nwp = nwp_evidence.forecast_start_time if nwp_evidence else None
        explanations.append(
            SourceExplanation(
                source="nwp_forecast",
                name="NOAA GFS Numerical Weather Prediction",
                description=(
                    f"Peak forecast intensity: {nwp_evidence.max_hourly_precipitation_mm_hr:.1f} mm/hr, "
                    f"24h accumulated rain: {nwp_evidence.accumulated_precipitation_mm:.1f} mm."
                    if nwp_evidence and is_avail
                    else "NOAA GFS forecast stream unavailable."
                ),
                raw_value={
                    "max_hourly_mm_hr": nwp_evidence.max_hourly_precipitation_mm_hr,
                    "accumulated_mm": nwp_evidence.accumulated_precipitation_mm,
                    "max_cape_j_kg": nwp_evidence.max_cape_j_kg,
                }
                if nwp_evidence and is_avail
                else None,
                normalized_score=round(norm_s, 4),
                original_weight=original_weights["nwp_forecast"],
                effective_weight=w_eff,
                contribution=contrib,
                timestamp=ts_nwp,
                status="available" if is_avail else "unavailable",
            )
        )
        if nwp_evidence and is_avail and nwp_evidence.max_hourly_precipitation_mm_hr >= 15.6:
            trigger_reasons.append(
                f"NOAA GFS NWP predicts intense precipitation ({nwp_evidence.max_hourly_precipitation_mm_hr:.1f} mm/hr)."
            )

        # 3. Radar Explanation
        is_avail, obj, norm_s = streams["radar_nowcast"]
        w_eff = effective_weights["radar_nowcast"]
        contrib = round(w_eff * norm_s, 4)
        composite_score += contrib
        ts_radar = radar_evidence.observation_timestamp if radar_evidence else None
        explanations.append(
            SourceExplanation(
                source="radar_nowcast",
                name="RainViewer Doppler Weather Radar Composite",
                description=(
                    f"Peak reflectivity: {radar_evidence.max_reflectivity_dbz:.1f} dBZ, "
                    f"estimated rain rate: {radar_evidence.estimated_peak_rain_rate_mm_hr:.1f} mm/hr."
                    if radar_evidence and is_avail
                    else "Live Doppler radar composite unavailable."
                ),
                raw_value={
                    "max_reflectivity_dbz": radar_evidence.max_reflectivity_dbz,
                    "estimated_peak_rain_rate_mm_hr": radar_evidence.estimated_peak_rain_rate_mm_hr,
                }
                if radar_evidence and is_avail
                else None,
                normalized_score=round(norm_s, 4),
                original_weight=original_weights["radar_nowcast"],
                effective_weight=w_eff,
                contribution=contrib,
                timestamp=ts_radar,
                status="available" if is_avail else "unavailable",
            )
        )
        if radar_evidence and is_avail and radar_evidence.max_reflectivity_dbz >= 45.0:
            trigger_reasons.append(
                f"Doppler radar reflectivity ({radar_evidence.max_reflectivity_dbz:.1f} dBZ) "
                f"indicates intense convective precipitation core."
            )

        # 4. Satellite Inundation Explanation
        is_avail, obj, norm_s = streams["satellite_inundation"]
        w_eff = effective_weights["satellite_inundation"]
        contrib = round(w_eff * norm_s, 4)
        composite_score += contrib
        ts_sat = satellite_evidence.scene_acquisition_datetime if satellite_evidence else None
        temporal_st = satellite_evidence.temporal_status if satellite_evidence else "unavailable"
        explanations.append(
            SourceExplanation(
                source="satellite_inundation",
                name="Sentinel-2 L2A / Model 2 FloodUNet Inundation",
                description=(
                    f"Flooded area: {satellite_evidence.flooded_area_sq_km:.2f} km² "
                    f"({satellite_evidence.flooded_percentage:.1f}% of valid ground footprint), "
                    f"polygons: {satellite_evidence.polygon_count}, status: {temporal_st} "
                    f"(age: {satellite_evidence.observation_age_hours:.1f}h)."
                    if satellite_evidence and is_avail
                    else "Sentinel-2 multispectral inundation analysis unavailable."
                ),
                raw_value={
                    "flooded_area_sq_km": satellite_evidence.flooded_area_sq_km,
                    "flooded_percentage": satellite_evidence.flooded_percentage,
                    "temporal_status": temporal_st,
                }
                if satellite_evidence and is_avail
                else None,
                normalized_score=round(norm_s, 4),
                original_weight=original_weights["satellite_inundation"],
                effective_weight=w_eff,
                contribution=contrib,
                timestamp=ts_sat,
                status=temporal_st.lower() if is_avail else "unavailable",
            )
        )
        if satellite_evidence and is_avail and satellite_evidence.flooded_percentage >= 5.0:
            trigger_reasons.append(
                f"Satellite inundation segmentation detected {satellite_evidence.flooded_percentage:.1f}% "
                f"surface water coverage ({satellite_evidence.flooded_area_sq_km:.2f} km²)."
            )

        composite_score = max(0.0, min(1.0, round(composite_score, 4)))

        # Determine prototype risk level
        if composite_score <= self.settings.RISK_LOW_MAX:
            risk_level = RiskLevel.LOW
            urgency = "NONE"
            monitoring = "Routine meteorological and satellite monitoring."
        elif composite_score <= self.settings.RISK_MODERATE_MAX:
            risk_level = RiskLevel.MODERATE
            urgency = "MONITOR"
            monitoring = "Monitor 6-hour radar nowcasting and GFS forecast updates."
        elif composite_score <= self.settings.RISK_HIGH_MAX:
            risk_level = RiskLevel.HIGH
            urgency = "PREPARE"
            monitoring = "Active monitoring: hourly Doppler radar scans and municipal drainage alerts."
        else:
            risk_level = RiskLevel.EXTREME
            urgency = "ACTION"
            monitoring = "Immediate operational alert: continuous radar tracking and emergency inundation monitoring."

        if not trigger_reasons:
            trigger_reasons.append("Environmental variables within normal baseline limits.")

        # Freshness metadata
        freshness_meta = {
            "rainfall_observation_date": ts_rf,
            "nwp_forecast_time": ts_nwp,
            "radar_observation_time": ts_radar,
            "satellite_scene_time": ts_sat,
            "satellite_temporal_status": temporal_st if satellite_evidence else None,
            "satellite_observation_age_hours": satellite_evidence.observation_age_hours if satellite_evidence else None,
        }

        # Evidence dictionary
        evidence_dict = {
            "rainfall_model": rainfall_evidence.model_dump() if rainfall_evidence else None,
            "nwp": nwp_evidence.model_dump() if nwp_evidence else None,
            "radar": radar_evidence.model_dump() if radar_evidence else None,
            "satellite_inundation": satellite_evidence.model_dump() if satellite_evidence else None,
        }

        return RiskAssessmentResponse(
            status="success",
            requested_location=location,
            location_name=location_name,
            risk=RiskScoreDetail(
                score=composite_score,
                level=risk_level,
                thresholds={
                    "low_max": self.settings.RISK_LOW_MAX,
                    "moderate_max": self.settings.RISK_MODERATE_MAX,
                    "high_max": self.settings.RISK_HIGH_MAX,
                },
            ),
            evidence=evidence_dict,
            fusion=FusionMetadata(
                policy_applied=policy_applied,
                original_weights=original_weights,
                effective_weights=effective_weights,
                available_sources=available_sources,
                unavailable_sources=unavailable_sources,
                freshness=freshness_meta,
            ),
            explanations=explanations,
            prototype_warning_assessment=PrototypeWarningCandidate(
                risk_level=risk_level,
                urgency=urgency,
                trigger_reasons=trigger_reasons,
                recommended_monitoring=monitoring,
                disclaimer=(
                    "EXPERIMENTAL PROTOTYPE DECISION ASSESSMENT DEVELOPED FOR SIH 2026 PS 26071. "
                    "NOT AN OFFICIAL IMD GOVERNMENT WEATHER WARNING."
                ),
            ),
            generated_at=datetime.now(timezone.utc).isoformat(),
        )
