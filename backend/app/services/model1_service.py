"""Model 1 (Next-Day Heavy Rainfall Prediction) real inference service."""

from datetime import datetime, timezone
import logging
from pathlib import Path
import threading
from typing import Any, Dict, List, Optional
import numpy as np
import xgboost as xgb

from backend.app.core.config import get_settings
from backend.app.core.errors import ModelNotLoadedError
from backend.app.schemas.common import Coordinates
from backend.app.schemas.prediction import (
    FeatureShapContribution,
    RainfallPrediction,
    RainfallPredictionResponse,
    RainfallXaiSummary,
)
from backend.app.schemas.weather import WeatherFeatureVector
from backend.app.services.base import BaseService

logger = logging.getLogger("rainfall_backend.services.Model1Service")

# Exact 37 features in exact training order from best_heavy_rain_xgboost_v2.json
MODEL1_FEATURE_ORDER: List[str] = [
    "PRECTOTCORR",
    "T2M",
    "T2MDEW",
    "RH2M",
    "PS",
    "WS2M",
    "WS10M",
    "ALLSKY_SFC_SW_DWN",
    "rain_lag_1d",
    "rain_lag_2d",
    "rain_lag_3d",
    "rain_lag_7d",
    "rain_lag_14d",
    "rain_sum_prev_3d",
    "rain_sum_prev_7d",
    "rain_sum_prev_14d",
    "rain_sum_prev_30d",
    "rain_mean_prev_7d",
    "rain_max_prev_7d",
    "T2M_lag_1d",
    "T2MDEW_lag_1d",
    "RH2M_lag_1d",
    "PS_lag_1d",
    "WS2M_lag_1d",
    "WS10M_lag_1d",
    "ALLSKY_SFC_SW_DWN_lag_1d",
    "temperature_change_1d",
    "humidity_change_1d",
    "pressure_change_1d",
    "wind_change_1d",
    "month",
    "month_sin",
    "month_cos",
    "doy_sin",
    "doy_cos",
    "latitude",
    "longitude",
]

