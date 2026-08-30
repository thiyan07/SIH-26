"""Phase 7: weather-risk heuristics are deterministic, evidence-only flags."""
from __future__ import annotations

from app.engines.weather import weather_risk_factors


def _rec(indicator, value):
    return {"indicator": indicator, "value": value}


def test_heat_stress_high():
    out = weather_risk_factors([_rec("forecast_temperature_max", 43.0)])
    assert out["risk_delta"] >= 15
    heat = next(f for f in out["factors"] if f["factor"] == "heat_stress")
    assert heat["level"] == "high"
    assert "43.0C" in heat["note"]


def test_heat_stress_buckets():
    assert next(f["level"] for f in weather_risk_factors([_rec("temperature", 39.5)])["factors"]
                if f["factor"] == "heat_stress") == "medium"
    assert next(f["level"] for f in weather_risk_factors([_rec("current_temperature", 36.0)])["factors"]
                if f["factor"] == "heat_stress") == "low"
    # benign temperature -> no factor at all
    assert weather_risk_factors([_rec("temperature", 30.0)])["factors"] is None


def test_drought_flag_from_annual_rainfall():
    out = weather_risk_factors([_rec("rainfall", 320.0)])
    drought = next(f for f in out["factors"] if f["factor"] == "drought")
    assert drought["level"] == "high"
    assert "320mm" in drought["note"]


def test_flood_flag_from_daily_precipitation():
    out = weather_risk_factors([_rec("forecast_precipitation_sum", 150.0)])
    assert any(f["factor"] == "flood_risk" for f in out["factors"])


def test_multiple_flags_sum_but_cap_at_25():
    out = weather_risk_factors([
        _rec("forecast_temperature_max", 44.0),
        _rec("rainfall", 300.0),
        _rec("forecast_precipitation_sum", 180.0),
    ])
    assert out["risk_delta"] == 25  # 15 + 8 + 8 capped
    assert len(out["factors"]) == 3


def test_no_risk_when_empty_and_values_ignored_if_invalid():
    assert weather_risk_factors([])["factors"] is None
    assert weather_risk_factors([_rec("rainfall", "n/a")])["factors"] is None


def test_each_factor_reports_own_contribution():
    out = weather_risk_factors([_rec("forecast_temperature_max", 41.0)])
    (heat,) = out["factors"]
    assert heat["risk_delta"] == 15
    assert out["risk_delta"] == 15
