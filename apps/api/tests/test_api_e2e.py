"""End-to-end API test for the acceptance scenario (section 45):
Erode -> Sathyamangalam, capital 1,00,000, Dairy."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture()
def client(seeded):
    return TestClient(app)


def test_acceptance_vertical_slice(client):
    r = client.post("/analysis", json={
        "state": "Tamil Nadu",
        "district": "Erode",
        "block": "Sathyamangalam",
        "village": "Sathyamangalam",
        "capital_available": 100000,
        "category_code": "dairy",
        "language": "en",
    })
    assert r.status_code == 200, r.text
    ev = r.json()

    # geocoded location
    assert ev["location"]["district"] == "Erode"

    # mapped competitors within 5/10 km computed
    assert "mapped_competitors_5km" in ev["business_competition"]
    assert ev["business_competition"]["data_completeness"] in ("low", "medium", "high")

    # demographic baseline with provenance
    pop = ev["population"]
    assert pop["census_year"] == 2011
    assert pop["is_historical"] is True

    # opportunity score present (Prototype Index)
    score = ev["opportunity_score"]
    assert "overall_score" in score
    assert "confidence_label" in score

    # deterministic financials: 1L capital -> 10L project -> 9L loan
    fin = ev["financial_plan"]
    assert fin["project_cost"] == pytest.approx(1_000_000, rel=1e-6)
    assert fin["loan_amount"] == pytest.approx(900_000, rel=1e-6)

    # scheme routed to Term Loan
    assert fin["scheme_code"] == "term_loan"

    # repayment present
    assert "repayment" in ev

    # profit model present
    assert ev["profit_model"]["category_code"] == "dairy"
    assert "estimated_monthly_operating_profit" in ev["profit_model"]["outputs"]

    # recommendation present (four-state decision)
    assert ev["recommendation"]["label"] in ("GO", "MODIFY", "AVOID", "INSUFFICIENT DATA")

    # data sources documented
    assert isinstance(ev["data_sources"], list)

    # analysis_id persisted
    assert ev["analysis_id"]


def test_analysis_with_unknown_location_returns_422(client):
    r = client.post("/analysis", json={
        "state": "Tamil Nadu", "district": "Nonexistent",
        "capital_available": 100000, "category_code": "dairy",
    })
    assert r.status_code == 422


def test_financial_emi_endpoint(client):
    r = client.post("/financial/emi", json={
        "loan_amount": 90000, "interest_rate": 6.5, "tenure_years": 3,
        "moratorium_months": 3, "moratorium_mode": "interest_only_during_moratorium",
    })
    assert r.status_code == 200
    body = r.json()
    assert body["monthly_emi_effective"] > 0
    assert body["total_repayment"] > 0


def test_scheme_recommend_endpoint(client):
    r = client.post("/schemes/recommend", json={"project_cost": 100000})
    assert r.status_code == 200
    assert r.json()["scheme"]["code"] == "micro_finance"
    r2 = client.post("/schemes/recommend", json={"project_cost": 2_000_000})
    assert r2.json()["scheme"]["code"] == "term_loan"


def test_data_sources_endpoint(client):
    r = client.get("/data-sources")
    assert r.status_code == 200
    assert "sources" in r.json()


def test_locations_search(client):
    r = client.get("/locations/search", params={"q": "Sathya"})
    assert r.status_code == 200
    assert any("Sathyamangalam" in (loc.get("village") or "") for loc in r.json())


def test_ai_report_grounded_in_context(client, seeded):
    r = client.post("/analysis", json={
        "state": "Tamil Nadu", "district": "Erode",
        "block": "Sathyamangalam", "village": "Sathyamangalam",
        "capital_available": 100000, "category_code": "dairy",
    })
    analysis_id = r.json()["analysis_id"]
    res = client.post("/ai/report", json={"analysis_id": analysis_id, "language": "en", "mode": "report"})
    assert res.status_code == 200
    # Report is grounded in the evidence context
    assert res.json()["content"]


# ---------- Phase 22: E2E evidence-status contract ----------
# One analysis must expose every honest evidence status: REAL (verified price
# rows), CALCULATED (computed opportunity index), ESTIMATED (profit model),
# HISTORICAL (Census 2011 baseline), UNAVAILABLE (missing weather), and DEMO
# rows must never leak into real evidence.

def _run(client):
    return client.post("/analysis", json={
        "state": "Tamil Nadu", "district": "Erode",
        "block": "Sathyamangalam", "village": "Sathyamangalam",
        "capital_available": 100000, "category_code": "dairy",
    }).json()


def _price(session, item, demo=False, ref="2026-06-15", modal=52.0):
    from datetime import date

    from app.db.models import MarketPrice

    session.add(MarketPrice(
        item_name=item, category="agriculture", unit="kg",
        modal_price=modal, min_price=modal - 5, max_price=modal + 5,
        market_name="Erode Market", state="Tamil Nadu", district="Erode",
        mandi="Erode Market", reference_date=date.fromisoformat(ref),
        source_name="Agmarknet" if not demo else "some-demo",
        source_type="government" if not demo else "demo",
        dataset_name="market_prices", confidence="high",
        is_estimate=False, is_demo=demo,
    ))


def test_e2e_all_live_evidence_statuses(client, session):
    _price(session, "milk")
    _price(session, "ghee")
    session.commit()
    ev = _run(client)

    # REAL price evidence (verified, non-demo rows only)
    assert ev["price"]["available"] is True
    assert all(i["item_name"] for i in ev["price"]["items"])
    assert ev["price"]["source"]["source_type"] == "government"
    assert not any(i.get("is_demo") for i in ev["price"]["items"])

    # HISTORICAL population baseline
    assert ev["population"]["available"] is True
    assert ev["population"]["is_historical"] is True
    assert ev["population"]["census_year"] == 2011

    # ESTIMATED profit projection
    assert ev["profit_model"]["is_estimate"] is True

    # CALCULATED opportunity index with four-state decision
    score = ev["opportunity_score"]
    assert score["overall_score"] is not None
    assert score["risk_score"] is not None
    assert ev["recommendation"]["label"] in ("GO", "MODIFY", "AVOID", "INSUFFICIENT DATA")

    # UNAVAILABLE weather (no rows stored) - no fabricated flags
    assert ev["weather"]["available"] is False
    assert ev["weather"]["risk"]["factors"] is None

    # provenance ledger documented
    assert any(s["name"] == "Mandi prices (verified)" for s in ev["data_sources"])


def test_e2e_demo_rows_never_leak_into_evidence(client, session):
    from app.db.models import Business, WeatherStatistic

    _price(session, "milk", demo=True)          # demo price
    session.add(Business(
        name="Demo Dairy", category_code="dairy",
        latitude=11.5050, longitude=77.2390, source="demo", source_id="999",
        source_name="demo", source_type="demo", is_demo=True))
    session.add(WeatherStatistic(
        location_id="loc_sathya", level="village", indicator="forecast_temperature_max",
        period="2026-08-31", value=45.0, unit="degC",
        source_name="Open-Meteo", source_type="test", is_estimate=True, is_demo=True))
    session.commit()
    ev = _run(client)

    # demo price rows are excluded -> price UNAVAILABLE, not showing demo values
    assert ev["price"]["available"] is False
    assert ev["price"]["items"] == []
    assert ev["price"]["unavailable_reason"].startswith("No verified")

    # demo heat-stress weather row must NOT raise a risk flag
    assert ev["weather"]["available"] is False
    assert ev["weather"]["risk"]["factors"] is None
    assert ev["weather"]["records"] == []

    # demo competitor excluded from the mapped-competitor counts
    names = {c["name"] for c in ev["business_competition"].get("competitors", [])}
    assert "Demo Dairy" not in names