# Physical and semantic metadata for Explainable AI (XAI) feature interpretation
FEATURE_XAI_CONFIG: Dict[str, Dict[str, str]] = {
    "PRECTOTCORR": {
        "display_name": "Immediate Antecedent Rain (D-1)",
        "category": "antecedent_rainfall",
        "desc_pos": "Recent heavy rain primed catchment surface wetness and saturated topsoil.",
        "desc_neg": "Dry immediate antecedent conditions allow soil infiltration buffer.",
    },
    "T2M": {
        "display_name": "2m Air Temperature",
        "category": "temperature_wind",
        "desc_pos": "High surface thermal energy fuels buoyant convective updrafts.",
        "desc_neg": "Cooler surface temperatures restrict vertical cloud development.",
    },
    "T2MDEW": {
        "display_name": "Dew Point Temperature",
        "category": "moisture",
        "desc_pos": "Elevated dew point confirms abundant moisture content in boundary layer.",
        "desc_neg": "Low dew point indicates dry air requiring extensive cooling to condense.",
    },
    "RH2M": {
        "display_name": "Relative Humidity (2m)",
        "category": "moisture",
        "desc_pos": "Near-saturated relative humidity lowers condensation height, triggering cloudbursts.",
        "desc_neg": "Moderate/low relative humidity facilitates evaporation of descending precipitation.",
    },
    "PS": {
        "display_name": "Surface Barometric Pressure",
        "category": "instability_pressure",
        "desc_pos": "Low atmospheric surface pressure signifies cyclonic depression convergence.",
        "desc_neg": "Higher barometric pressure acts as a stabilizing anticyclonic ridge.",
    },
    "WS2M": {
        "display_name": "Surface Wind Speed (2m)",
        "category": "temperature_wind",
        "desc_pos": "Low-level wind flow provides steady moisture advection into convective cells.",
        "desc_neg": "Stagnant low-level wind limits convergence line development.",
    },
    "WS10M": {
        "display_name": "10m Wind Speed & Shear",
        "category": "temperature_wind",
        "desc_pos": "Sustained wind shear helps organize multicellular squall lines.",
        "desc_neg": "Weak wind shear prevents sustained storm cell regeneration.",
    },
    "ALLSKY_SFC_SW_DWN": {
        "display_name": "Solar Downward Flux",
        "category": "instability_pressure",
        "desc_pos": "Strong solar insolation intensifies daytime differential heating and instability.",
        "desc_neg": "Overcast radiative shielding reduces diurnal thermal lifting.",
    },
    "rain_lag_1d": {
        "display_name": "1-Day Prior Rainfall",
        "category": "antecedent_rainfall",
        "desc_pos": "Heavy rainfall 24h prior leaves soil near field capacity.",
        "desc_neg": "Zero rainfall 24h prior provides maximum ground absorption capacity.",
    },
    "rain_sum_prev_3d": {
        "display_name": "3-Day Cumulative Rainfall",
        "category": "antecedent_rainfall",
        "desc_pos": "Sustained 3-day precipitation has filled soil pore space, causing immediate runoff.",
        "desc_neg": "Low 3-day rainfall retains dry hydrological retention reservoirs.",
    },
    "rain_sum_prev_7d": {
        "display_name": "7-Day Cumulative Rainfall",
        "category": "antecedent_rainfall",
        "desc_pos": "Prolonged multi-day wet spell elevates regional water table to near-overflow.",
        "desc_neg": "Low 7-day cumulative total provides strong catchment storage headroom.",
    },
    "rain_sum_prev_14d": {
        "display_name": "14-Day Cumulative Rainfall",
        "category": "antecedent_rainfall",
        "desc_pos": "Bi-weekly cumulative rainfall indicates saturated catchment baselines.",
        "desc_neg": "Dry bi-weekly antecedent period cushions new rainfall impact.",
    },
    "rain_sum_prev_30d": {
        "display_name": "30-Day Cumulative Rainfall",
        "category": "antecedent_rainfall",
        "desc_pos": "Monthly high-volume rainfall maintains high baseline river discharge.",
        "desc_neg": "Low 30-day baseline leaves regional channels at low water levels.",
    },
    "rain_mean_prev_7d": {
        "display_name": "7-Day Mean Rainfall Intensity",
        "category": "antecedent_rainfall",
        "desc_pos": "Consistent daily rainfall persistence reinforces flood risk.",
        "desc_neg": "Infrequent daily rain events allow intermittent ground drainage.",
    },
    "rain_max_prev_7d": {
        "display_name": "7-Day Peak 24h Rainfall Event",
        "category": "antecedent_rainfall",
        "desc_pos": "Recent peak downpour damaged natural retention and accelerated runoff.",
        "desc_neg": "Absence of recent severe peak rainfall stabilizes catchment banks.",
    },
    "pressure_change_1d": {
        "display_name": "24h Barometric Pressure Delta",
        "category": "instability_pressure",
        "desc_pos": "Rapid barometric pressure drop signals an advancing cyclonic low or frontal boundary.",
        "desc_neg": "Rising barometric pressure indicates stabilizing tropospheric conditions.",
    },
    "humidity_change_1d": {
        "display_name": "24h Relative Humidity Surge",
        "category": "moisture",
        "desc_pos": "Sudden moisture surge indicates active atmospheric river or maritime tongue.",
        "desc_neg": "Drying trend prevents formation of deep saturated clouds.",
    },
    "temperature_change_1d": {
        "display_name": "24h Temperature Delta",
        "category": "temperature_wind",
        "desc_pos": "Surface warming increases convective available potential energy.",
        "desc_neg": "Cooling boundary layer stabilizes vertical lapse rate.",
    },
    "wind_change_1d": {
        "display_name": "24h Wind Speed Delta",
        "category": "temperature_wind",
        "desc_pos": "Accelerating winds indicate tightening pressure gradients and storm inflow.",
        "desc_neg": "Decelerating winds point to dissipating surface convergence.",
    },
    "month_sin": {
        "display_name": "Monsoon Seasonal Timing (Sin)",
        "category": "climatology",
        "desc_pos": "Date aligns with peak synoptic monsoon storm track climatology.",
        "desc_neg": "Outside peak monsoon active depression frequency periods.",
    },
    "month_cos": {
        "display_name": "Annual Seasonal Cycle (Cos)",
        "category": "climatology",
        "desc_pos": "Climatological alignment with regional high-precipitation regime.",
        "desc_neg": "Climatological alignment with regional dry or transition season.",
    },
    "doy_sin": {
        "display_name": "Day-of-Year Synoptic Cycle (Sin)",
        "category": "climatology",
        "desc_pos": "Astronomical solar heating cycle favors strong summer convection.",
        "desc_neg": "Reduced solar insolation geometry limits convective heating.",
    },
    "doy_cos": {
        "display_name": "Day-of-Year Synoptic Cycle (Cos)",
        "category": "climatology",
        "desc_pos": "Climatological seasonal inflection favors active storm belts.",
        "desc_neg": "Climatological seasonal phase favors quiescent weather.",
    },
    "latitude": {
        "display_name": "Geographic Latitude",
        "category": "climatology",
        "desc_pos": "Latitude intersects high-frequency monsoonal depression tracks.",
        "desc_neg": "Latitude situated in drier or leeward rain-shadow climatological zone.",
    },
    "longitude": {
        "display_name": "Geographic Longitude",
        "category": "climatology",
        "desc_pos": "Proximity to maritime moisture pathways enhances vapor flux.",
        "desc_neg": "Continental interior positioning reduces maritime vapor flux.",
    },
}


