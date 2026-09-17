"""Unit tests for Model 1 Tree SHAP Explainable AI (XAI) feature attribution."""

import pytest
from backend.app.schemas.weather import WeatherFeatureVector
from backend.app.services.model1_service import Model1Service, MODEL1_FEATURE_ORDER


def test_model1_shap_xai_attribution():
    """Verify Model 1 generates mathematically sound SHAP feature attributions."""
    m1 = Model1Service.get_instance()

    # Create synthetic feature vector
    raw_dict = {feat: 0.0 for feat in MODEL1_FEATURE_ORDER}
    raw_dict["RH2M"] = 92.5
    raw_dict["T2M"] = 28.4
    raw_dict["T2MDEW"] = 26.8
    raw_dict["PS"] = 98.2
    raw_dict["pressure_change_1d"] = -0.65
    raw_dict["rain_lag_1d"] = 45.0
    raw_dict["rain_sum_prev_3d"] = 110.0
    raw_dict["rain_sum_prev_7d"] = 180.0
    raw_dict["month"] = 7.0
    raw_dict["latitude"] = 26.85
    raw_dict["longitude"] = 80.95

    vec = WeatherFeatureVector(**raw_dict)
    res = m1.predict(vec)

    assert res.xai is not None
    xai = res.xai
    assert len(xai.all_contributions) == 37
    assert len(xai.top_positive_drivers) > 0
    assert len(xai.causality_chain) == 4
    assert len(xai.narrative) > 20

    # Ensure percentage contributions sum close to 100%
    pct_sum = sum(c.percentage_contribution for c in xai.all_contributions)
    assert 95.0 <= pct_sum <= 105.0

    # Verify key driver attributes
    top = xai.all_contributions[0]
    assert top.feature_name in MODEL1_FEATURE_ORDER
    assert top.display_name != ""
    assert top.category in ["moisture", "instability_pressure", "antecedent_rainfall", "temperature_wind", "climatology"]
    assert top.impact in ["increases_risk", "decreases_risk", "neutral"]
