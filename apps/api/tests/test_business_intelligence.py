"""Tests for the business-intelligence engines (weather sensitivity, monthly
economics, seasonal intelligence, product recommendations)."""
import pytest

from app.engines.business_intelligence import (
    apply_weather_risk,
    monthly_economics,
    recommend_products,
    seasonal_intelligence,
    weather_applicable,
    weather_sensitivity,
)


# ---------------------------------------------------------------------------
# Monthly economics — the canonical deterministic cash-flow chain
# ---------------------------------------------------------------------------
def test_monthly_economics_spec_case():
    """revenue 80000 / COGS 52000 / opex 15000 / EMI 4500
    -> GP 28000 / margin 35% / operating profit 13000 / cash surplus 8500."""
    e = monthly_economics(
        "grocery",
        monthly_revenue=80000,
        cogs=52000,
        opex=15000,
        emi=4500,
    )
    assert e.gross_profit == pytest.approx(28000)
    assert e.gross_margin_pct == pytest.approx(35.0)
    assert e.operating_profit == pytest.approx(13000)
    assert e.cash_surplus == pytest.approx(8500)
    assert e.break_even_state == "surplus"
    assert e.is_estimate is True


def test_monthly_economics_zero_revenue_no_div_by_zero():
    e = monthly_economics("grocery", monthly_revenue=0, cogs=0, opex=5000, emi=2000)
    assert e.monthly_revenue == 0
    assert e.gross_profit == 0
    assert e.gross_margin_pct == 0.0
    assert e.operating_profit == pytest.approx(-5000)
    assert e.cash_surplus == pytest.approx(-7000)
    assert e.break_even_revenue is None
    assert e.break_even_state == "insufficient_data"


def test_monthly_economics_cogs_pct():
    e = monthly_economics("grocery", monthly_revenue=100000, cogs_pct=70, opex=10000, emi=0)
    assert e.cogs == pytest.approx(70000)
    assert e.gross_margin_pct == pytest.approx(30.0)
    assert e.operating_profit == pytest.approx(20000)


def test_monthly_economics_deficit_when_emi_exceeds_profit():
    e = monthly_economics("grocery", monthly_revenue=50000, cogs=48000, opex=3000, emi=5000)
    assert e.operating_profit == pytest.approx(-1000)
    assert e.cash_surplus == pytest.approx(-6000)
    assert e.break_even_state == "deficit"


# ---------------------------------------------------------------------------
# Weather / climate sensitivity
# ---------------------------------------------------------------------------
def test_weather_sensitivity_mapping():
    assert weather_sensitivity("agriculture")["sensitivity"] == "VERY HIGH"
    assert weather_sensitivity("dairy")["sensitivity"] == "HIGH"
    assert weather_sensitivity("mobile_shop")["sensitivity"] == "LOW"
    # Unknown categories fall back safely
    assert weather_sensitivity("does_not_exist")["sensitivity"] == "LOW"
    assert weather_sensitivity("unknown")["relevant"] is False


def test_weather_applicable_gates_categories():
    assert weather_applicable("agriculture") is True
    assert weather_applicable("dairy") is True
    assert weather_applicable("grocery") is False
    assert weather_applicable("mobile_shop") is False


def test_apply_weather_risk_suppresses_for_low_relevance():
    low = apply_weather_risk("mobile_shop", {"available": True, "risk": {"risk_delta": 20}})
    assert low["relevant"] is False
    assert low["risk"]["risk_delta"] == 0
    assert low["risk"]["factors"] is None
    # But the availability is still surfaced for transparency
    assert low["available"] is True


def test_apply_weather_risk_surfaces_for_high_relevance():
    risk = {"factors": [{"factor": "heat_stress"}], "risk_delta": 15}
    high = apply_weather_risk("agriculture", {"available": True, "risk": risk})
    assert high["relevant"] is True
    assert high["sensitivity"] == "VERY HIGH"
    assert high["risk"]["risk_delta"] == 15


# ---------------------------------------------------------------------------
# Seasonal intelligence
# ---------------------------------------------------------------------------
def test_seasonal_intelligence_shape_and_bounds():
    s = seasonal_intelligence("textile", month=6)
    assert len(s["curve"]) == 12
    assert all(0.5 <= x <= 1.5 for x in s["curve"])
    assert 1 <= s["current_month"] <= 12
    assert s["current_index"] == pytest.approx(s["curve"][5])
    assert s["peak_month"] in range(1, 13)
    assert s["cash_flow_risk"] in ("LOW", "MEDIUM", "HIGH")
    assert s["is_estimate"] is True
    assert isinstance(s["inventory_implication"], str)
    assert s["peak_index"] >= max(s["curve"]) - 1e-9


def test_seasonal_intelligence_stable_category_has_low_risk():
    s = seasonal_intelligence("other", month=3)
    assert s["cash_flow_risk"] == "LOW"


def test_seasonal_intelligence_clamps_month():
    assert seasonal_intelligence("grocery", month=99)["current_month"] == 12
    assert seasonal_intelligence("grocery", month=0)["current_month"] == 1


# ---------------------------------------------------------------------------
# Product recommendations
# ---------------------------------------------------------------------------
def test_recommend_products_schema():
    recs = recommend_products("grocery")
    assert recs
    for r in recs:
        assert {"product", "relevance", "reason", "confidence", "evidence"} <= set(r)
        assert r["relevance"] in ("high", "medium", "low")
        assert r["provenance"] == "ESTIMATED"
        assert r["is_estimate"] is True


def test_recommend_products_fallback_for_unknown():
    recs = recommend_products("not_a_category")
    assert recs
    assert all("is_estimate" in r for r in recs)
