"""Profit model simulator tests (plan §18/§24): every known category must run.

Regression guard: `simulate_model` previously invoked every model's `fn`
with a single argument while `_generic(inputs, defaults)` required the
defaults, raising TypeError for all generic categories (textile,
food_processing, restaurant, agriculture, manufacturing, handicrafts, other,
poultry). All `fn` functions now share the `(inputs, defaults=None)`
contract.
"""
from __future__ import annotations

import pytest

from app.engines.profit import known_categories, model_inputs_schema, simulate_model


@pytest.mark.parametrize("code", [c["code"] for c in known_categories()])
def test_every_category_simulates(code):
    res = simulate_model(code)
    assert res.category_code == code
    # profit may be negative for default demo models (e.g. high-risk dairy)
    assert isinstance(res.outputs["estimated_monthly_operating_profit"], float)
    assert res.outputs["monthly_revenue"] > 0
    assert "cost_breakdown" in res.outputs
    assert res.is_estimate is True


def test_generic_uses_defaults_and_merges_inputs():
    res = simulate_model("textile")
    # default revenue 35000 - default operating cost 18000
    assert res.outputs["monthly_revenue"] == pytest.approx(35000.0)
    assert res.outputs["monthly_operating_cost"] == pytest.approx(18000.0)
    assert res.outputs["estimated_monthly_operating_profit"] == pytest.approx(17000.0)

    res2 = simulate_model("textile", {"monthly_revenue": 50000.0})
    assert res2.inputs["monthly_revenue"] == pytest.approx(50000.0)
    assert res2.inputs["monthly_operating_cost"] == pytest.approx(18000.0)
    assert res2.outputs["estimated_monthly_operating_profit"] == pytest.approx(32000.0)


def test_dairy_specific_model_still_works():
    res = simulate_model("dairy", {"number_of_animals": 3.0})
    assert res.outputs["daily_revenue"] > 0
    assert res.inputs["number_of_animals"] == pytest.approx(3.0)
    assert "veterinary" in res.outputs["cost_breakdown"]


def test_grocery_model_still_works():
    res = simulate_model("grocery")
    assert res.outputs["monthly_revenue"] == pytest.approx(60000.0)
    assert res.outputs["estimated_monthly_operating_profit"] == pytest.approx(
        60000.0 * 0.12 - (3000 + 5000 + 1000 + 2000)
    )


def test_input_schema_matches_known_categories():
    for c in known_categories():
        schema = model_inputs_schema(c["code"])
        assert schema["inputs_schema"]
        assert schema["defaults"]


def test_unknown_category_rejected():
    with pytest.raises(ValueError):
        simulate_model("not_a_category")
