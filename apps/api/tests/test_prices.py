"""Plan hardening: verified DB-backed price provider (plan §17)."""
from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient

from app.db.models import MarketPrice
from app.engines.prices import derive_price_evidence, price_score_from_evidence
from app.main import app

client = TestClient(app)


def _add_price(session, item, district="Erode", ref="2026-01-15", modal=42.0,
               market="Erode Market", source_name="Agmarknet", demo=True):
    row = MarketPrice(
        item_name=item, category="agriculture", unit="kg",
        modal_price=modal, min_price=modal - 5, max_price=modal + 5,
        market_name=market, state="Tamil Nadu", district=district, mandi=market,
        reference_date=date.fromisoformat(ref),
        source_name=source_name, source_type="demo" if demo else "government",
        dataset_name="market_prices", confidence="high",
        is_estimate=False, is_demo=demo,
    )
    session.add(row)
    return row


def test_no_rows_reports_unavailable(session):
    ev = derive_price_evidence(session, "Erode", "dairy")
    assert ev["available"] is False
    assert ev["item_count"] == 0
    assert price_score_from_evidence(ev) is None


def test_latest_reference_date_per_item(session):
    _add_price(session, item="milk", ref="2026-01-01", modal=40.0)
    _add_price(session, item="milk", ref="2026-06-15", modal=52.0)
    session.flush()
    ev = derive_price_evidence(session, "Erode", "dairy")
    assert ev["available"] is True
    (milk,) = ev["items"]
    assert milk["item_name"] == "milk"
    assert milk["modal_price"] == 52.0
    assert milk["reference_date"] == "2026-06-15"


def test_district_scoped(session):
    _add_price(session, item="milk", district="Salem")
    session.flush()
    assert derive_price_evidence(session, "Erode", "grocery")["item_count"] == 0
    assert derive_price_evidence(session, "Erode", "dairy")["item_count"] == 0
    assert derive_price_evidence(session, "Salem", "dairy")["item_count"] == 1


def test_relevance_filter_and_coverage(session):
    for item in ("milk", "ghee", "curd", "tomato"):
        _add_price(session, item=item)
    session.flush()
    ev = derive_price_evidence(session, "Erode", "dairy")  # relevant: milk/ghee/curd/paneer/butter
    assert ev["available"] is True
    assert ev["item_count"] == 3
    assert ev["coverage"] == round(3 / 5, 2)
    assert {i["item_name"] for i in ev["items"]} == {"milk", "ghee", "curd"}


def test_unmapped_category_accepts_any_item(session):
    _add_price(session, item="cobalt")
    session.flush()
    ev = derive_price_evidence(session, "Erode", "handicrafts")
    assert ev["available"] is True
    assert ev["coverage"] == 1.0


def test_price_score_from_coverage():
    assert price_score_from_evidence({"available": True, "item_count": 1, "coverage": 1.0}) == 90.0
    assert price_score_from_evidence({"available": True, "item_count": 3, "coverage": 0.4}) == 60.0
    assert price_score_from_evidence({"available": False, "item_count": 0, "coverage": 0.0}) is None


def test_analysis_price_unavailable_without_rows(seeded):
    d = client.post("/analysis", json={
        "state": "Tamil Nadu", "district": "Erode", "block": "Sathyamangalam",
        "village": "Sathyamangalam", "capital_available": 100000,
        "category_code": "dairy",
    }).json()
    assert d["price"]["available"] is False
    assert d["opportunity_score"]["price_score"] == 50.0


def test_analysis_uses_verified_price_rows(session):
    session.add_all([
        _add_price(session, item="milk", ref="2026-06-15", modal=52.0),
        _add_price(session, item="ghee", ref="2026-06-15", modal=480.0),
        _add_price(session, item="curd", ref="2026-06-15", modal=45.0),
    ])
    session.commit()
    d = client.post("/analysis", json={
        "state": "Tamil Nadu", "district": "Erode", "block": "Sathyamangalam",
        "village": "Sathyamangalam", "capital_available": 100000,
        "category_code": "dairy",
    }).json()
    assert d["price"]["available"] is True
    assert d["price"]["item_count"] == 3
    assert d["opportunity_score"]["price_score"] >= 40
    names = {s["name"] for s in d["data_sources"]}
    assert "Mandi prices (verified)" in names
