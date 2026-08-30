"""Weather risk heuristics (Phase 7).

Evaluates ONLY stored, provenance-tagged weather rows (Open-Meteo/NASA POWER)
into named, explained risk flags. It is deterministic and never invents
values: every flag cites the recorded indicator/value that triggered it, and a
flag simply does not exist when the underlying row is missing.

Flags
-----
- heat_stress  : temperature (mean/max/current/forecast max) too high.
- drought      : low annual rainfall total vs a fixed index-sensibility bar.
- flood_risk   : very high daily precipitation (current or forecast).

Each flag carries `level` (high|medium|low) and a plain-language `note`.
`risk_delta` sums the contributions (capped at 25) for the overall risk score.
"""
from __future__ import annotations

from typing import Optional

HEAT_HIGH_LEVEL = 15
HEAT_MEDIUM_LEVEL = 8
HEAT_LOW_LEVEL = 3

DROUGHT_HIGH_LEVEL = 8
DROUGHT_MEDIUM_LEVEL = 4

FLOOD_LEVEL = 8

RISK_CAP = 25


def _first_ge(records: list[dict], indicators: tuple[str, ...], above: float) -> Optional[float]:
    for rec in records:
        if rec.get("indicator") in indicators:
            try:
                v = float(rec.get("value"))
            except (TypeError, ValueError):
                continue
            if v >= above:
                return v
    return None


def _max_of(records: list[dict], indicators: tuple[str, ...]) -> Optional[float]:
    best = None
    for rec in records:
        if rec.get("indicator") in indicators:
            try:
                v = float(rec.get("value"))
            except (TypeError, ValueError):
                continue
            best = v if best is None else max(best, v)
    return best


def _min_of(records: list[dict], indicators: tuple[str, ...]) -> Optional[float]:
    best = None
    for rec in records:
        if rec.get("indicator") in indicators:
            try:
                v = float(rec.get("value"))
            except (TypeError, ValueError):
                continue
            best = v if best is None else min(best, v)
    return best


def weather_risk_factors(records: list[dict]) -> dict:
    """Evaluate stored weather rows into risk flags + a capped risk_delta."""
    found: list[dict] = []  # {factor, level, note, contribution}
    total = 0

    heat_ind = ("temperature", "temperature_max", "current_temperature", "forecast_temperature_max")
    heat_peak = _max_of(records, heat_ind)
    if heat_peak is not None and heat_peak >= 40.0:
        found.append({"factor": "heat_stress", "level": "high", "contribution": HEAT_HIGH_LEVEL,
                      "note": f"Peak recorded temperature {heat_peak:.1f}C (heat-stress conditions)."})
    elif heat_peak is not None and heat_peak >= 38.0:
        found.append({"factor": "heat_stress", "level": "medium", "contribution": HEAT_MEDIUM_LEVEL,
                      "note": f"Peak recorded temperature {heat_peak:.1f}C (heat-stress watch)."})
    elif heat_peak is not None and heat_peak >= 35.0:
        found.append({"factor": "heat_stress", "level": "low", "contribution": HEAT_LOW_LEVEL,
                      "note": f"Peak recorded temperature {heat_peak:.1f}C (elevated)."})

    # Drought: annual rainfall totals (period 'YYYY' rows from ERA5 annual sums).
    annual = _min_of(records, ("rainfall",))
    if annual is not None and annual < 400.0:
        found.append({"factor": "drought", "level": "high", "contribution": DROUGHT_HIGH_LEVEL,
                      "note": f"Lowest recorded annual rainfall {annual:.0f}mm (drought-prone)."})
    elif annual is not None and annual < 600.0:
        found.append({"factor": "drought", "level": "medium", "contribution": DROUGHT_MEDIUM_LEVEL,
                      "note": f"Lowest recorded annual rainfall {annual:.0f}mm (below-normal rainfall)."})

    # Flood risk: very high daily precipitation (current or forecast).
    flood = _first_ge(records, ("current_precipitation", "forecast_precipitation_sum"), 100.0)
    if flood is not None:
        found.append({"factor": "flood_risk", "level": "high", "contribution": FLOOD_LEVEL,
                      "note": f"Recorded precipitation {flood:.0f}mm/day (flood risk)."})

    total = min(RISK_CAP, sum(f["contribution"] for f in found))
    for f in found:
        f["risk_delta"] = f.pop("contribution")
    return {
        "factors": found or None,
        "risk_delta": total,
    }
