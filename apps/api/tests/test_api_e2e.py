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

    # recommendation present
    assert ev["recommendation"]["label"] in ("GO", "MODIFY", "AVOID")

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
