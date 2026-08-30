"""MarketReachAnalyzer — reusable market-reach engine (plan §13).

Input:  location (population/households + competitor/reach radius).
Output: population_baseline, households, commercial_demand_signals,
        market_accessibility, confidence.

Everything is computed from cached, provenance-bearing DB records. Missing
evidence is reported as unavailable (never fabricated); confidence is
reduced accordingly.

`commercial_demand_signals` are nearby mapped establishments that represent
buying/demand clusters for a category (restaurants, hotels, markets,
retail). The exact categories examined are configurable via `signal_codes`.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from app.geo import find_nearby_with_distance

DEFAULT_SIGNAL_CODES = ("restaurant", "grocery", "market")  # demand proxies

# Demand score proxy based on population baseline (documented heuristic).
# Missing population -> demand score is unavailable (None), not fabricated.
def _demand_score(population: Optional[int]) -> Optional[float]:
    if population is None or population <= 0:
        return None
    return round(min(100.0, 40.0 + (population / 5000.0) * 30.0), 1)


@dataclass
class MarketReachResult:
    population_baseline: Optional[int]
    population_year: Optional[int]
    households: Optional[int]
    commercial_demand_signals: dict
    market_accessibility: dict
    confidence: float
    available_population: bool

    def to_dict(self) -> dict:
        return {
            "market_reach": {
                "population_baseline": self.population_baseline,
                "population_year": self.population_year,
                "households": self.households,
                "available_population": self.available_population,
                "demand_score": _demand_score(self.population_baseline),
                "commercial_demand_signals": self.commercial_demand_signals,
                "market_accessibility": self.market_accessibility,
                "confidence": self.confidence,
                "notes": [
                    "Population is the historical Census baseline and is NOT current population.",
                    "Commercial demand signals are counts of mapped establishments and may be incomplete.",
                ],
            }
        }


def analyze(
    db: Any,
    *,
    location: Any,
    radius_km: float = 10.0,
    signal_codes: tuple[str, ...] = DEFAULT_SIGNAL_CODES,
    data_completeness: str = "medium",
) -> MarketReachResult:
    """Assemble market-reach indicators for an ORM Location row."""
    lat, lon = location.latitude, location.longitude
    PopulationStatistic = __import__("app.db.models", fromlist=["PopulationStatistic"]).PopulationStatistic
    from sqlalchemy import select

    pop = db.execute(
        select(PopulationStatistic).where(PopulationStatistic.location_id == location.id)
    ).scalars().first()

    # commercial demand signals: mapped establishments per signal category
    signals = {}
    for code in signal_codes:
        rows = find_nearby_with_distance(
            db, __import__("app.db.models", fromlist=["Business"]).Business,
            lat, lon, radius_km, {"category_code": code}, limit=300,
        )
        signals[code] = {"count": len(rows), "radius_km": radius_km}

    InfrastructurePoint = __import__("app.db.models", fromlist=["InfrastructurePoint"]).InfrastructurePoint
    markets = find_nearby_with_distance(
        db, InfrastructurePoint, lat, lon, 20.0, {"kind": "market"}, limit=50,
    )
    transport = find_nearby_with_distance(
        db, InfrastructurePoint, lat, lon, 20.0, {"kind": "transport"}, limit=50,
    )
    market_dists = [d for _, d in markets]
    transport_dists = [d for _, d in transport]

    available_pop = pop is not None and pop.population is not None
    base_conf = {"high": 0.9, "medium": 0.67, "low": 0.45}.get(data_completeness, 0.5)
    if not available_pop:
        base_conf *= 0.7

    return MarketReachResult(
        population_baseline=pop.population if available_pop else None,
        population_year=pop.census_year if available_pop else None,
        households=pop.households if available_pop else None,
        commercial_demand_signals=signals,
        market_accessibility={
            "nearest_market_km": round(min(market_dists), 2) if market_dists else None,
            "markets_within_20km": len(markets),
            "nearest_transport_km": round(min(transport_dists), 2) if transport_dists else None,
            "transport_points_within_20km": len(transport),
        },
        confidence=round(base_conf, 2),
        available_population=available_pop,
    )
