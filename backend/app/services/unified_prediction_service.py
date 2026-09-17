"""Unified end-to-end prediction pipeline orchestrator."""

import asyncio
from datetime import date, datetime, timezone
import logging
import time
from typing import Any, Dict, List, Optional, Tuple

from backend.app.core.config import Settings, get_settings
from backend.app.core.errors import WeatherObservationValidationError
from backend.app.schemas.common import Coordinates
from backend.app.schemas.prediction import InundationPipelineResponse, RainfallPipelineResponse
from backend.app.schemas.risk import (
    NwpEvidence,
    RadarEvidence,
    RainfallEvidence,
    SatelliteInundationEvidence,
)
from backend.app.schemas.unified import (
    SourceStatusDetail,
    UnifiedInundationSummary,
    UnifiedNwpSummary,
    UnifiedPredictionRequest,
    UnifiedPredictionResponse,
    UnifiedRadarSummary,
    UnifiedRainfallSummary,
    UnifiedRiskSummary,
    UnifiedTimingDetail,
)
from backend.app.services.base import BaseService
from backend.app.services.nwp_service import NWPService
from backend.app.services.radar_service import RadarService
from backend.app.services.risk_fusion_service import RiskFusionService
from backend.app.services.satellite_imagery_service import SatelliteImageryService
from backend.app.services.warning_service import WarningService
from backend.app.services.weather_service import WeatherObservationService

logger = logging.getLogger("rainfall_backend.services.unified_prediction")


