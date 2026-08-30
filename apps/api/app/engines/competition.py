"""CompetitionAnalyzer — reusable competition engine (plan §12).

Input:  location (lat/lon), business_category, radius(es).
Output: mapped_competitors, density, nearest_competitor_km,
        competition_level, confidence + evidence.

Data comes from the already-ingested database (cached OSM), never live.

Documented formulas
-------------------
- `density` = mapped competitors within the primary radius, scaled by the
  area of the search disc in square km (nominal cross-section used only as a
  comparability index, NOT a claim of actual market size):
      area_km2 = pi * radius_km^2
      density  = min(mapped_count / (area_km2 / 10), 1.0)
  The `/10` normalises so that ~10 mapped businesses in a 5km disc (≈78 km²)
  maps to a density of ~1.0. Density is a relative intensity index, rounded
  to 2 decimals.

- `competition_level` (low / moderate / high) thresholds:
      mapped_competitors >= 15  -> high
      mapped_competitors >= 5   -> moderate
      else                      -> low

- `competition_score` (0-100, higher = more favourable to a new entrant):
      if no mapped competitors : 80 (advantage), confidence reduced by
                                  coverage so absent data is not read as
                                  absence of competition.
      else                     : clamp(100 - min(mapped_count * 6, 100))
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Optional

from app.geo import find_nearby_with_distance

PRIMARY_RADIUS_KM = 5.0
SECONDARY_RADIUS_KM = 10.0


@dataclass
class CompetitionResult:
    mapped_competitors: int
    density: float
    nearest_competitor_km: Optional[float]
    competition_level: str
    confidence: float  # 0..1
    coverage: str
    data_completeness: str
    nearest_competitor: Optional[str] = None
    businesses: list[dict] = field(default_factory=list)


def _level(count: int) -> str:
    if count >= 15:
        return "high"
    if count >= 5:
        return "moderate"
    return "low"


def _density(count: int, radius_km: float) -> float:
    area_km2 = math.pi * (radius_km ** 2)
    if area_km2 <= 0:
        return 0.0
    return round(min(count / (area_km2 / 10.0), 1.0), 2)


def _comp_score(count: int, coverage: str) -> float:
    if count == 0:
        # No mapped competitors -> apparent advantage, but confidence penalised
        # by coverage so absence of data is not reported as absence of demand.
        return 80.0
    score = 100.0 - min(float(count) * 6.0, 100.0)
    return round(max(5.0, score), 1)


def _confidence(count: int, coverage: str) -> float:
    # Coverage-derived confidence (0..1). Absent data does not read as high
    # confidence "no competition".
    base = {"high": 0.9, "medium": 0.67, "low": 0.45}.get(coverage, 0.5)
    if count == 0 and coverage != "high":
        base *= 0.6  # "no mapped competitors" is less certain with low coverage
    return round(base, 2)


def analyze(
    db: Any,
    *,
    latitude: float,
    longitude: float,
    category_code: str,
    radius_km: float = PRIMARY_RADIUS_KM,
    data_completeness: str = "medium",
) -> CompetitionResult:
    """Count mapped competitors within radius and nearest distance."""
    rows = find_nearby_with_distance(
        db, __import__("app.db.models", fromlist=["Business"]).Business,
        latitude, longitude, radius_km, {"category_code": category_code}, limit=300,
    )
    count = len(rows)
    distances = [d for _, d in rows]
    nearest = min(distances) if distances else None
    nearest_row = min(rows, key=lambda r: r[1])[0] if rows else None

    return CompetitionResult(
        mapped_competitors=count,
        density=_density(count, radius_km),
        nearest_competitor_km=round(nearest, 2) if nearest is not None else None,
        competition_level=_level(count),
        confidence=_confidence(count, data_completeness),
        coverage=data_completeness,
        data_completeness=data_completeness,
        nearest_competitor=nearest_row.name if nearest_row else None,
        businesses=[
            {
                "id": r.id, "name": r.name, "category_code": r.category_code,
                "latitude": r.latitude, "longitude": r.longitude,
                "distance_km": round(d, 2),
                "source_name": r.source_name, "source_type": r.source_type,
                "confidence": r.confidence,
            }
            for r, d in rows[:50]
        ],
    )


def to_dict(r: CompetitionResult, *, as_mapped: bool = True) -> dict:
    """Serialize, always using the cautious "mapped" wording (plan §6)."""
    return {
        "mapped_competitors": r.mapped_competitors,
        "mapped_competitors_5km": r.mapped_competitors,
        "density": r.density,
        "nearest_competitor_km": r.nearest_competitor_km,
        "nearest_competitor": r.nearest_competitor,
        "competition_level": r.competition_level,
        "competition_score": _comp_score(r.mapped_competitors, r.coverage),
        "confidence": r.confidence,
        "data_completeness": r.data_completeness,
        "coverage": r.coverage,
        "note": "Mapped business data may be incomplete; competitor counts are minimums, not exhaustive.",
        "businesses": r.businesses,
    }
