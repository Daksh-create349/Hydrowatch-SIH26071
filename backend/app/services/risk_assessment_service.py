"""Multi-source Risk Assessment Pipeline Orchestrator."""

import asyncio
from datetime import date, datetime, timezone
import logging
from typing import Optional

from backend.app.core.config import Settings, get_settings
from backend.app.schemas.common import Coordinates
from backend.app.schemas.risk import (
    NwpEvidence,
    RadarEvidence,
    RainfallEvidence,
    RiskAssessmentResponse,
    SatelliteInundationEvidence,
)
from backend.app.services.base import BaseService
from backend.app.services.nwp_service import NWPService
from backend.app.services.radar_service import RadarService
from backend.app.services.risk_fusion_service import RiskFusionService
from backend.app.services.satellite_imagery_service import SatelliteImageryService
from backend.app.services.weather_service import WeatherObservationService

logger = logging.getLogger("rainfall_backend.services.risk_assessment")


class RiskAssessmentService(BaseService):
    """
    Orchestrates real multi-source data ingestion and risk fusion:
    1. Real Model 1 Next-Day Heavy Rainfall XGBoost (NASA POWER)
    2. Real Numerical Weather Prediction (Open-Meteo NOAA GFS)
    3. Real Doppler Weather Radar scans (RainViewer)
    4. Real Sentinel-2 Level-2A Inundation Inference (Model 2 FloodUNet)
    5. Missing-source policy, weight renormalization, and explainability decomposition.
    """

    def __init__(
        self,
        settings: Optional[Settings] = None,
        weather_service: Optional[WeatherObservationService] = None,
        nwp_service: Optional[NWPService] = None,
        radar_service: Optional[RadarService] = None,
        satellite_service: Optional[SatelliteImageryService] = None,
        fusion_service: Optional[RiskFusionService] = None,
    ):
        super().__init__(
            name="RiskAssessmentService",
            description="End-to-end multi-source environmental risk assessment orchestrator",
        )
        self.settings = settings or get_settings()
        self.weather_service = weather_service or WeatherObservationService(settings=self.settings)
        self.nwp_service = nwp_service or NWPService(settings=self.settings)
        self.radar_service = radar_service or RadarService(settings=self.settings)
        self.satellite_service = satellite_service or SatelliteImageryService()
        self.fusion_service = fusion_service or RiskFusionService()

    def check_connection(self) -> bool:
        """Baseline check."""
        return True

    async def assess_risk(
        self,
        latitude: float,
        longitude: float,
        prediction_date: Optional[date] = None,
        nwp_horizon_hours: int = 24,
        satellite_max_cloud: float = 25.0,
        min_polygon_area_sq_m: float = 500.0,
        location_name: Optional[str] = None,
    ) -> RiskAssessmentResponse:
        """
        Execute parallel real data ingestion and deterministic fusion.
        Handles partial stream failures gracefully according to Missing-Source Policy.
        """
        coords = Coordinates(latitude=latitude, longitude=longitude)
        target_date = prediction_date or datetime.now(timezone.utc).date()

        logger.info(
            "Starting multi-source risk assessment for (%f, %f) on date=%s, nwp_horizon=%dh, max_cloud=%.1f%%",
            latitude,
            longitude,
            target_date,
            nwp_horizon_hours,
            satellite_max_cloud,
        )

        # NWP forecast days needed
        nwp_forecast_days = max(1, (nwp_horizon_hours + 23) // 24)

        # Concurrently execute real ingestion across all 4 independent streams
        m1_task = self.weather_service.predict_rainfall(
            coordinates=coords,
            prediction_date=target_date,
            location_name=location_name,
        )
        nwp_task = self.nwp_service.fetch_point_forecast(
            coordinates=coords,
            forecast_days=nwp_forecast_days,
        )
        radar_task = self.radar_service.fetch_radar_composite(
            coordinates=coords,
        )
        sat_task = self.satellite_service.predict_inundation(
            latitude=latitude,
            longitude=longitude,
            target_date=target_date,
            max_cloud_percentage=satellite_max_cloud,
            min_polygon_area_sq_m=min_polygon_area_sq_m,
            location_name=location_name,
        )

        results = await asyncio.gather(
            m1_task,
            nwp_task,
            radar_task,
            sat_task,
            return_exceptions=True,
        )

        m1_res, nwp_res, radar_res, sat_res = results

        # ------------------------------------------------------------
        # 1. Parse Model 1 Rainfall Evidence
        # ------------------------------------------------------------
        rainfall_ev: Optional[RainfallEvidence] = None
        if isinstance(m1_res, Exception):
            logger.warning("Risk assessment: Model 1 rainfall stream failed: %s", m1_res)
        elif m1_res is not None:
            latest_weather = getattr(m1_res, "latest_weather", {}) or {}
            precip = float(latest_weather.get("PRECTOTCORR", 0.0))
            rainfall_ev = RainfallEvidence(
                heavy_rain_probability=m1_res.heavy_rain_probability,
                heavy_rain_predicted=m1_res.heavy_rain_predicted,
                model_threshold=m1_res.threshold,
                observation_date=m1_res.observation_date,
                latest_precipitation_mm=precip,
                historical_records_used=m1_res.historical_records_used,
                source="NASA POWER + Model 1 XGBoost",
                available=True,
            )

        # ------------------------------------------------------------
        # 2. Parse NWP Forecast Evidence
        # ------------------------------------------------------------
        nwp_ev: Optional[NwpEvidence] = None
        if isinstance(nwp_res, Exception):
            logger.warning("Risk assessment: NWP forecast stream failed: %s", nwp_res)
        elif nwp_res is not None:
            horizon_hrs = min(nwp_horizon_hours, nwp_res.forecast_horizon_hours)
            mean_rate = nwp_res.summary.total_precipitation_mm / float(horizon_hrs) if horizon_hrs > 0 else 0.0
            nwp_ev = NwpEvidence(
                forecast_precipitation_mm_hr=round(mean_rate, 2),
                max_hourly_precipitation_mm_hr=round(nwp_res.summary.max_hourly_precipitation_mm_hr, 2),
                accumulated_precipitation_mm=round(nwp_res.summary.total_precipitation_mm, 2),
                max_cape_j_kg=nwp_res.summary.max_cape_j_kg,
                forecast_horizon_hours=horizon_hrs,
                forecast_start_time=nwp_res.forecasts[0].valid_time if nwp_res.forecasts else None,
                forecast_end_time=nwp_res.forecasts[-1].valid_time if nwp_res.forecasts else None,
                source_model=f"{nwp_res.model_name} via Open-Meteo",
                available=True,
            )

        # ------------------------------------------------------------
        # 3. Parse Doppler Radar Evidence
        # ------------------------------------------------------------
        radar_ev: Optional[RadarEvidence] = None
        if isinstance(radar_res, Exception):
            logger.warning("Risk assessment: Radar scan stream failed: %s", radar_res)
        elif radar_res is not None:
            scan = radar_res.latest_scan
            radar_ev = RadarEvidence(
                max_reflectivity_dbz=scan.max_reflectivity_dbz,
                mean_reflectivity_dbz=scan.mean_reflectivity_dbz,
                active_echo_percentage=scan.echo_coverage_pct,
                estimated_peak_rain_rate_mm_hr=scan.estimated_max_rain_rate_mm_hr,
                observation_timestamp=scan.timestamp_iso,
                source=radar_res.source,
                available=True,
            )

        # ------------------------------------------------------------
        # 4. Parse Sentinel-2 Inundation Evidence
        # ------------------------------------------------------------
        sat_ev: Optional[SatelliteInundationEvidence] = None
        if isinstance(sat_res, Exception):
            logger.warning("Risk assessment: Sentinel-2 inundation stream failed: %s", sat_res)
        elif sat_res is not None:
            scene_meta = sat_res.selected_scene or {}
            acq_raw = scene_meta.get("acquisition_datetime")
            acq_time_str: Optional[str] = None
            age_hours = 0.0
            if acq_raw is not None:
                if isinstance(acq_raw, datetime):
                    acq_dt = acq_raw if acq_raw.tzinfo else acq_raw.replace(tzinfo=timezone.utc)
                    acq_time_str = acq_dt.isoformat()
                else:
                    acq_time_str = str(acq_raw)
                    try:
                        acq_dt = datetime.fromisoformat(acq_time_str.replace("Z", "+00:00"))
                    except Exception:
                        acq_dt = None
                if acq_dt:
                    now_dt = datetime.now(timezone.utc)
                    age_hours = max(0.0, (now_dt - acq_dt).total_seconds() / 3600.0)

            if age_hours <= self.settings.SATELLITE_CURRENT_MAX_AGE_HOURS:
                temp_status = "CURRENT"
            elif age_hours <= self.settings.SATELLITE_RECENT_MAX_AGE_HOURS:
                temp_status = "RECENT"
            else:
                temp_status = "HISTORICAL"

            sat_ev = SatelliteInundationEvidence(
                flooded_area_sq_km=sat_res.flooded_area_sq_km,
                valid_area_sq_km=sat_res.valid_area_sq_km,
                flooded_percentage=sat_res.flooded_percentage,
                polygon_count=sat_res.polygon_count,
                scene_id=scene_meta.get("scene_id"),
                scene_acquisition_datetime=acq_time_str,
                cloud_coverage_percentage=scene_meta.get("cloud_coverage_percentage"),
                model_threshold=sat_res.threshold,
                temporal_status=temp_status,
                observation_age_hours=round(age_hours, 1),
                source="Sentinel-2 L2A via Element 84 Earth Search",
                available=True,
            )

        # ------------------------------------------------------------
        # 5. Deterministic Multi-Source Risk Fusion
        # ------------------------------------------------------------
        return self.fusion_service.fuse_evidence(
            location=coords,
            rainfall_evidence=rainfall_ev,
            nwp_evidence=nwp_ev,
            radar_evidence=radar_ev,
            satellite_evidence=sat_ev,
            location_name=location_name,
        )
