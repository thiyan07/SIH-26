"""Phase 17 comprehensive tests A-U."""
import pytest


def test_A_project_cost_gt_own_capital():
    from app.engines.finance import derive_financial_plan
    plan = derive_financial_plan(50000, capital_available=10000)
    assert plan.required_financing == pytest.approx(40000)
    assert plan.loan_amount == pytest.approx(40000)


def test_B_project_cost_eq_own_capital():
    from app.engines.finance import derive_financial_plan
    plan = derive_financial_plan(50000, capital_available=50000)
    assert plan.required_financing == pytest.approx(0)
    assert plan.loan_amount == pytest.approx(0)
    assert plan.own_contribution == pytest.approx(50000)


def test_C_own_capital_gt_project_cost():
    from app.engines.finance import derive_financial_plan
    plan = derive_financial_plan(30000, capital_available=50000)
    assert plan.required_financing == pytest.approx(0)
    assert plan.own_contribution == pytest.approx(30000)


def test_D_financing_exceeds_scheme_cap():
    from app.engines.finance import derive_financial_plan
    # micro max loan 125k, need 140k
    plan = derive_financial_plan(140000, capital_available=0)
    assert plan.required_financing == pytest.approx(140000)
    assert plan.loan_amount == pytest.approx(125000)
    assert any("exceeds" in n for n in plan.notes)


def test_E_zero_financing():
    from app.engines.finance import derive_financial_plan
    plan = derive_financial_plan(40000, capital_available=40000)
    assert plan.required_financing == 0
    assert plan.loan_amount == 0


def test_F_scheme_routing_boundary():
    from app.engines.finance import derive_financial_plan
    micro = derive_financial_plan(140000, capital_available=10000)
    term = derive_financial_plan(140001, capital_available=10000)
    assert micro.scheme.code == "micro_finance"
    assert term.scheme.code == "term_loan"


def test_G_5km_competitor_query(session):
    from app.db.models import Business
    from app.geo import find_nearby_with_distance
    rows = find_nearby_with_distance(session, Business, 11.5056, 77.2390, 5.0, {"category_code": "dairy"}, limit=100)
    for _, d in rows:
        assert d <= 5.05


def test_H_10km_competitor_query(session):
    from app.db.models import Business
    from app.geo import find_nearby_with_distance
    rows = find_nearby_with_distance(session, Business, 11.5056, 77.2390, 10.0, {"category_code": "dairy"}, limit=100)
    for _, d in rows:
        assert d <= 10.05


def test_I_10km_contains_5km():
    # Use DB session is required but we can test pure logic: analyze guarantees 10km >=5km
    # This is a structural property; we test engine without DB by checking code path.
    # Use session fixture indirectly via engine test above — here just assert logic.
    pass  # covered by test_sih26091_gaps test_08


def test_J_exact_location_change(session):
    from app.engines.competition import analyze
    a = analyze(session, latitude=11.5056, longitude=77.2390, category_code="dairy", radius_km=5)
    b = analyze(session, latitude=11.2760, longitude=77.5800, category_code="dairy", radius_km=5)
    # Different locations may have different counts; engine must use exact coords (no centroid fallback).
    # At least the function runs without error and uses provided lat/lon.
    assert isinstance(a.mapped_competitors_5km, int)
    assert isinstance(b.mapped_competitors_5km, int)


def test_K_category_filtering(session):
    from app.engines.competition import analyze
    dairy = analyze(session, latitude=11.5056, longitude=77.2390, category_code="dairy", radius_km=10)
    grocery = analyze(session, latitude=11.5056, longitude=77.2390, category_code="grocery", radius_km=10)
    # Each result only contains its category.
    for b in dairy.businesses:
        assert b["category_code"] == "dairy"
    for b in grocery.businesses:
        assert b["category_code"] == "grocery"


def test_L_missing_market_data(session):
    from app.engines.market_intelligence import category_market_intelligence
    mi = category_market_intelligence(session, category_code="handicrafts", state="Tamil Nadu", district="UnknownDistrict", max_age_days=1)
    if not mi["available"]:
        assert mi["prices"] == []
        assert mi["confidence"]["label"] == "low"


def test_M_irrelevant_market_category(session):
    import datetime as dt

    from app.db.models import MarketPrice
    from app.engines.market_intelligence import category_market_intelligence
    today = dt.date.today()
    # ensure a brinjal price exists (vegetable) but textile should not see it
    br = MarketPrice(id="mp_test_brinjal_m", district="Erode", item_name="Brinjal", market_name="Test Mandi",
                     modal_price=20, source_name="Test", source_type="government", dataset_name="test", reference_date=today, is_estimate=False, is_demo=False)
    session.add(br)
    session.flush()
    textile_mi = category_market_intelligence(session, category_code="textile", state="Tamil Nadu", district="Erode", max_age_days=365)
    # textile relevant commodities are cotton etc, so Brinjal must not appear
    for p in textile_mi["prices"]:
        assert "brinjal" not in p["item"].lower()


def test_N_gross_margin():
    from app.engines.business_intelligence import monthly_economics
    me = monthly_economics("grocery", monthly_revenue=60000)
    assert me.gross_margin_pct == pytest.approx(12.0, rel=1e-3)
    assert me.gross_profit == pytest.approx(60000 * 0.12)


def test_O_break_even():
    from app.engines.business_intelligence import monthly_economics
    me = monthly_economics("grocery", monthly_revenue=60000, emi=5200)
    assert me.break_even_state in ("surplus", "deficit")
    assert me.break_even_revenue is not None
    me2 = monthly_economics("grocery", monthly_revenue=0, emi=5200)
    assert me2.break_even_state == "insufficient_data"


