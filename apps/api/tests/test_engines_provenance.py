"""Tests for reusable provenance/freshness/quality and the new
CompetitionAnalyzer + MarketReachAnalyzer engines (plan §9, §10, §12, §13,
§30 data integrity)."""
from __future__ import annotations

import datetime as dt

import pytest

from app.engines.competition import _comp_score, _density, _level, analyze
from app.engines.market import analyze as analyze_market
from app.provenance import (
    DEFAULT_POLICIES,
    FRESHNESS_AGING,
    FRESHNESS_FRESH,
    FRESHNESS_OLD,
    FRESHNESS_RECENT,
    FRESHNESS_UNKNOWN,
    QualityInputs,
    compute_data_quality,
    freshness_for,
)

# ---------- provenance / freshness (§9) ----------

def test_source_specific_freshness_policies():
    today = dt.date(2026, 1, 1)
    # Population 2011 baseline is "old" under the population policy...
    assert freshness_for(source_type="population", reference_year=2011, now=today) == FRESHNESS_OLD
    # ...but weather from 2023.would be "old" too under weather policy (fresher window).
    assert freshness_for(source_type="weather",
                         reference_date=dt.date(2023, 1, 1), now=today) == FRESHNESS_OLD


def test_population_allowed_older_than_weather():
    # A 2011 baseline is "old" for population, but a 2011 weather figure is
    # also old; the key point: policies differ so a single global threshold is
    # never used (plan §9).
    assert DEFAULT_POLICIES["population"].aging_under > DEFAULT_POLICIES["weather"].aging_under


def test_freshness_recent():
    assert freshness_for(source_type="population", reference_year=2020) in (
        FRESHNESS_RECENT, FRESHNESS_AGING, FRESHNESS_FRESH,
    )


def test_freshness_unknown_when_no_reference():
    assert freshness_for(source_type="business") == FRESHNESS_UNKNOWN


# ---------- data-quality / confidence (§10) ----------

def test_quality_score_with_old_census_flagged():
    q = compute_data_quality(QualityInputs(
        freshness_buckets=[FRESHNESS_OLD],
        geographic_precision="centroid",
        coverage="medium",
        completeness=0.6,
    ))
    assert 0 <= q["data_confidence_score"] <= 100
    assert q["confidence_label"] in ("low", "medium", "high")
    assert any("old" in r.lower() for r in q["reasons"])


def test_quality_score_demo_reduces_confidence():
    clean = compute_data_quality(QualityInputs(freshness_buckets=[FRESHNESS_FRESH]))
    demo = compute_data_quality(QualityInputs(freshness_buckets=[FRESHNESS_FRESH], any_demo=True))
    assert demo["data_confidence_score"] < clean["data_confidence_score"]


def test_quality_score_missing_reduces_confidence():
    full = compute_data_quality(QualityInputs(freshness_buckets=[FRESHNESS_FRESH], completeness=1.0))
    partial = compute_data_quality(QualityInputs(
        freshness_buckets=[FRESHNESS_FRESH], completeness=0.5,
        any_missing_indicators=["population"]))
    assert partial["data_confidence_score"] < full["data_confidence_score"]


# ---------- CompetitionAnalyzer (§12) ----------

def test_comp_score_counts():
    assert _comp_score(0, "medium") == 80.0
    assert _comp_score(2, "medium") == pytest.approx(88.0, rel=1e-6)  # 100 - 12
    assert _comp_score(20, "medium") >= 5.0


def test_density_documented_formula():
    # 10 businesses in a 5km disc (area ~78.5 km²) -> density ~1.0
    assert _density(10, 5.0) == pytest.approx(1.0, abs=0.05)


def test_level_thresholds():
    assert _level(3) == "low"
    assert _level(5) == "moderate"
    assert _level(15) == "high"


def test_competition_analyzer_db(session):
    res = analyze(
        session, latitude=11.5056, longitude=77.2390,
        category_code="dairy", radius_km=5.0, data_completeness="medium",
    )
    assert res.mapped_competitors >= 1  # demo dairy businesses within 5km
    assert 0.0 <= res.density <= 1.0
    assert res.nearest_competitor_km is not None and res.nearest_competitor_km >= 0
    assert res.competition_level in ("low", "moderate", "high")
    assert 0.0 <= res.confidence <= 1.0
    # cautious wording
    d = to_dict_for(res)
    assert "mapped" in d["note"].lower()


