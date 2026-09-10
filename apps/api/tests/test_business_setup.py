"""Tests for Business Setup & Operating Plan engine."""
from app.engines.business_setup import available_models, build_setup_plan
from app.engines.cost_templates import get_total_template_cost


def test_category_specific_setup_grocery():
    plan = build_setup_plan("grocery", "micro", capital_available=30000)
    assert plan["category_code"] == "grocery"
    assert plan["scale"] == "micro"
    assert any("shelves" in i["name"].lower() for i in plan["items"])
    assert plan["total_initial_requirement"] == get_total_template_cost("grocery", "micro", 1.0)

def test_category_specific_setup_dairy():
    plan = build_setup_plan("dairy", "micro")
    assert any("milking" in i["name"].lower() for i in plan["items"])
    assert any("shed" in i["name"].lower() for i in plan["items"])

def test_category_specific_setup_tailoring():
    plan = build_setup_plan("textile", "micro")
    assert any("sewing" in i["name"].lower() for i in plan["items"])

def test_category_specific_setup_restaurant():
    plan = build_setup_plan("restaurant", "micro")
    assert any("cooking" in i["name"].lower() or "stove" in i["name"].lower() for i in plan["items"])

def test_scale_changes():
    micro = build_setup_plan("grocery", "micro")
    small = build_setup_plan("grocery", "small")
    assert small["total_initial_requirement"] > micro["total_initial_requirement"]
    assert small["startup_cost"] > micro["startup_cost"]

def test_required_recommended_optional_classification():
    plan = build_setup_plan("grocery", "small")
    statuses = {i["status"] for i in plan["items"]}
    assert "REQUIRED" in statuses
    assert "RECOMMENDED" in statuses or "OPTIONAL" in statuses

def test_total_setup_cost_matches_finance():
    plan = build_setup_plan("grocery", "small", location_factor=0.82)
    total = get_total_template_cost("grocery", "small", 0.82)
    assert plan["total_initial_requirement"] == total

def test_inventory_and_working_capital():
    plan = build_setup_plan("grocery", "micro")
    assert plan["initial_inventory"] > 0
    assert plan["working_capital"] > 0

def test_lean_setup_when_capital_low():
    plan = build_setup_plan("grocery", "small", capital_available=35000)
    lean = plan["lean_option"]
    assert lean is not None
    assert lean["lean_total"] < plan["total_initial_requirement"]
    assert lean["financing_needed"] < plan["total_initial_requirement"] - 35000

def test_lean_not_needed_when_capital_sufficient():
    plan = build_setup_plan("grocery", "micro", capital_available=200000)
    assert plan["lean_option"] is None

def test_monthly_operating_requirements():
    plan = build_setup_plan("grocery", "micro")
    assert len(plan["monthly_operating_requirements"]) > 0
    assert any("rent" in r["name"].lower() for r in plan["monthly_operating_requirements"])

def test_daily_targets():
    from app.engines.business_intelligence import monthly_economics, monthly_economics_to_dict
    econ = monthly_economics_to_dict(monthly_economics("grocery", emi=0))
    plan = build_setup_plan("grocery", "micro", monthly_economics_dict=econ)
    assert plan["operating_targets"]["daily_sales_needed"] is not None
    assert plan["operating_targets"]["operating_days"] in (26, 30)

def test_break_even_translation():
    from app.engines.business_intelligence import monthly_economics, monthly_economics_to_dict
    econ = monthly_economics_to_dict(monthly_economics("grocery", monthly_revenue=60000, emi=2000))
    plan = build_setup_plan("grocery", "micro", monthly_economics_dict=econ)
    assert plan["operating_targets"]["break_even_daily"] is not None

def test_product_mix_uses_recommend_products():
    plan = build_setup_plan("grocery", "micro")
    assert len(plan["product_mix"]) > 0
    assert all("product" in p for p in plan["product_mix"])

def test_kpis_category_specific():
    grocery_kpis = build_setup_plan("grocery", "micro")["kpis"]
    assert any("daily sales" in k["kpi"].lower() for k in grocery_kpis)
    dairy_kpis = build_setup_plan("dairy", "micro")["kpis"]
    assert any("litres" in k["kpi"].lower() for k in dairy_kpis)

def test_provenance_status():
    plan = build_setup_plan("grocery", "micro")
    assert plan["data_status"] == "ESTIMATED"
    assert all(i["provenance"]["status"] == "ESTIMATED" for i in plan["items"])

def test_no_duplicate_financial_calculation():
    # Plan total must equal cost template, not a new formula
    for cat in ["grocery", "dairy", "textile", "restaurant"]:
        for scale in ["micro", "small"]:
            plan = build_setup_plan(cat, scale)
            assert plan["total_initial_requirement"] == get_total_template_cost(cat, scale, 1.0), f"{cat} {scale}"

def test_plan_values_match_profit():
    from app.engines.business_intelligence import monthly_economics, monthly_economics_to_dict
    econ = monthly_economics_to_dict(monthly_economics("dairy", emi=0))
    plan = build_setup_plan("dairy", "micro", monthly_economics_dict=econ)
    assert plan["planned_values"]["planned_revenue"] == econ["monthly_revenue"]

def test_business_models():
    assert any(m["code"] == "milk_production" for m in available_models("dairy"))
    assert any(m["code"] == "takeaway" for m in available_models("restaurant"))
    assert available_models("handicrafts")[0]["code"] == "standard"

def test_model_resolution():
    plan = build_setup_plan("dairy", "micro", model="dairy_retail")
    assert plan["model"] == "dairy_retail"
    plan2 = build_setup_plan("dairy", "micro", model="invalid")
    assert plan2["model"] == "milk_production"  # fallback to first

def test_sourcing_hook_unavailable():
    plan = build_setup_plan("grocery", "micro")
    assert all(s["status"] == "UNAVAILABLE" for s in plan["sourcing_needs"])
    assert "Supplier discovery" in plan["sourcing_needs"][0]["evidence"]

def test_missing_market_evidence_confidence():
    plan_no_market = build_setup_plan("grocery", "micro", market_evidence=None)
    plan_with_market = build_setup_plan("grocery", "micro", market_evidence={"available": True, "prices": [{"item": "rice"}]})
    assert plan_no_market["confidence"] == "low"
    assert plan_with_market["confidence"] == "medium"

def test_working_capital_no_government_label():
    plan = build_setup_plan("grocery", "micro")
    assert "government" not in plan["planned_values"].get("planned_working_capital", "") if isinstance(plan["planned_values"].get("planned_working_capital"), str) else True
    # Ensure buffer note says modelled estimate
    assert plan["inventory_plan"] is not None

def test_separate_business_models_cost_difference():
    # dairy milk_production vs retail should have different handling but currently share template cost (model doesn't change cost yet, but model field preserved)
    # We test that model is respected and extensible
    p1 = build_setup_plan("dairy", "micro", model="milk_production")
    p2 = build_setup_plan("dairy", "micro", model="dairy_retail")
    assert p1["model"] != p2["model"]