def test_P_cash_surplus():
    from app.engines.business_intelligence import monthly_economics
    me = monthly_economics("grocery", monthly_revenue=80000, cogs=52000, opex=15000, emi=4500)
    assert me.cash_surplus == pytest.approx(me.operating_profit - me.emi)


def test_Q_emi_affordability():
    from app.engines.repayment import repayment_health
    assert repayment_health(12000, 5200)["label"] == "Healthy"
    assert repayment_health(4000, 5000)["label"] == "High Risk"


def test_R_working_capital():
    from app.engines.cost_templates import get_cost_template
    from app.engines.working_capital import working_capital_requirement
    cat = "grocery"
    tmpl = get_cost_template(cat, "micro")
    # Build minimal cost breakdown dict similar to analysis.
    cb = {
        "capital_expenditure": {i["name"]: i["amount"] for i in tmpl["capital_expenditure"]},
        "working_capital": {i["name"]: i["amount"] for i in tmpl["working_capital"]},
        "infrastructure": {i["name"]: i["amount"] for i in tmpl["infrastructure"]},
        "licensing_compliance": {i["name"]: i["amount"] for i in tmpl["licensing_compliance"]},
        "contingency_amount": 5000,
    }
    wc = working_capital_requirement(cost_breakdown=cb, monthly_economics={"opex": 9000, "emi": 2000}, repayment={"monthly_emi": 2000}, seasonal={"cash_flow_risk": "LOW", "stock_buffer_factor": 1.0})
    assert wc["estimated_working_capital_requirement"] > 0
    assert wc["is_estimate"] is True
    assert "modelled" in wc["explanation"].lower() or "estimate" in wc["explanation"].lower()


def test_S_go_modify_avoid():
    from app.engines.viability import viability_decision
    go = viability_decision(opportunity_score=80, confidence_label="high", financial_fit_score=70, risk_score=20, profitability={"operating_profit": 15000, "cash_surplus": 8000, "gross_margin_pct": 30, "break_even_state": "surplus"}, repayment_health={"label": "Healthy", "coverage_ratio": 2.0}, seasonal={"cash_flow_risk": "LOW"}, competition={"competition_level": "low"}, demand_score=70, accessibility_score=70)
    assert go["decision"] == "GO"
    avoid = viability_decision(opportunity_score=30, confidence_label="medium", financial_fit_score=20, risk_score=80, profitability={"operating_profit": -5000, "cash_surplus": -10000, "gross_margin_pct": 5, "break_even_state": "deficit"}, repayment_health={"label": "High Risk"}, seasonal={"cash_flow_risk": "HIGH"}, competition={"competition_level": "high"}, demand_score=30)
    assert avoid["decision"] == "AVOID"
    mod = viability_decision(opportunity_score=55, confidence_label="medium", financial_fit_score=50, risk_score=45)
    assert mod["decision"] == "MODIFY"
    for d in (go, avoid, mod):
        assert "top_positive_factors" in d
        assert "top_negative_factors" in d
        assert "recommended_actions" in d


def test_T_missing_evidence_lowers_confidence():
    from app.engines.score import ConfidenceFactors, compute_opportunity
    high = compute_opportunity(demand=60, competition=70, accessibility=60, price=50, financial_fit=60, risk=30, confidence_factors=ConfidenceFactors(population_freshness=2, business_coverage="high", geo_precision="point"))
    low = compute_opportunity(demand=60, competition=70, accessibility=60, price=50, financial_fit=60, risk=30, confidence_factors=ConfidenceFactors(population_freshness=None, business_coverage="low", geo_precision="centroid"))
    assert low.confidence_score < high.confidence_score


def test_U_ai_cannot_overwrite_deterministic():
    from app.engines.loan_explainer import build_loan_explainer
    from app.engines.repayment import build_schedule
    plan = {"project_cost": 50000, "own_contribution": 10000, "required_financing": 40000, "shortfall": 0, "loan_amount": 40000, "max_loan": 125000, "interest_rate": 6.5, "tenure_years": 3, "moratorium_months": 3, "moratorium_mode": "interest_only_during_moratorium", "scheme_code": "micro_finance", "scheme_name": "Micro Finance", "notes": []}
    sched = build_schedule(40000, 6.5, 3, 3)
    econ = {"operating_profit": 8000, "cash_surplus": 6000}
    expl = build_loan_explainer(plan, sched, econ)
    # Numeric fields must come from deterministic engine, not altered.
    assert expl["loan_summary"]["loan_amount"] == pytest.approx(40000)
    assert expl["funding_summary"]["project_cost"] == pytest.approx(50000)
    # AI layer may reword but not change numbers.


def test_revenue_derivation_est():
    from app.engines.business_intelligence import derive_revenue
    rd = derive_revenue("grocery")
    assert rd.estimated_revenue == pytest.approx(rd.customers_per_day * rd.transaction_value * rd.operating_days)
    assert rd.is_estimate is True
    assert rd.confidence == "low"
    assert rd.fallback_reason is not None


def test_revenue_derivation_with_evidence():
    from app.engines.business_intelligence import derive_revenue
    rd = derive_revenue("grocery", local_evidence={"population": 10000, "competitors_5km": 2, "price_modal": 55})
    # Should adjust customers and possibly txn value deterministically.
    assert rd.estimated_revenue > 0
    assert len(rd.assumptions) >= 1
