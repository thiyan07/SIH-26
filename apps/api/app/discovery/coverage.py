"""Coverage engine — measurable discovery coverage, not fake completeness.

For every (district, locality, category, source) tracks:
queries_attempted / successful / unique / google/osm / cross_matches / last_scraped

Status: GOOD | PARTIAL | LOW | NOT_SEARCHED | ERROR | STALE
Wording: High/Medium/Low discovery coverage (never "total businesses").
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

COV_GOOD = "GOOD"
COV_PARTIAL = "PARTIAL"
COV_LOW = "LOW"
COV_NOT_SEARCHED = "NOT_SEARCHED"
COV_ERROR = "ERROR"
COV_STALE = "STALE"

FRESH_LABELS = {"fresh": 30, "aging": 90, "stale": 180}

@dataclass
class CoverageRecord:
    district: str
    locality: str
    category: str
    source: str
    queries_attempted: int = 0
    queries_successful: int = 0
    unique_results: int = 0
    google_results: int = 0
    osm_results: int = 0
    cross_source_matches: int = 0
    last_scraped_at: str | None = None
    search_depth: int = 0
    coverage_status: str = COV_NOT_SEARCHED
    freshness: str = "unknown"

    def to_dict(self) -> dict:
        return {
            "district": self.district,
            "locality": self.locality,
            "category": self.category,
            "source": self.source,
            "queries_attempted": self.queries_attempted,
            "queries_successful": self.queries_successful,
            "unique_results": self.unique_results,
            "google_results": self.google_results,
            "osm_results": self.osm_results,
            "cross_source_matches": self.cross_source_matches,
            "last_scraped_at": self.last_scraped_at,
            "search_depth": self.search_depth,
            "coverage_status": self.coverage_status,
            "freshness": self.freshness,
        }

def assess_coverage(rec: CoverageRecord, config=None) -> str:
    if rec.queries_attempted == 0:
        return COV_NOT_SEARCHED
    if rec.queries_successful == 0:
        return COV_ERROR
    # Stale check
    if rec.last_scraped_at:
        try:
            last = dt.datetime.fromisoformat(rec.last_scraped_at.replace("Z", "+00:00"))
            age_days = (dt.datetime.now(dt.timezone.utc) - last).days
            if age_days > 180:
                return COV_STALE
        except Exception:
            pass
    # Heuristic: good = many unique results + multiple sources
    if rec.unique_results >= 15 and rec.cross_source_matches >= 2:
        return COV_GOOD
    if rec.unique_results >= 5:
        return COV_PARTIAL
    if rec.unique_results > 0:
        return COV_LOW
    # attempted but found nothing: could be low coverage or truly sparse
    return COV_LOW

def coverage_label(status: str) -> str:
    mapping = {
        COV_GOOD: "High discovery coverage",
        COV_PARTIAL: "Moderate discovery coverage",
        COV_LOW: "Low discovery coverage",
        COV_NOT_SEARCHED: "Not yet surveyed",
        COV_ERROR: "Discovery error",
        COV_STALE: "Stale discovery coverage",
    }
    return mapping.get(status, status)

def freshness_for(last_scraped_at: str | None, fresh_days=30, aging_days=90) -> str:
    if not last_scraped_at:
        return "unknown"
    try:
        last = dt.datetime.fromisoformat(last_scraped_at.replace("Z", "+00:00"))
        age = (dt.datetime.now(dt.timezone.utc) - last).days
        if age <= fresh_days:
            return "fresh"
        if age <= aging_days:
            return "aging"
        return "stale"
    except Exception:
        return "unknown"

def discovery_coverage_score(locality_coverage: float, category_coverage: float, source_diversity: float, search_saturation: float, freshness: float, geographic_coverage: float) -> float:
    """Weighted discovery coverage score (0-100), not a business truth score."""
    weights = {
        "locality": 0.25,
        "category": 0.20,
        "source_diversity": 0.15,
        "saturation": 0.15,
        "freshness": 0.15,
        "geographic": 0.10,
    }
    score = (
        locality_coverage * weights["locality"]
        + category_coverage * weights["category"]
        + source_diversity * weights["source_diversity"]
        + search_saturation * weights["saturation"]
        + freshness * weights["freshness"]
        + geographic_coverage * weights["geographic"]
    )
    return round(score, 1)

def aggregate_coverage(records: list[CoverageRecord]) -> dict:
    total = len(records)
    if total == 0:
        return {"total": 0, "by_status": {}, "overall": "Not yet surveyed"}
    by_status: dict[str, int] = {}
    for r in records:
        s = r.coverage_status
        by_status[s] = by_status.get(s, 0) + 1
    # Overall label based on majority
    if by_status.get(COV_GOOD, 0) / total > 0.6:
        overall = "High discovery coverage"
    elif (by_status.get(COV_GOOD, 0) + by_status.get(COV_PARTIAL, 0)) / total > 0.5:
        overall = "Moderate discovery coverage"
    elif by_status.get(COV_NOT_SEARCHED, 0) / total > 0.5:
        overall = "Not yet surveyed"
    else:
        overall = "Low discovery coverage"
    return {"total": total, "by_status": by_status, "overall": overall}
