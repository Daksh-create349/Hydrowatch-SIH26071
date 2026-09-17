"""Numerical Weather Prediction (NWP) client for Open-Meteo NOAA GFS API."""

import asyncio
from datetime import datetime, timezone
import logging
import math
from typing import Any, Dict, List, Optional
import httpx

from backend.app.core.config import Settings, get_settings
from backend.app.core.errors import ExternalApiError, WeatherObservationValidationError
from backend.app.schemas.common import Coordinates
from backend.app.schemas.nwp import (
    NWPForecastItem,
    NWPForecastSummary,
    NWPPointForecastResponse,
)

logger = logging.getLogger("rainfall_backend.services.OpenMeteoNwpClient")

REQUIRED_NWP_HOURLY_FIELDS: List[str] = [
    "time",
    "precipitation",
    "temperature_2m",
    "relative_humidity_2m",
    "dew_point_2m",
    "surface_pressure",
    "wind_speed_10m",
]


class OpenMeteoNwpClient:
    """
    Asynchronous client for Open-Meteo GFS Numerical Weather Prediction API.
    Fetches real NOAA Global Forecast System (0.25° grid) atmospheric forecasts.
    """

    def __init__(
        self,
        settings: Optional[Settings] = None,
        http_client: Optional[httpx.AsyncClient] = None,
    ):
        self.settings = settings or get_settings()
        self.base_url = self.settings.NWP_BASE_URL
        self.model = self.settings.NWP_MODEL
        self.timeout_seconds = self.settings.NWP_TIMEOUT_SECONDS
        self.max_retries = self.settings.NWP_MAX_RETRIES
        self._custom_http_client = http_client

    async def fetch_point_forecast(
        self,
        coordinates: Coordinates,
        forecast_days: int = 3,
    ) -> NWPPointForecastResponse:
        """
        Fetch real NWP point forecast for given coordinates over forecast_days horizon.

        Raises:
            ExternalApiError: If Open-Meteo GFS request times out or returns HTTP error.
            WeatherObservationValidationError: If response is corrupt, missing fields, or non-finite.
        """
        days = max(1, min(16, forecast_days))
        params = {
            "latitude": f"{coordinates.latitude:.4f}",
            "longitude": f"{coordinates.longitude:.4f}",
            "hourly": "precipitation,temperature_2m,relative_humidity_2m,dew_point_2m,surface_pressure,wind_speed_10m,cape",
            "wind_speed_unit": "ms",
            "models": self.model,
            "forecast_days": days,
        }

        headers = {"User-Agent": f"SIH2026-RainfallBackend/{self.settings.APP_VERSION}"}

        logger.info(
            "Requesting NWP forecast from Open-Meteo (%s) for (%f, %f), horizon=%d days",
            self.model,
            coordinates.latitude,
            coordinates.longitude,
            days,
        )

        last_exception: Optional[Exception] = None

        for attempt in range(1, self.max_retries + 1):
            try:
                if self._custom_http_client:
                    response = await self._custom_http_client.get(
                        self.base_url,
                        params=params,
                        headers=headers,
                        timeout=self.timeout_seconds,
                    )
                else:
                    async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                        response = await client.get(
                            self.base_url,
                            params=params,
                            headers=headers,
                        )

                if 400 <= response.status_code < 500:
                    err_msg = f"NWP API client error HTTP {response.status_code}: {response.text[:200]}"
                    logger.error(err_msg)
                    raise ExternalApiError(
                        service_name="OPEN_METEO_GFS",
                        message=err_msg,
                        status_code=502,
                        details={"http_status": response.status_code, "params": params},
                    )

                response.raise_for_status()

                try:
                    payload = response.json()
                except Exception as json_err:
                    raise WeatherObservationValidationError(
                        f"NWP provider returned invalid JSON: {str(json_err)}"
                    ) from json_err

                return self.parse_response(payload, coordinates)

            except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError) as exc:
                last_exception = exc
                logger.warning(
                    "NWP API attempt %d/%d failed: %s (%s)",
                    attempt,
                    self.max_retries,
                    type(exc).__name__,
                    str(exc),
                )
                if attempt < self.max_retries:
                    await asyncio.sleep(0.5 * (2 ** (attempt - 1)))
            except (ExternalApiError, WeatherObservationValidationError):
                raise
            except Exception as unk_err:
                last_exception = unk_err
                logger.error("Unexpected error contacting NWP provider: %s", str(unk_err))
                break

        err_detail = f"{type(last_exception).__name__}: {str(last_exception)}" if last_exception else "Unknown error"
        raise ExternalApiError(
            service_name="OPEN_METEO_GFS",
            message=f"NWP API request failed after {self.max_retries} attempts ({err_detail})",
            status_code=504 if isinstance(last_exception, httpx.TimeoutException) else 502,
            details={"attempts": self.max_retries, "params": params, "last_error": err_detail},
        )

    def parse_response(
        self,
        payload: Dict[str, Any],
        requested_coords: Coordinates,
    ) -> NWPPointForecastResponse:
        """Parse raw Open-Meteo GFS JSON response into NWPPointForecastResponse."""
        if not isinstance(payload, dict):
            raise WeatherObservationValidationError("NWP payload must be a JSON object")

        hourly = payload.get("hourly")
        if not isinstance(hourly, dict):
            raise WeatherObservationValidationError("Missing 'hourly' dictionary in NWP response")

        for field in REQUIRED_NWP_HOURLY_FIELDS:
            if field not in hourly or not isinstance(hourly[field], list):
                raise WeatherObservationValidationError(
                    f"Required NWP variable '{field}' missing in hourly output"
                )

        times = hourly["time"]
        count = len(times)
        if count == 0:
            raise WeatherObservationValidationError("NWP response returned zero hourly intervals")

        for field in REQUIRED_NWP_HOURLY_FIELDS:
            if len(hourly[field]) != count:
                raise WeatherObservationValidationError(
                    f"Mismatched length in NWP variable '{field}': expected {count}, got {len(hourly[field])}"
                )

        precip_list = hourly["precipitation"]
        temp_list = hourly["temperature_2m"]
        rh_list = hourly["relative_humidity_2m"]
        dew_list = hourly["dew_point_2m"]
        pres_list = hourly["surface_pressure"]
        wind_list = hourly["wind_speed_10m"]
        cape_list = hourly.get("cape", [None] * count)

        forecast_items: List[NWPForecastItem] = []
        for i in range(count):
            try:
                precip = float(precip_list[i]) if precip_list[i] is not None else 0.0
                temp = float(temp_list[i])
                rh = float(rh_list[i])
                dew = float(dew_list[i])
                pres_hpa = float(pres_list[i])
                wind = float(wind_list[i])
                cape = float(cape_list[i]) if cape_list[i] is not None else None
            except (TypeError, ValueError) as err:
                raise WeatherObservationValidationError(
                    f"Non-numeric value in NWP forecast at hour {i}: {str(err)}"
                ) from err

            # Finite number checks
            for val, name in [(precip, "precipitation"), (temp, "temperature_2m"), (rh, "relative_humidity_2m"), (pres_hpa, "surface_pressure"), (wind, "wind_speed_10m")]:
                if not math.isfinite(val):
                    raise WeatherObservationValidationError(f"Non-finite value ({val}) for NWP field '{name}' at step {i}")

            pres_kpa = round(pres_hpa / 10.0, 4)

            forecast_items.append(
                NWPForecastItem(
                    valid_time=times[i],
                    lead_hours=i,
                    precipitation_mm_hr=max(0.0, round(precip, 3)),
                    temperature_2m_c=round(temp, 2),
                    relative_humidity_pct=max(0.0, min(100.0, round(rh, 1))),
                    dew_point_2m_c=round(dew, 2),
                    surface_pressure_hpa=round(pres_hpa, 2),
                    surface_pressure_kpa=pres_kpa,
                    wind_speed_10m_ms=max(0.0, round(wind, 2)),
                    cape_j_kg=round(cape, 1) if cape is not None and math.isfinite(cape) else None,
                )
            )

        precips = [item.precipitation_mm_hr for item in forecast_items]
        temps = [item.temperature_2m_c for item in forecast_items]
        winds = [item.wind_speed_10m_ms for item in forecast_items]
        capes = [item.cape_j_kg for item in forecast_items if item.cape_j_kg is not None]

        summary = NWPForecastSummary(
            total_precipitation_mm=round(sum(precips), 2),
            max_hourly_precipitation_mm_hr=round(max(precips), 2),
            min_temperature_c=round(min(temps), 2),
            max_temperature_c=round(max(temps), 2),
            max_wind_speed_ms=round(max(winds), 2),
            max_cape_j_kg=round(max(capes), 1) if capes else None,
        )

        elevation = payload.get("elevation")

        return NWPPointForecastResponse(
            status="success",
            source="Open-Meteo GFS (NOAA 0.25° Seamless)",
            model_name=self.model,
            coordinates=requested_coords,
            elevation_m=float(elevation) if elevation is not None else None,
            generated_at=datetime.now(timezone.utc).isoformat(),
            forecast_horizon_hours=count,
            forecast_count=count,
            units={
                "time": "ISO 8601 UTC",
                "precipitation": "mm/hour",
                "temperature": "°C",
                "relative_humidity": "%",
                "surface_pressure": "hPa / kPa",
                "wind_speed": "m/s",
                "cape": "J/kg",
            },
            summary=summary,
            forecasts=forecast_items,
            metadata={
                "grid_resolution": "0.25° (~25 km)",
                "update_frequency": "4x daily (00, 06, 12, 18 UTC cycles)",
                "provider_url": "https://open-meteo.com/",
                "data_license": "ODbL / Open Data",
            },
        )