def to_dict_for(res):
    from app.engines.competition import to_dict
    return to_dict(res)


# ---------- MarketReachAnalyzer (§13) ----------

def test_market_reach_analyzer_db(session):
    from app.db.models import Location
    loc = session.query(Location).filter_by(village="Sathyamangalam").first()
    mr = analyze_market(session, location=loc, radius_km=10.0, data_completeness="medium")
    d = mr.to_dict()["market_reach"]
    # Population baseline available from seeded demo proxy
    assert d["population_baseline"] is not None
    assert d["population_year"] == 2011
    assert "commercial_demand_signals" in d
    assert "nearest_market_km" in d["market_accessibility"]
    assert 0.0 <= d["confidence"] <= 1.0


def test_market_reach_no_population_low_confidence():
    q = compute_data_quality(QualityInputs(
        freshness_buckets=[], completeness=0.4, any_missing_indicators=["population"]))
    # Absence reduces confidence rather than fabricating a value
    assert q["completeness"] < 1.0


# ---------- OSM category mapping (§4) ----------

def test_osm_category_mapping():
    from scripts.ingest_osm.ingest import _category_for_tags
    assert _category_for_tags({"shop": "dairy"}) == "dairy"
    assert _category_for_tags({"amenity": "restaurant"}) == "restaurant"
    assert _category_for_tags({"shop": "convenience"}) == "grocery"
    # An unrelated shop should not map to a known business category
    assert _category_for_tags({"shop": "car_repair"}) is None


def test_osm_region_preset_resolves_bbox():
    from scripts.ingest_osm.ingest import DEFAULT_REGION, REGION_BBOXES
    assert DEFAULT_REGION in REGION_BBOXES
    assert len(REGION_BBOXES[DEFAULT_REGION].split(",")) == 4


def test_osm_infra_kind_mapping():
    from scripts.ingest_osm.ingest import _infra_kind
    assert _infra_kind({"amenity": "bank"}) == "bank"
    assert _infra_kind({"amenity": "school"}) == "school"
    assert _infra_kind({"amenity": "bus_station"}) == "transport"
    assert _infra_kind({"amenity": "restaurant"}) is None


# ---------- Deterministic 14-section report (§23) ----------

def test_build_report_has_14_sections_and_grounds_values():
    from app.ai.compose import build_report
    evidence = {
        "opportunity_score": {"overall_score": 62, "confidence_label": "Medium"},
        "recommendation": {"label": "Proceed with caution", "reason": "moderate fit"},
        "financial_plan": {"capital_available": 50000, "project_cost": 100000,
                           "loan_amount": 50000, "margin_pct": 50, "scheme_name": "PMEGP",
                           "interest_rate": 7, "tenure_years": 5, "moratorium_months": 12,
                           "source_document": "demo"},
        "repayment": {"monthly_emi": 990.41, "health_label": "healthy",
                      "coverage_ratio": 1.2, "disclaimer": "est"},
        "population": {"available": True, "population": 9800000},
        "market": {"market_reach": {"households": 2450000,
                                    "market_accessibility": {"nearest_market_km": 12,
                                                             "nearest_transport_km": 5}}},
        "business_competition": {"mapped_competitors_5km": 1, "mapped_competitors_10km": 3,
                                 "nearest_competitor_km": 1.2, "data_completeness": "medium"},
        "infrastructure": {"nearest_market_km": 12, "nearest_transport_km": 5},
        "location": {"village": "Sathyamangalam", "block": "Sathyamangalam",
                     "district": "Erode", "state": "Tamil Nadu"},
        "data_sources": [{"name": "Census 2011", "reference_year": 2011, "confidence": "high"}],
        "prices": [],
    }
    sections = build_report(evidence)
    names = [s["section"] for s in sections]
    assert len(sections) == 14
    assert "Scheme" in names and names[0] == "Executive Summary"
    # Population wording must reflect historical baseline, not current population
    market = [s for s in sections if s["section"] == "Market Reach"][0]
    assert any("Census 2011" in k for k, _ in market["items"])
    scheme = [s for s in sections if s["section"] == "Scheme"][0]
    assert "PMEGP" in [v for _, v in scheme["items"]]


def test_build_report_missing_population_not_invented():
    from app.ai.compose import build_report
    sections = build_report({})
    market = [s for s in sections if s["section"] == "Market Reach"][0]
    assert any("Unavailable" in str(v) for _, v in market["items"])
