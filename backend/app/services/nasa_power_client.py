"""NASA POWER Daily Point API async client and response parser."""

import asyncio
from datetime import date, datetime
import logging
import math
from typing import Any, Dict, List, Optional
import httpx

from backend.app.core.config import Settings, get_settings
from backend.app.core.errors import ExternalApiError, WeatherObservationValidationError
from backend.app.schemas.common import Coordinates
from backend.app.schemas.weather import DailyWeatherRecord

logger = logging.getLogger("rainfall_backend.services.NasaPowerClient")

REQUIRED_NASA_POWER_PARAMS: List[str] = [
    "PRECTOTCORR",
    "T2M",
    "T2MDEW",
    "RH2M",
    "PS",
    "WS2M",
    "WS10M",
    "ALLSKY_SFC_SW_DWN",
]


class NasaPowerClient:
    """
    Asynchronous client for NASA POWER Daily Point API.
    Fetches real surface meteorological observations with retry, backoff, and strict validation.
    """

    def __init__(self, settings: Optional[Settings] = None, http_client: Optional[httpx.AsyncClient] = None):
        self.settings = settings or get_settings()
        self.base_url = self.settings.NASA_POWER_BASE_URL
        self.community = self.settings.NASA_POWER_COMMUNITY
        self.timeout_seconds = self.settings.NASA_POWER_TIMEOUT_SECONDS
        self.max_retries = self.settings.NASA_POWER_MAX_RETRIES
        self._custom_http_client = http_client

    async def fetch_daily_weather(
        self,
        coordinates: Coordinates,
        start_date: date,
        end_date: date,
    ) -> List[DailyWeatherRecord]:
        """
        Fetch and parse real historical daily observations between start_date and end_date.

        Raises:
            ValueError: If date range or coordinates are invalid.
            ExternalApiError: If NASA POWER API request times out or fails after retries.
            WeatherObservationValidationError: If response is corrupt, missing variables, or non-finite.
        """
        if start_date > end_date:
            raise ValueError(f"start_date ({start_date}) must be on or before end_date ({end_date})")

        params = {
            "parameters": ",".join(REQUIRED_NASA_POWER_PARAMS),
            "community": self.community,
            "longitude": f"{coordinates.longitude:.4f}",
            "latitude": f"{coordinates.latitude:.4f}",
            "start": start_date.strftime("%Y%m%d"),
            "end": end_date.strftime("%Y%m%d"),
            "format": "JSON",
        }

        logger.info(
            "Fetching NASA POWER weather data for (%f, %f) from %s to %s",
            coordinates.latitude,
            coordinates.longitude,
            start_date,
            end_date,
        )

        headers = {"User-Agent": f"SIH2026-RainfallBackend/{self.settings.APP_VERSION}"}

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

                # If client error (4xx), do not retry
                if 400 <= response.status_code < 500:
                    error_msg = f"NASA POWER API client error: HTTP {response.status_code}"
                    try:
                        err_json = response.json()
                        error_msg += f" - {err_json.get('messages', err_json)}"
                    except Exception:
                        error_msg += f" - {response.text[:200]}"
                    logger.error(error_msg)
                    raise ExternalApiError(
                        service_name="NASA_POWER",
                        message=error_msg,
                        status_code=502,
                        details={"http_status": response.status_code, "query": params},
                    )

                response.raise_for_status()

                try:
                    payload = response.json()
                except Exception as json_err:
                    raise WeatherObservationValidationError(
                        f"NASA POWER API returned invalid JSON: {str(json_err)}"
                    ) from json_err

                return self.parse_response(payload, coordinates)

            except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError) as exc:
                last_exception = exc
                logger.warning(
                    "NASA POWER API attempt %d/%d failed: %s (%s)",
                    attempt,
                    self.max_retries,
                    type(exc).__name__,
                    str(exc),
                )
                if attempt < self.max_retries:
                    delay = 0.5 * (2 ** (attempt - 1))
                    await asyncio.sleep(delay)
            except (ExternalApiError, WeatherObservationValidationError, ValueError):
                raise
            except Exception as unk_err:
                last_exception = unk_err
                logger.error("Unexpected error contacting NASA POWER API: %s", str(unk_err))
                break

        err_detail = f"{type(last_exception).__name__}: {str(last_exception)}" if last_exception else "Unknown failure"
        raise ExternalApiError(
            service_name="NASA_POWER",
            message=f"NASA POWER API request failed after {self.max_retries} attempts ({err_detail})",
            status_code=504 if isinstance(last_exception, httpx.TimeoutException) else 502,
            details={"attempts": self.max_retries, "params": params, "last_error": err_detail},
        )

    def parse_response(
        self,
        payload: Dict[str, Any],
        requested_coords: Coordinates,
    ) -> List[DailyWeatherRecord]:
        """
        Parse raw NASA POWER JSON payload into chronologically ordered DailyWeatherRecord objects.

        Strictly enforces:
        - Presence of all 8 core parameters
        - Strict numeric conversion (rejects NaN, ±Inf, and -999.0 missing values)
        - Chronological ordering
        - Coordinate proximity sanity check (within 1.0 degree grid cell tolerance)
        """
        if not isinstance(payload, dict):
            raise WeatherObservationValidationError("NASA POWER payload must be a JSON object")

        # 1. Coordinate check
        geometry = payload.get("geometry")
        if isinstance(geometry, dict) and geometry.get("type") == "Point":
            coords = geometry.get("coordinates", [])
            if len(coords) >= 2:
                ret_lon, ret_lat = float(coords[0]), float(coords[1])
                # NASA POWER resolves to nearest 0.5x0.5 grid cell centroid
                if abs(ret_lat - requested_coords.latitude) > 1.0 or abs(ret_lon - requested_coords.longitude) > 1.0:
                    logger.warning(
                        "NASA POWER grid centroid (lat=%.4f, lon=%.4f) deviates from requested (lat=%.4f, lon=%.4f)",
                        ret_lat,
                        ret_lon,
                        requested_coords.latitude,
                        requested_coords.longitude,
                    )

        # 2. Extract parameter dictionaries
        properties = payload.get("properties")
        if not isinstance(properties, dict):
            raise WeatherObservationValidationError("Missing 'properties' in NASA POWER response")

        parameter_dict = properties.get("parameter")
        if not isinstance(parameter_dict, dict):
            raise WeatherObservationValidationError("Missing 'properties.parameter' in NASA POWER response")

        # 3. Verify all required parameters exist
        for param in REQUIRED_NASA_POWER_PARAMS:
            if param not in parameter_dict or not isinstance(parameter_dict[param], dict):
                raise WeatherObservationValidationError(
                    f"Required meteorological variable '{param}' missing in NASA POWER response"
                )

        # 4. Extract and sort date keys
        sample_param = REQUIRED_NASA_POWER_PARAMS[0]
        date_keys = list(parameter_dict[sample_param].keys())
        if not date_keys:
            raise WeatherObservationValidationError(
                "NASA POWER response contains zero daily observation records"
            )

        # Ensure all required parameters share the identical date keys
        for param in REQUIRED_NASA_POWER_PARAMS[1:]:
            p_keys = set(parameter_dict[param].keys())
            if not set(date_keys).issubset(p_keys):
                missing_for_param = set(date_keys) - p_keys
                raise WeatherObservationValidationError(
                    f"Parameter '{param}' is missing records for dates: {sorted(list(missing_for_param))[:5]}"
                )

        # Sort dates chronologically
        try:
            sorted_dates = sorted(
                [(datetime.strptime(d_str, "%Y%m%d").date(), d_str) for d_str in date_keys],
                key=lambda x: x[0],
            )
        except ValueError as date_err:
            raise WeatherObservationValidationError(
                f"Failed to parse date key from NASA POWER: {str(date_err)}"
            ) from date_err

        # 5. Construct validated DailyWeatherRecord objects
        records: List[DailyWeatherRecord] = []
        for d_obj, d_str in sorted_dates:
            param_values: Dict[str, float] = {}
            for param in REQUIRED_NASA_POWER_PARAMS:
                raw_val = parameter_dict[param].get(d_str)
                if raw_val is None:
                    raise WeatherObservationValidationError(
                        f"Missing value for '{param}' on date {d_str}"
                    )
                try:
                    float_val = float(raw_val)
                except (TypeError, ValueError) as num_err:
                    raise WeatherObservationValidationError(
                        f"Non-numeric value '{raw_val}' for '{param}' on date {d_str}"
                    ) from num_err

                if not math.isfinite(float_val):
                    raise WeatherObservationValidationError(
                        f"Non-finite value '{float_val}' for '{param}' on date {d_str}"
                    )
                if float_val in (-999.0, -999, -99.0):
                    raise WeatherObservationValidationError(
                        f"NASA POWER missing sentinel value ({float_val}) encountered for '{param}' on date {d_str}"
                    )

                param_values[param] = float_val

            record = DailyWeatherRecord(
                date=d_obj,
                latitude=requested_coords.latitude,
                longitude=requested_coords.longitude,
                PRECTOTCORR=param_values["PRECTOTCORR"],
                T2M=param_values["T2M"],
                T2MDEW=param_values["T2MDEW"],
                RH2M=param_values["RH2M"],
                PS=param_values["PS"],
                WS2M=param_values["WS2M"],
                WS10M=param_values["WS10M"],
                ALLSKY_SFC_SW_DWN=param_values["ALLSKY_SFC_SW_DWN"],
            )
            records.append(record)

        return records
