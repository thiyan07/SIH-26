"""Data-quality scoring registry (plan §10 extension)."""
from __future__ import annotations

import pytest

from app.data_quality import (
    SOURCE_QUALITY_CATALOG,
    _freshness_status,
    confidence_band,
    score_source,
)


def test_udyam_catalog_is_pincode_and_honest():
    e = SOURCE_QUALITY_CATALOG["udyam"]
    assert e.geo_resolution == "pincode"
    assert e.source_type == "government"
    assert e.cadence == "DAILY"
    # Pincode granularity + no turnover/investment in the unit list are caveats.
    assert any("Pincode" in lim for lim in e.limitations)


def test_score_source_returns_all_five_scores():
    r = score_source(SOURCE_QUALITY_CATALOG["udyam"], age_years=0.1)
    for k in ("source_quality_score", "freshness_score", "completeness_score",
              "verification_score", "overall_confidence_score"):
        assert r[k] is not None
        assert 0 <= r[k] <= 100
    assert r["overall_confidence_score"] == pytest.approx(
        round(0.25 * r["source_quality_score"] + 0.20 * r["freshness_score"]
              + 0.20 * r["completeness_score"] + 0.35 * r["verification_score"], 1))


def test_freshness_buckets_are_cadence_aware():
    # Daily-feed UDYAM: 0.1y fresh, 0.4y recent, 0.7y stale, 1.5y very stale.
    udyam = SOURCE_QUALITY_CATALOG["udyam"]
    assert _freshness_status(udyam, 0.1) == "FRESH"
    assert _freshness_status(udyam, 0.4) == "RECENT"
    assert _freshness_status(udyam, 0.7) == "STALE"
    assert _freshness_status(udyam, 1.5) == "VERY_STALE"
    # Census baseline: fresh/recent/stale thresholds are 0 -> very stale at any age.
    census = SOURCE_QUALITY_CATALOG["census_2011"]
    assert _freshness_status(census, 15.0) == "VERY_STALE"


def test_stale_daily_feed_scores_freshness_low_but_verify_carries():
    u = SOURCE_QUALITY_CATALOG["udyam"]
    stale = score_source(u, age_years=2.0)  # 2y old daily feed
    fresh = score_source(u, age_years=0.05)
    assert stale["freshness_score"] < fresh["freshness_score"]
    assert stale["freshness_status"] == "VERY_STALE"
    # Verification is weighted highest, so a well-verified source stays medium+
    # even when stale - but the reasons must call out the staleness.
    assert any("VERY_STALE" in r for r in stale["reasons"])


def test_unverified_and_conflicting_are_downgraded():
    # A source verified -> keeps verification; a CONFLICTING one is capped.
    base = SOURCE_QUALITY_CATALOG["udyam"]
    normal = score_source(base, age_years=0.1)
    # simulate by overriding the entry's verification status
    import dataclasses
    conflict_entry = dataclasses.replace(
        base, verification_status="CONFLICTING", verification=100.0)
    conflict = score_source(conflict_entry, age_years=0.1)
    assert conflict["verification_score"] <= 45.0
    assert conflict["verification_score"] < normal["verification_score"]
    assert any("CONFLICTING" in r for r in conflict["reasons"])


def test_missing_snapshot_not_assumed_fresh():
    # No age and a live cadence source -> freshness unknown (not fresh), lowish.
    fresh_snapshot = score_source(SOURCE_QUALITY_CATALOG["udyam"], age_years=0.05)
    no_snapshot = score_source(SOURCE_QUALITY_CATALOG["udyam"], age_years=None)
    assert no_snapshot["freshness_status"] == "UNKNOWN"
    assert no_snapshot["freshness_score"] < fresh_snapshot["freshness_score"]


def test_confidence_band_mapping():
    assert confidence_band(80) == "high"
    assert confidence_band(50) == "medium"
    assert confidence_band(20) == "low"