class Model1Service(BaseService):
    """
    Real XGBoost Next-Day Heavy Rainfall Classifier Inference Service.
    - Loads native best_heavy_rain_xgboost_v2.json
    - Preserves 37 ordered features
    - Applies frozen validation-selected decision threshold: 0.81
    - Thread-safe singleton model caching
    """

    _instance: Optional["Model1Service"] = None
    _lock: threading.Lock = threading.Lock()
    _booster: Optional[xgb.Booster] = None
    _loaded_path: Optional[Path] = None

    def __init__(self, model_path: Optional[str] = None):
        super().__init__(
            name="Model1Service",
            description="XGBoost next-day heavy rainfall prediction classifier",
        )
        self.settings = get_settings()
        self.model_path = Path(model_path or self.settings.MODEL1_PATH)
        self.threshold = self.settings.MODEL1_THRESHOLD

    @classmethod
    def get_instance(cls, model_path: Optional[str] = None) -> "Model1Service":
        """Get or initialize singleton service instance."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls(model_path=model_path)
            return cls._instance

    @property
    def is_loaded(self) -> bool:
        """Check if model booster is actively loaded in memory."""
        return self.__class__._booster is not None

    @property
    def is_connected(self) -> bool:
        """Service is connected when model is loaded and ready for inference."""
        return self.is_loaded

    def check_connection(self) -> bool:
        """Verify model readiness."""
        return self.is_loaded

    def resolve_model_file(self) -> Path:
        """Resolve actual model file on disk or raise FileNotFoundError."""
        resolved = self.model_path if self.model_path.is_absolute() else (Path.cwd() / self.model_path)
        if resolved.is_file():
            return resolved

        # Check relative to repository root
        repo_root = Path(__file__).resolve().parents[3]
        for candidate in [
            repo_root / "models" / self.model_path.name,
            repo_root / self.model_path.name,
            repo_root / self.model_path,
        ]:
            if candidate.is_file():
                return candidate

        raise FileNotFoundError(f"Model 1 file not found at '{self.model_path}' or in '{repo_root / 'models'}'")

    def has_model_artifact(self) -> bool:
        """Check if model file exists on disk without loading."""
        try:
            self.resolve_model_file()
            return True
        except FileNotFoundError:
            return False

    def load(self, force_reload: bool = False) -> None:
        """
        Load XGBoost booster from configured model file.
        Thread-safe; avoids reloading if already loaded unless force_reload=True.
        """
        with self.__class__._lock:
            if self.__class__._booster is not None and not force_reload:
                return

            try:
                resolved_file = self.resolve_model_file()
                logger.info("Loading Model 1 (XGBoost) from: %s", resolved_file)
                bst = xgb.Booster()
                bst.load_model(str(resolved_file))

                # Verify feature consistency if available in booster
                if bst.feature_names and len(bst.feature_names) != len(MODEL1_FEATURE_ORDER):
                    raise ValueError(
                        f"Expected {len(MODEL1_FEATURE_ORDER)} features in model, got {len(bst.feature_names)}"
                    )

                self.__class__._booster = bst
                self.__class__._loaded_path = resolved_file
                self._is_connected = True
                logger.info("Model 1 successfully loaded with %d features", len(MODEL1_FEATURE_ORDER))
            except Exception as exc:
                self.__class__._booster = None
                self._is_connected = False
                self._last_error = str(exc)
                logger.error("Failed to load Model 1: %s", exc)
                raise

    def get_health_detail(self) -> Dict[str, Any]:
        """Return detailed health state for /api/v1/models/health."""
        return {
            "loaded": self.is_loaded,
            "path_configured": self.has_model_artifact(),
            "model_type": "xgboost",
            "checkpoint_path": str(self.__class__._loaded_path or self.model_path),
            "threshold": self.threshold,
            "device": "cpu",
            "details": {
                "feature_count": len(MODEL1_FEATURE_ORDER),
                "last_error": self._last_error,
            },
        }

    def predict(
        self, features: WeatherFeatureVector, location: Optional[Coordinates] = None
    ) -> RainfallPredictionResponse:
        """
        Execute real inference using loaded XGBoost model.
        Features are strictly extracted in MODEL1_FEATURE_ORDER.
        """
        if not self.is_loaded:
            try:
                self.load()
            except Exception as err:
                raise ModelNotLoadedError(
                    model_name="heavy_rainfall_xgboost_v2",
                    path=str(self.model_path),
                    details={"error": str(err)},
                )

        bst = self.__class__._booster
        if bst is None:
            raise ModelNotLoadedError(
                model_name="heavy_rainfall_xgboost_v2",
                path=str(self.model_path),
            )

        # Build feature array in exact order
        feature_dict = features.model_dump()
        ordered_values: List[float] = []
        for name in MODEL1_FEATURE_ORDER:
            if name not in feature_dict or feature_dict[name] is None:
                raise ValueError(f"Missing required meteorological feature: '{name}'")
            ordered_values.append(float(feature_dict[name]))

        data_matrix = np.array([ordered_values], dtype=np.float32)
        dmatrix = xgb.DMatrix(data_matrix, feature_names=MODEL1_FEATURE_ORDER)

        raw_pred = bst.predict(dmatrix)
        prob = float(raw_pred[0])
        prob = max(0.0, min(1.0, prob))  # Ensure valid range

        # Compute exact Tree SHAP values
        raw_contribs = bst.predict(dmatrix, pred_contribs=True)
        xai_summary = self._build_xai_summary(
            contribs=raw_contribs[0],
            ordered_values=ordered_values,
            probability=prob,
            threshold=self.threshold,
        )

        is_heavy = prob >= self.threshold

        return RainfallPredictionResponse(
            model="heavy_rainfall_xgboost_v2",
            probability=round(prob, 4),
            threshold=self.threshold,
            heavy_rain=is_heavy,
            prediction="heavy_rain" if is_heavy else "no_heavy_rain",
            feature_count=len(MODEL1_FEATURE_ORDER),
            xai=xai_summary,
            metadata={
                "frozen_threshold": self.threshold,
                "input_latitude": features.latitude,
                "input_longitude": features.longitude,
                "base_margin": xai_summary.base_margin,
            },
        )

    @classmethod
    def _build_xai_summary(
        cls,
        contribs: np.ndarray,
        ordered_values: List[float],
        probability: float,
        threshold: float,
    ) -> RainfallXaiSummary:
        """Construct structured Explainable AI breakdown from raw Tree SHAP outputs."""
        feature_shap = contribs[:-1]
        base_margin = float(contribs[-1])
        model_margin = float(np.sum(contribs))

        abs_sum = float(np.sum(np.abs(feature_shap)))
        if abs_sum <= 1e-6:
            abs_sum = 1.0

        all_contributions: List[FeatureShapContribution] = []
        for idx, feat_name in enumerate(MODEL1_FEATURE_ORDER):
            s_val = float(feature_shap[idx])
            obs_val = float(ordered_values[idx])
            pct = round((abs(s_val) / abs_sum) * 100.0, 1)

            cfg = FEATURE_XAI_CONFIG.get(feat_name, {})
            disp_name = cfg.get("display_name", feat_name)
            category = cfg.get("category", "meteorology")

            if s_val > 0.005:
                impact = "increases_risk"
                desc = cfg.get("desc_pos", f"{disp_name} pushed rainfall risk higher.")
            elif s_val < -0.005:
                impact = "decreases_risk"
                desc = cfg.get("desc_neg", f"{disp_name} suppressed rainfall probability.")
            else:
                impact = "neutral"
                desc = f"{disp_name} had neutral impact on this forecast."

            all_contributions.append(
                FeatureShapContribution(
                    feature_name=feat_name,
                    display_name=disp_name,
                    category=category,
                    observed_value=round(obs_val, 2),
                    shap_value=round(s_val, 4),
                    impact=impact,
                    percentage_contribution=pct,
                    description=desc,
                )
            )

        # Sort all by absolute SHAP impact
        all_contributions.sort(key=lambda c: abs(c.shap_value), reverse=True)

        # Extract top positive (risk-raising) and top negative (risk-lowering)
        top_pos = [c for c in all_contributions if c.shap_value > 0.005][:5]
        top_neg = [c for c in all_contributions if c.shap_value < -0.005][:5]

        # Natural language synthesis narrative
        pos_names = [f"{c.display_name} (+{c.percentage_contribution}%)" for c in top_pos[:3]]
        neg_names = [f"{c.display_name} (-{c.percentage_contribution}%)" for c in top_neg[:2]]

        if probability >= threshold:
            drivers_str = ", ".join(pos_names) if pos_names else "strong moisture flux"
            narrative = (
                f"Model 1 classifies this event as HEAVY RAINFALL with {probability*100:.1f}% probability "
                f"(exceeding the {threshold*100:.0f}% threshold). Key meteorological drivers raising risk: "
                f"{drivers_str}. Tropospheric moisture convergence and antecedent catchment wetness "
                f"substantially elevate severe downpour and flood potential."
            )
        else:
            suppressors_str = ", ".join(neg_names) if neg_names else "stable atmospheric conditions"
            narrative = (
                f"Model 1 predicts a rainfall probability of {probability*100:.1f}% "
                f"(below the {threshold*100:.0f}% heavy rain threshold). Suppressing factors include: "
                f"{suppressors_str}. Stable boundary layer dynamics and lack of cyclonic forcing inhibit deep convective cloudbursts."
            )

        rh_idx = MODEL1_FEATURE_ORDER.index("RH2M")
        dew_idx = MODEL1_FEATURE_ORDER.index("T2MDEW")
        ps_idx = MODEL1_FEATURE_ORDER.index("PS")
        dp_idx = MODEL1_FEATURE_ORDER.index("pressure_change_1d")
        r3_idx = MODEL1_FEATURE_ORDER.index("rain_sum_prev_3d")
        r7_idx = MODEL1_FEATURE_ORDER.index("rain_sum_prev_7d")

        causality = [
            f"1. Atmospheric Moisture: 2m Relative Humidity is {ordered_values[rh_idx]:.1f}% with dew point at {ordered_values[dew_idx]:.1f}°C.",
            f"2. Barometric & Synoptic Forcing: Surface pressure is {ordered_values[ps_idx]:.1f} kPa with 24h delta of {ordered_values[dp_idx]:.2f} kPa.",
            f"3. Catchment Antecedent State: Preceding 3-day rainfall sum is {ordered_values[r3_idx]:.1f} mm and 7-day cumulative total is {ordered_values[r7_idx]:.1f} mm.",
            f"4. Model Inference Outcome: 37-feature Tree SHAP margin produces {probability*100:.1f}% heavy rain probability (threshold: {threshold*100:.0f}%).",
        ]

        return RainfallXaiSummary(
            base_margin=round(base_margin, 4),
            model_score_margin=round(model_margin, 4),
            top_positive_drivers=top_pos,
            top_negative_drivers=top_neg,
            all_contributions=all_contributions,
            narrative=narrative,
            causality_chain=causality,
        )

    def predict_heavy_rainfall(self, features: WeatherFeatureVector) -> RainfallPrediction:
        """Domain adapter method fulfilling original service interface."""
        res = self.predict(features)
        return RainfallPrediction(
            target_date=datetime.now().strftime("%Y-%m-%d"),
            coordinates=Coordinates(latitude=features.latitude, longitude=features.longitude),
            heavy_rain_probability=res.probability,
            is_heavy_rain=res.heavy_rain,
            decision_threshold=res.threshold,
            model_version=res.model,
            confidence=abs(res.probability - 0.5) * 2,
        )
