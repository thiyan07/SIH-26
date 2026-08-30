"""Reusable provenance, freshness, and data-quality model.

Plan §3 (provenance), §9 (freshness), §10 (quality score).

A single `Provenance` value object carries the canonical provenance fields on
every externally-sourced fact. Freshness is evaluated per-source via
source-specific policies (population may legitimately be older than weather).
These helpers stay detached from the ORM so they are trivially unit-testable.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Optional

# Canonical freshness buckets (plan §9)
FRESHNESS_FRESH = "fresh"
FRESHNESS_RECENT = "recent"
FRESHNESS_AGING = "aging"
FRESHNESS_OLD = "old"
FRESHNESS_UNKNOWN = "unknown"

# Confidence bands (where a numeric 0-100 confidence is also desired)
CONF_HIGH = "high"
CONF_MEDIUM = "medium"
CONF_LOW = "low"


@dataclass
class Provenance:
    """Canonical provenance for any externally-sourced record (plan §3)."""

    source_name: Optional[str] = None
    source_url: Optional[str] = None
    dataset_name: Optional[str] = None
    source_type: Optional[str] = None  # government|osm|vendor|proxy|demo
    reference_date: Optional[dt.date] = None
    reference_year: Optional[int] = None
    retrieved_at: Optional[dt.datetime] = None
    geographic_level: Optional[str] = None
    license: Optional[str] = None
    confidence: Optional[str] = None  # low|medium|high
    is_estimate: bool = False
    is_demo: bool = False
    methodology: Optional[str] = None

    def to_dict(self) -> dict:
        out: dict = {
            "source_name": self.source_name,
            "source_url": self.source_url,
            "dataset_name": self.dataset_name,
            "source_type": self.source_type,
            "geographic_level": self.geographic_level,
            "license": self.license,
            "confidence": self.confidence,
            "is_estimate": self.is_estimate,
            "is_demo": self.is_demo,
            "methodology": self.methodology,
        }
        if self.reference_date is not None:
            out["reference_date"] = self.reference_date.isoformat()
        if self.reference_year is not None:
            out["reference_year"] = self.reference_year
        if self.retrieved_at is not None:
            out["retrieved_at"] = self.retrieved_at.isoformat()
        return {k: v for k, v in out.items() if v is not None and v != "" and v is not False}


@dataclass
class FreshnessPolicy:
    """Per-source freshness thresholds (plan §9: no single global threshold).

    Lists age (in years, fractional allowed) boundaries between buckets.
    A newer age maps to "fresh"; an older age to "old".

    Example defaults:
      population : fresh<5, recent<10, aging<15, else old
      weather    : fresh<0.25, recent<1, aging<2, else old
      business   : fresh<0.5, recent<1, aging<2, else old
    """

    fresh_under: float = 1.0          # age_years < this -> fresh
    recent_under: float = 3.0         # age_years < this -> recent
    aging_under: float = 10.0         # age_years < this -> aging
    # age_years >= aging_under -> old

    def bucket(self, age_years: Optional[float]) -> str:
        if age_years is None:
            return FRESHNESS_UNKNOWN
        if age_years < self.fresh_under:
            return FRESHNESS_FRESH
        if age_years < self.recent_under:
            return FRESHNESS_RECENT
        if age_years < self.aging_under:
            return FRESHNESS_AGING
        return FRESHNESS_OLD


# Default source-specific policies (plan §9).
DEFAULT_POLICIES: dict[str, FreshnessPolicy] = {
    "population": FreshnessPolicy(fresh_under=5, recent_under=10, aging_under=15),
    "weather": FreshnessPolicy(fresh_under=0.25, recent_under=1.0, aging_under=2.0),
    "business": FreshnessPolicy(fresh_under=0.5, recent_under=1.0, aging_under=2.0),
    "market_price": FreshnessPolicy(fresh_under=0.5, recent_under=1.0, aging_under=2.0),
    "infrastructure": FreshnessPolicy(fresh_under=1.0, recent_under=2.0, aging_under=4.0),
    "government": FreshnessPolicy(fresh_under=1.0, recent_under=3.0, aging_under=6.0),
    "default": FreshnessPolicy(fresh_under=1.0, recent_under=3.0, aging_under=5.0),
}


def age_years(reference: dt.date, now: Optional[dt.date] = None) -> Optional[float]:
    """Whole-fraction years between a reference date and now."""
    if reference is None:
        return None
    now = now or dt.date.today()
    return (now - reference).days / 365.25


def age_years_from_year(reference_year: Optional[int], now: Optional[int] = None) -> Optional[float]:
    if reference_year is None:
        return None
    now = now or dt.date.today().year
    return float(now - reference_year)


def freshness_for(
    *,
    source_type: Optional[str],
    reference_date: Optional[dt.date] = None,
    reference_year: Optional[int] = None,
    now: Optional[dt.date] = None,
) -> str:
    """Bucket freshness using the policy appropriate to the source."""
    policy_key = source_type if source_type in DEFAULT_POLICIES else "default"
    policy = DEFAULT_POLICIES[policy_key]
    if reference_date is not None:
        return policy.bucket(age_years(reference_date, now))
    return policy.bucket(age_years_from_year(reference_year, (now or dt.date.today()).year))


def confidence_band(score: float) -> str:
    if score >= 70:
        return CONF_HIGH
    if score >= 40:
        return CONF_MEDIUM
    return CONF_LOW


@dataclass
class QualityInputs:
    """Inputs to the data-quality / confidence score (plan §10)."""

    freshness_buckets: list[str] = field(default_factory=list)  # one per source
    geographic_precision: str = "point"           # point|centroid|village
    coverage: str = "medium"                      # low|medium|high
    completeness: float = 1.0                     # 0..1 ratio of indicators present
    source_reliability: str = "medium"            # high|medium|low (gov > osm > demo)
    any_demo: bool = False
    any_missing_indicators: list[str] = field(default_factory=list)


def compute_data_quality(q: QualityInputs) -> dict:
    """Combine quality factors into a single 0-100 `data_confidence_score`.

    Deterministic, transparent, and explained via `reasons`. Missing inputs
    reduce confidence instead of fabricating values (plan §10, §16, §22).
    """
    reasons: list[str] = []
    score = 70.0

    # Freshness: old/aging/unknown sources penalize; per-source buckets.
    for b in q.freshness_buckets:
        if b in (FRESHNESS_FRESH, FRESHNESS_RECENT):
            reasons.append(f"Source data is {b}.")
        elif b == FRESHNESS_AGING:
            score -= 8
            reasons.append("Some source data is ageing.")
        elif b == FRESHNESS_OLD:
            score -= 15
            reasons.append("Some source data is old (e.g. historical Census baseline).")
        else:  # unknown
            score -= 10
            reasons.append("Freshness of some source data is unknown.")

    # Geographic precision
    if q.geographic_precision == "centroid":
        score -= 6
        reasons.append("Location precision is approximate (centroid, whole village).")
    elif q.geographic_precision != "point":
        score -= 4
        reasons.append("Location precision is approximate.")

    # Coverage / completeness
    coverage_penalty = {"low": -15, "medium": -7, "high": 0}.get(q.coverage, 0)
    if coverage_penalty:
        score += coverage_penalty
        reasons.append(f"Business/layer coverage is {q.coverage} (mapped data may be incomplete).")
    if q.completeness < 1.0:
        missing = int((1.0 - q.completeness) * 100)
        score -= min(20, missing // 10 * 3)
        reasons.append(
            f"{missing}% of indicator evidence is missing/insufficient: "
            f"{', '.join(q.any_missing_indicators[:5]) or 'see analysis'}."
        )

    # Source reliability
    if q.source_reliability == "low":
        score -= 10
        reasons.append("Some sources have low reliability.")
    if q.any_demo:
        score -= 12
        reasons.append("Includes demo/proxy data (not verified official values).")

    score = max(0.0, min(100.0, round(score, 1)))
    return {
        "data_confidence_score": score,
        "confidence_label": confidence_band(score),
        "reasons": reasons,
        "geographic_precision": q.geographic_precision,
        "coverage": q.coverage,
        "completeness": round(q.completeness, 2),
        "freshness_buckets": q.freshness_buckets,
    }
