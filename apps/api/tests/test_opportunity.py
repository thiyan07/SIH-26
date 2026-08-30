"""Opportunity engine + confidence tests (section 40)."""
from __future__ import annotations

import pytest

from app.engines.score import (
    DEFAULT_WEIGHTS,
    ConfidenceFactors,
    _recommend,
    compute_opportunity,
    confidence_label,
)


def test_weights_sum_to_one():
    assert abs(sum(DEFAULT_WEIGHTS.values()) - 1.0) < 1e-9


def test_normalization_and_overall():
    r = compute_opportunity(demand=80, competition=60, accessibility=70,
                            price=50, financial_fit=90, risk=30)
    expected = (
        0.25 * 80 + 0.20 * 60 + 0.15 * 70 + 0.15 * 50
        + 0.15 * 90 + 0.10 * (100 - 30)
    )
    assert r.overall_score == pytest.approx(expected, rel=1e-6)
    assert 0 <= r.overall_score <= 100


def test_bounds_clamped():
    r = compute_opportunity(demand=150, competition=-10, financial_fit=999, risk=0)
    assert all(0 <= v <= 100 for v in [r.demand_score, r.competition_score,
                                       r.financial_fit_score, r.risk_score])


def test_missing_data_reduces_confidence():
    full = compute_opportunity(demand=80, competition=60, accessibility=70,
                               price=50, financial_fit=90, risk=20,
                               confidence_factors=ConfidenceFactors(business_coverage="high"))
    partial = compute_opportunity(demand=80,
                                  confidence_factors=ConfidenceFactors(business_coverage="low"))
    assert partial.confidence_score < full.confidence_score
    assert "insufficient" in " ".join(map(str, partial.confidence_factors["reasons"])) or \
           any("missing" in r for r in partial.confidence_factors["reasons"])


def test_stale_census_lowers_confidence():
    fresh = compute_opportunity(demand=70, confidence_factors=ConfidenceFactors(population_freshness=1))
    old = compute_opportunity(demand=70, confidence_factors=ConfidenceFactors(population_freshness=13))
    assert old.confidence_score < fresh.confidence_score


def test_confidence_label_thresholds():
    assert confidence_label(0) == "low"
    assert confidence_label(50) == "medium"
    assert confidence_label(90) == "high"


def test_recommend_go():
    label, _ = _recommend(78, 80, 30, "high")
    assert label == "GO"


def test_recommend_avoid():
    label, _ = _recommend(30, 30, 90, "medium")
    assert label == "AVOID"


def test_recommend_modify():
    label, _ = _recommend(58, 45, 40, "medium")
    assert label == "MODIFY"


def test_low_confidence_forces_modify():
    label, _ = _recommend(95, 95, 10, "low")
    assert label == "MODIFY"


def test_custom_weights():
    r = compute_opportunity(demand=100, competition=0, accessibility=0, price=0,
                            financial_fit=0, risk=0,
                            weights={"demand": 1.0, "competition": 0, "accessibility": 0,
                                     "price": 0, "financial_fit": 0, "risk": 0})
    assert r.overall_score == pytest.approx(100, rel=1e-6)
