"""Weather Observation Service with real NASA POWER meteorological data integration."""

from datetime import date, datetime, timedelta
import logging
from typing import Any, Dict, List, Optional
import httpx

from backend.app.core.config import Settings, get_settings
from backend.app.schemas.common import Coordinates
from backend.app.schemas.prediction import RainfallPipelineResponse
from backend.app.schemas.weather import DailyWeatherRecord, WeatherFeatureVector, WeatherObservation
from backend.app.services.base import BaseService
from backend.app.services.feature_builder import Model1FeatureBuilder
from backend.app.services.model1_service import Model1Service
from backend.app.services.nasa_power_client import NasaPowerClient

logger = logging.getLogger("rainfall_backend.services.WeatherObservationService")


class WeatherObservationService(BaseService):
    """
    Service for ingesting real surface meteorological data and constructing
    leakage-safe Model 1 feature vectors via NASA POWER Daily API.
    """

    def __init__(
        self,
        settings: Optional[Settings] = None,
        nasa_client: Optional[NasaPowerClient] = None,
        http_client: Optional[httpx.AsyncClient] = None,
    ):
        super().__init__(
            name="WeatherObservationService",
            description="Surface meteorological observation ingestion and feature engineering via NASA POWER",
        )
        self.settings = settings or get_settings()
        self.nasa_client = nasa_client or NasaPowerClient(
            settings=self.settings,
            http_client=http_client,
        )
        # In-situ surface station (IMD AWS) sensor telemetry is not connected yet.
        # Remote NASA POWER meteorological pipeline is operational via async methods.
        self._is_connected = False

    def check_connection(self) -> bool:
        """In-situ station network is not yet active."""
        return False

    def get_latest_observation(self, coordinates: Coordinates) -> WeatherObservation:
        """
        In-situ surface automated weather station (IMD AWS) live sensor telemetry is not connected yet.
        Raises NotImplementedError to strictly prevent returning fake sensor data.
        """
        raise NotImplementedError(
            "Live IMD AWS weather station telemetry integration is not yet connected. "
            "Use async NASA POWER pipeline for real satellite/meteorological observations. "
            "Fake data is strictly forbidden."
        )

    def extract_feature_vector(
        self, coordinates: Coordinates, target_date: datetime
    ) -> WeatherFeatureVector:
        """
        Synchronous extraction is deprecated.
        Raises NotImplementedError to maintain contract integrity with earlier test suite.
        Use async build_feature_vector() for real network data.
        """
        raise NotImplementedError(
            "Synchronous feature extraction is not supported for remote HTTP data sources. "
            "Use async build_feature_vector() with real NASA POWER data."
        )

    async def fetch_historical_records(
        self,
        coordinates: Coordinates,
        start_date: date,
        end_date: date,
    ) -> List[DailyWeatherRecord]:
        """Fetch real daily meteorological records from NASA POWER."""
        return await self.nasa_client.fetch_daily_weather(coordinates, start_date, end_date)

    async def build_feature_vector(
        self,
        coordinates: Coordinates,
        prediction_date: date,
        history_buffer_days: int = 40,
    ) -> WeatherFeatureVector:
        """
        Fetch real NASA POWER weather history and construct the exact 37-feature vector.
        
        Fetches up to history_buffer_days before prediction_date to ensure a minimum of
        30 consecutive daily observations leading up to D-1.
        """
        target_obs_date = prediction_date - timedelta(days=1)
        start_date = target_obs_date - timedelta(days=history_buffer_days)

        logger.info(
            "Requesting NASA POWER history for (%f, %f) from %s to %s (predicting for %s)",
            coordinates.latitude,
            coordinates.longitude,
            start_date,
            target_obs_date,
            prediction_date,
        )

        records = await self.nasa_client.fetch_daily_weather(
            coordinates=coordinates,
            start_date=start_date,
            end_date=target_obs_date,
        )

        return Model1FeatureBuilder.build_feature_vector(
            records=records,
            prediction_date=prediction_date,
            coordinates=coordinates,
        )

    async def predict_rainfall(
        self,
        coordinates: Coordinates,
        prediction_date: date,
        location_name: Optional[str] = None,
    ) -> RainfallPipelineResponse:
        """
        Full end-to-end pipeline:
        1. Fetch real NASA POWER weather history
        2. Construct exact 37 features (zero leakage)
        3. Infer heavy rainfall probability via real Model 1 XGBoost
        4. Return structured response
        """
        target_obs_date = prediction_date - timedelta(days=1)
        start_date = target_obs_date - timedelta(days=40)

        # 1. Fetch real weather data
        records = await self.nasa_client.fetch_daily_weather(
            coordinates=coordinates,
            start_date=start_date,
            end_date=target_obs_date,
        )

        # 2. Build exact 37 features
        feature_vector = Model1FeatureBuilder.build_feature_vector(
            records=records,
            prediction_date=prediction_date,
            coordinates=coordinates,
        )

        # 3. Predict via Model 1
        m1 = Model1Service.get_instance()
        m1_result = m1.predict(feature_vector, location=coordinates)

        # 4. Extract latest observation summary for metadata
        latest_record = next(r for r in reversed(records) if r.date == target_obs_date)
        latest_summary = {
            "date": str(latest_record.date),
            "PRECTOTCORR": latest_record.PRECTOTCORR,
            "T2M": latest_record.T2M,
            "T2MDEW": latest_record.T2MDEW,
            "RH2M": latest_record.RH2M,
            "PS": latest_record.PS,
            "WS2M": latest_record.WS2M,
            "WS10M": latest_record.WS10M,
            "ALLSKY_SFC_SW_DWN": latest_record.ALLSKY_SFC_SW_DWN,
        }

        # 5. Return structured pipeline response
        return RainfallPipelineResponse(
            status="success",
            prediction_date=str(prediction_date),
            observation_date=str(target_obs_date),
            coordinates=coordinates,
            location_name=location_name,
            heavy_rain_predicted=m1_result.heavy_rain,
            heavy_rain_probability=m1_result.probability,
            threshold=m1_result.threshold,
            model_version=m1_result.model,
            historical_records_used=len(records),
            features_computed=len(feature_vector.model_dump()),
            latest_weather=latest_summary,
            xai=m1_result.xai,
            metadata={
                "frozen_threshold": m1_result.threshold,
                "lookback_window_days": Model1FeatureBuilder.MIN_REQUIRED_DAYS,
                "data_source": "NASA_POWER_DAILY_POINT_API",
                "community": self.settings.NASA_POWER_COMMUNITY,
            },
        )