class UnifiedPredictionService(BaseService):
    """
    Unified end-to-end prediction orchestrator.
    Concurrently coordinates independent environmental data ingestion and ML inference:
    1. Observational weather & Model 1 XGBoost heavy rainfall probability (NASA POWER)
    2. Numerical Weather Prediction forecast (Open-Meteo NOAA GFS)
    3. Doppler Weather Radar observations (RainViewer)
    4. Sentinel-2 Level-2A imagery & Model 2 FloodUNet inundation (Element 84 Earth Search)
    5. Multi-source risk fusion with dynamic missing-source weight renormalization
    6. Deterministic warning decision engine with physical trigger evaluations

    Never calls internal HTTP endpoints; coordinates service classes directly in-process.
    """

    def __init__(
        self,
        settings: Optional[Settings] = None,
        weather_service: Optional[WeatherObservationService] = None,
        nwp_service: Optional[NWPService] = None,
        radar_service: Optional[RadarService] = None,
        satellite_service: Optional[SatelliteImageryService] = None,
        fusion_service: Optional[RiskFusionService] = None,
        warning_service: Optional[WarningService] = None,
    ):
        super().__init__(
            name="UnifiedPredictionService",
            description="Unified end-to-end multi-source prediction orchestrator",
        )
        self.settings = settings or get_settings()
        self.weather_service = weather_service or WeatherObservationService(settings=self.settings)
        self.nwp_service = nwp_service or NWPService(settings=self.settings)
        self.radar_service = radar_service or RadarService(settings=self.settings)
        self.satellite_service = satellite_service or SatelliteImageryService()
        self.fusion_service = fusion_service or RiskFusionService()
        self.warning_service = warning_service or WarningService()

    def check_connection(self) -> bool:
        """Health check."""
        return True

    async def predict(self, request: UnifiedPredictionRequest) -> UnifiedPredictionResponse:
        """
        Execute unified prediction workflow:
        Stage A: Concurrent independent evidence collection with latency measurement
        Stage B: Deterministic multi-source risk fusion with missing-source handling
        Stage C: Explainable warning decision and physical trigger evaluation
        Stage D: Complete response assembly with GeoJSON, status, and provenance
        """
        t0 = time.perf_counter()

        # ------------------------------------------------------------
        # 1. Parameter Validation & Date Normalization
        # ------------------------------------------------------------
        target_date: date
        if request.prediction_date:
            try:
                target_date = datetime.strptime(request.prediction_date, "%Y-%m-%d").date()
            except ValueError as err:
                raise WeatherObservationValidationError(
                    f"Invalid prediction_date format: '{request.prediction_date}'. Expected 'YYYY-MM-DD'."
                ) from err
        else:
            target_date = datetime.now(timezone.utc).date()

        sat_date: Optional[date] = None
        if request.satellite_date:
            try:
                sat_date = datetime.strptime(request.satellite_date, "%Y-%m-%d").date()
            except ValueError as err:
                raise WeatherObservationValidationError(
                    f"Invalid satellite_date format: '{request.satellite_date}'. Expected 'YYYY-MM-DD'."
                ) from err

        coords = Coordinates(latitude=request.latitude, longitude=request.longitude)
        nwp_horizon = request.nwp_horizon_hours or 24
        nwp_forecast_days = max(1, (nwp_horizon + 23) // 24)
        sat_max_cloud = request.satellite_max_cloud if request.satellite_max_cloud is not None else 25.0
        min_poly_area = request.min_polygon_area_sq_m if request.min_polygon_area_sq_m is not None else 500.0

        logger.info(
            "Unified prediction started for (%f, %f), target_date=%s, nwp_horizon=%dh, max_cloud=%.1f%%",
            request.latitude,
            request.longitude,
            target_date,
            nwp_horizon,
            sat_max_cloud,
        )

        # ------------------------------------------------------------
        # 2. Stage A: Concurrent Evidence Collection
        # ------------------------------------------------------------
        async def _safe_run(coro) -> Tuple[Any, float, Optional[Exception]]:
            start = time.perf_counter()
            try:
                result = await coro
                elapsed_ms = (time.perf_counter() - start) * 1000.0
                return result, elapsed_ms, None
            except Exception as exc:
                elapsed_ms = (time.perf_counter() - start) * 1000.0
                return None, elapsed_ms, exc

        weather_coro = self.weather_service.predict_rainfall(
            coordinates=coords,
            prediction_date=target_date,
            location_name=request.location_name,
        )
        nwp_coro = self.nwp_service.fetch_point_forecast(
            coordinates=coords,
            forecast_days=nwp_forecast_days,
        )
        radar_coro = self.radar_service.fetch_radar_composite(
            coordinates=coords,
        )
        satellite_coro = self.satellite_service.predict_inundation(
            latitude=request.latitude,
            longitude=request.longitude,
            target_date=sat_date or target_date,
            max_cloud_percentage=sat_max_cloud,
            min_polygon_area_sq_m=min_poly_area,
            location_name=request.location_name,
        )

        results = await asyncio.gather(
            _safe_run(weather_coro),
            _safe_run(nwp_coro),
            _safe_run(radar_coro),
            _safe_run(satellite_coro),
        )

        (m1_res, m1_ms, m1_err), (nwp_res, nwp_ms, nwp_err), (radar_res, radar_ms, radar_err), (sat_res, sat_ms, sat_err) = results

        source_status: Dict[str, SourceStatusDetail] = {}

        # ------------------------------------------------------------
        # 3. Process Model 1 Rainfall Stream
        # ------------------------------------------------------------
        rainfall_ev: Optional[RainfallEvidence] = None
        rainfall_summary: Optional[UnifiedRainfallSummary] = None
        if m1_err is not None:
            logger.warning("Unified prediction: Weather/Model 1 stream failed: %s", m1_err)
            source_status["weather_model1"] = SourceStatusDetail(
                available=False,
                status="failed",
                source="NASA POWER + Model 1 XGBoost",
                latency_ms=round(m1_ms, 2),
                timestamp=None,
                error=f"{m1_err.__class__.__name__}: {m1_err}",
            )
        elif isinstance(m1_res, RainfallPipelineResponse):
            latest_weather = m1_res.latest_weather or {}
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
            rainfall_summary = UnifiedRainfallSummary(
                probability=m1_res.heavy_rain_probability,
                predicted=m1_res.heavy_rain_predicted,
                threshold=m1_res.threshold,
                observation_date=m1_res.observation_date,
                model_version=m1_res.model_version,
                historical_records_used=m1_res.historical_records_used,
                latest_precipitation_mm=precip,
                xai=m1_res.xai,
            )
            source_status["weather_model1"] = SourceStatusDetail(
                available=True,
                status="success",
                source="NASA POWER + Model 1 XGBoost",
                latency_ms=round(m1_ms, 2),
                timestamp=m1_res.observation_date,
                error=None,
            )

        # ------------------------------------------------------------
        # 4. Process NWP Forecast Stream
        # ------------------------------------------------------------
        nwp_ev: Optional[NwpEvidence] = None
        nwp_summary: Optional[UnifiedNwpSummary] = None
        if nwp_err is not None:
            logger.warning("Unified prediction: NWP forecast stream failed: %s", nwp_err)
            source_status["nwp"] = SourceStatusDetail(
                available=False,
                status="failed",
                source="Open-Meteo GFS (NOAA 0.25° Seamless)",
                latency_ms=round(nwp_ms, 2),
                timestamp=None,
                error=f"{nwp_err.__class__.__name__}: {nwp_err}",
            )
        elif nwp_res is not None:
            horizon_hrs = min(nwp_horizon, nwp_res.forecast_horizon_hours)
            mean_rate = nwp_res.summary.total_precipitation_mm / float(horizon_hrs) if horizon_hrs > 0 else 0.0
            valid_times = [item.valid_time for item in (nwp_res.forecasts or [])][:horizon_hrs]

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
            hourly_precip = [
                round(float(item.precipitation_mm_hr), 2)
                for item in (nwp_res.forecasts or [])[:horizon_hrs]
            ]
            nwp_summary = UnifiedNwpSummary(
                source=nwp_res.source,
                model_name=nwp_res.model_name,
                forecast_summary=nwp_res.summary,
                forecast_horizon_hours=horizon_hrs,
                valid_times=valid_times,
                peak_hourly_precipitation_mm_hr=round(nwp_res.summary.max_hourly_precipitation_mm_hr, 2),
                accumulated_precipitation_mm=round(nwp_res.summary.total_precipitation_mm, 2),
                max_cape_j_kg=nwp_res.summary.max_cape_j_kg,
                hourly_precipitation=hourly_precip,
            )
            source_status["nwp"] = SourceStatusDetail(
                available=True,
                status="success",
                source=f"{nwp_res.model_name} via Open-Meteo",
                latency_ms=round(nwp_ms, 2),
                timestamp=nwp_res.generated_at,
                error=None,
            )

        # ------------------------------------------------------------
        # 5. Process Doppler Radar Stream
        # ------------------------------------------------------------
        radar_ev: Optional[RadarEvidence] = None
        radar_summary: Optional[UnifiedRadarSummary] = None
        if radar_err is not None:
            logger.warning("Unified prediction: Radar stream failed: %s", radar_err)
            source_status["radar"] = SourceStatusDetail(
                available=False,
                status="failed",
                source="RainViewer Global Doppler Radar Composite",
                latency_ms=round(radar_ms, 2),
                timestamp=None,
                error=f"{radar_err.__class__.__name__}: {radar_err}",
            )
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
            radar_summary = UnifiedRadarSummary(
                source=radar_res.source,
                timestamp=scan.timestamp_iso,
                max_reflectivity_dbz=scan.max_reflectivity_dbz,
                mean_reflectivity_dbz=scan.mean_reflectivity_dbz,
                estimated_rain_rate_mm_hr=scan.estimated_max_rain_rate_mm_hr,
                coverage_percentage=scan.echo_coverage_pct,
                tile_url=scan.tile_url,
            )
            source_status["radar"] = SourceStatusDetail(
                available=True,
                status="success",
                source=radar_res.source,
                latency_ms=round(radar_ms, 2),
                timestamp=scan.timestamp_iso,
                error=None,
            )

        # ------------------------------------------------------------
        # 6. Process Sentinel-2 / Model 2 Inundation Stream
        # ------------------------------------------------------------
        sat_ev: Optional[SatelliteInundationEvidence] = None
        inundation_summary: Optional[UnifiedInundationSummary] = None
        if sat_err is not None:
            logger.warning("Unified prediction: Sentinel-2 inundation stream failed: %s", sat_err)
            source_status["satellite_model2"] = SourceStatusDetail(
                available=False,
                status="failed",
                source="Sentinel-2 L2A via Element 84 Earth Search",
                latency_ms=round(sat_ms, 2),
                timestamp=None,
                error=f"{sat_err.__class__.__name__}: {sat_err}",
            )
        elif isinstance(sat_res, InundationPipelineResponse):
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
            inundation_summary = UnifiedInundationSummary(
                source="Sentinel-2 L2A via Element 84 Earth Search",
                scene=scene_meta,
                flooded_area_sq_km=sat_res.flooded_area_sq_km,
                valid_area_sq_km=sat_res.valid_area_sq_km,
                flooded_percentage=sat_res.flooded_percentage,
                polygon_count=sat_res.polygon_count,
                geojson=sat_res.geojson,
            )
            source_status["satellite_model2"] = SourceStatusDetail(
                available=True,
                status="success",
                source="Sentinel-2 L2A via Element 84 Earth Search",
                latency_ms=round(sat_ms, 2),
                timestamp=acq_time_str,
                error=None,
            )

        # ------------------------------------------------------------
        # 7. Stage B: Multi-Source Risk Fusion
        # ------------------------------------------------------------
        fusion_start = time.perf_counter()
        risk_response = self.fusion_service.fuse_evidence(
            location=coords,
            rainfall_evidence=rainfall_ev,
            nwp_evidence=nwp_ev,
            radar_evidence=radar_ev,
            satellite_evidence=sat_ev,
            location_name=request.location_name,
        )
        fusion_ms = (time.perf_counter() - fusion_start) * 1000.0

        # ------------------------------------------------------------
        # 8. Stage C: Warning Decision Layer
        # ------------------------------------------------------------
        warning_start = time.perf_counter()
        warning_response = self.warning_service.evaluate_warning(risk_response)
        warning_ms = (time.perf_counter() - warning_start) * 1000.0

        total_ms = (time.perf_counter() - t0) * 1000.0

        # ------------------------------------------------------------
        # 9. Stage D: Assemble Unified Response
        # ------------------------------------------------------------
        risk_summary = UnifiedRiskSummary(
            score=risk_response.risk.score,
            level=risk_response.risk.level,
            thresholds=risk_response.risk.thresholds,
            fusion=risk_response.fusion,
            explanations=risk_response.explanations,
        )

        timing = UnifiedTimingDetail(
            weather_model1_ms=round(m1_ms, 2),
            nwp_ms=round(nwp_ms, 2),
            radar_ms=round(radar_ms, 2),
            satellite_model2_ms=round(sat_ms, 2),
            fusion_ms=round(fusion_ms, 2),
            warning_ms=round(warning_ms, 2),
            total_ms=round(total_ms, 2),
        )

        return UnifiedPredictionResponse(
            status="success",
            request=request.model_dump(),
            generated_at=datetime.now(timezone.utc).isoformat(),
            rainfall_prediction=rainfall_summary,
            nwp=nwp_summary,
            radar=radar_summary,
            inundation=inundation_summary,
            risk=risk_summary,
            warning=warning_response.warning,
            source_status=source_status,
            timing=timing,
            provenance=warning_response.source_provenance,
        )
