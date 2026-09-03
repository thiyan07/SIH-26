"""SIH26092: category-aware Market Intelligence engine tests."""
from __future__ import annotations

from datetime import date, timedelta

from app.db.models import MarketPrice
from app.engines.market_intelligence import (
    RELEVANT_COMMODITIES,
    category_market_intelligence,
    relevant_commodities,
)


def _add_price(session, *, item, district="Erode", ref="2026-08-31", modal=100.0,
               market="Perundurai(Uzhavar Sandhai )", demo=False, source_type="government",
               source_name="data.gov.in"):
    row = MarketPrice(
        item_name=item, category="agriculture", unit="kg",
        modal_price=modal, min_price=modal - 5, max_price=modal + 5,
        market_name=market, state="Tamil Nadu", district=district, mandi=None,
        reference_date=ref,
        source_name=source_name, source_type=source_type,
        dataset_name="market_prices", confidence="high",
        is_estimate=False, is_demo=demo,
    )
    session.add(row)
    return row


def _run(session, category="grocery", district="Erode",
         lat=None, lng=None, max_age_days=90, today=None):
    return category_market_intelligence(
        session, category_code=category, state="Tamil Nadu", district=district,
        latitude=lat, longitude=lng, max_age_days=max_age_days, today=today,
    )


def test_grocery_filters_to_relevant_commodities_only(session):
    # Tomato & onion are grocery-relevant; "ghee" is not.
    _add_price(session, item="Tomato", modal=90.0)
    _add_price(session, item="Onion", modal=110.0)
    _add_price(session, item="Ghee", modal=900.0)
    session.flush()

    out = _run(session, category="grocery")
    items = {p["item"].lower() for p in out["prices"]}
    assert out["available"] is True
    assert "tomato" in items and "onion" in items
    assert "ghee" not in items  # dairy commodity filtered out for grocery


def test_demo_rows_are_excluded(session):
    _add_price(session, item="Rice", modal=50.0, demo=True, source_type="demo")
    session.flush()
    out = _run(session, category="grocery")
    assert out["available"] is False
    assert out["prices"] == []


def test_freshness_window_filters_stale_rows(session):
    _add_price(session, item="Tomato", ref=date.today() - timedelta(days=2))
    _add_price(session, item="Onion", ref=date.today() - timedelta(days=200))
    session.flush()

    fresh = _run(session, category="grocery", max_age_days=90)
    assert {p["item"].lower() for p in fresh["prices"]} == {"tomato"}

    wide = _run(session, category="grocery", max_age_days=300)
    assert {p["item"].lower() for p in wide["prices"]} == {"tomato", "onion"}


def test_no_relevant_category_reports_unavailable_honestly(session):
    _add_price(session, item="Tomato", modal=90.0)  # real price exists
    session.flush()
    out = _run(session, category="textile")  # textile has a commodity list (cotton etc.)
    assert out["available"] is False
    assert out["confidence"]["score"] == 0.0
    assert out["confidence"]["label"] == "low"


def test_metadata_exposed(session):
    _add_price(session, item="Tomato", modal=90.0)
    session.flush()
    out = _run(session, category="grocery")
    assert out["category_code"] == "grocery"
    assert out["district"] == "Erode"
    assert out["commodity_scope"]["has_specific_commodities"] is True
    assert "tomato" in " ".join(out["commodity_scope"]["relevant_commodities"]).lower() or \
        any("tomato" in c for c in out["commodity_scope"]["relevant_commodities"])
    assert out["source_hierarchy"]  # non-empty when available


def test_relevant_commodities_catalog(session):
    assert "tomato" in relevant_commodities("grocery")
    assert "milk" in relevant_commodities("dairy")
    assert "chicken" in relevant_commodities("meat_shop")
    assert relevant_commodities("pharmacy") == ()  # no list -> accepts any
    assert "grocery" in RELEVANT_COMMODITIES


def test_demand_context_only_when_coordinates_given(session):
    _add_price(session, item="Tomato", modal=90.0)
    session.flush()
    no_loc = _run(session, category="grocery", lat=None, lng=None)
    assert no_loc["demand_context"] is None  # no coords -> no fabricated demand signal
    # coordinates path doesn't crash and builds a demand block
    with_loc = _run(session, category="grocery", lat=11.27, lng=77.6)
    assert with_loc["available"] is True
    assert with_loc["demand_context"] is not None
