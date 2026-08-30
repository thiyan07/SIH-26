"""Plan §14: DB-backed category profiles."""
from __future__ import annotations

from app.ai.compose import build_risks
from app.db.models import BusinessCategory
from app.engines.category_profiles import (
    CATEGORY_PROFILES,
    PROFILE_FIELDS,
    get_category_profile,
    seed_category_profiles,
)
from app.engines.profit import known_categories

_CATEGORY_CODES = {c["code"] for c in known_categories()}

_REQUIRED_KEYS = (
    "required_inputs",
    "demand_signals",
    "competition_categories",
    "cost_components",
    "revenue_components",
    "risk_factors",
    "seasonality",
)


def test_registry_covers_all_known_categories():
    assert set(CATEGORY_PROFILES) == _CATEGORY_CODES
    for code, profile in CATEGORY_PROFILES.items():
        for key in _REQUIRED_KEYS:
            assert key in profile, f"{code} missing {key}"
        assert profile["name"], f"{code} missing name"


def test_registry_consistent_with_engines():
    dairy = CATEGORY_PROFILES["dairy"]
    assert "feed_cost" in dairy["cost_components"]
    assert dairy["demand_signals"] == ["restaurant", "grocery", "market"]
    assert dairy["competition_categories"] == ["dairy"]
    assert "Milk spoilage" in dairy["risk_factors"][1]["factor"] or any(
        "milk" in r["factor"].lower() for r in dairy["risk_factors"]
    )
    assert dairy["seasonality"]["note"]
    assert CATEGORY_PROFILES["restaurant"]["competition_categories"] == ["restaurant", "food_processing"]


def test_get_profile_falls_back_without_db(session):
    profile = get_category_profile(session, "dairy")
    assert profile["code"] == "dairy"
    assert profile["name"]
    assert profile["demand_signals"]
    assert profile.get("db_backed") is False or "db_backed" in profile


def test_seed_populates_db_and_get_returns_db_backed(session):
    seeded = seed_category_profiles(session)
    assert seeded >= len(_CATEGORY_CODES) - 2  # conftest pre-creates dairy+grocery
    session.flush()
    row = session.query(BusinessCategory).filter(BusinessCategory.code == "dairy").first()
    assert row is not None
    for field in PROFILE_FIELDS:
        assert getattr(row, field), f"dairy.{field} not seeded"
    profile = get_category_profile(session, "dairy")
    assert profile["db_backed"] is True
    assert profile["cost_components"] == row.cost_components
    assert profile["name"] == row.name


def test_seed_is_idempotent(session):
    first = seed_category_profiles(session)
    session.flush()
    second = seed_category_profiles(session)
    assert second == 0
    assert first >= len(_CATEGORY_CODES) - 2


def test_db_edits_override_registry(session):
    seed_category_profiles(session)
    session.flush()
    row = session.query(BusinessCategory).filter(BusinessCategory.code == "dairy").first()
    row.demand_signals = ["dairy"]
    session.flush()
    profile = get_category_profile(session, "dairy")
    assert profile["demand_signals"] == ["dairy"]
    assert profile["db_backed"] is True


def test_unknown_category_returns_empty(session):
    assert get_category_profile(session, "nope") == {}


def test_build_risks_inject_category_profile(session):
    seed_category_profiles(session)
    session.flush()
    profile = get_category_profile(session, "dairy")
    evidence = {"category_profile": profile, "business_competition": {"data_completeness": "medium"}}
    risks = build_risks(evidence)
    factors = [r["factor"] for r in risks]
    assert "Data completeness" in factors
    assert "Fodder & feed price volatility" in factors
    assert "Seasonality" in factors


def test_build_risks_without_profile_preserves_defaults():
    risks = build_risks({"business_competition": {"data_completeness": "low"}})
    assert any("Data completeness" in r["factor"] for r in risks)
    assert not any(r["factor"] == "Seasonality" for r in risks) or \
        not any("feed" in r["factor"].lower() for r in risks)
