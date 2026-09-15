"""Market Gap Detection — saturated/moderate/underserved with feasibility."""
from __future__ import annotations

__version__ = "1.0.0"

# Thresholds for competitor density per category within radius
# These are transparent and never invented — 0 count means no evidence, not no competitors
THRESHOLDS = {
    "high": 5,  # >=5 competitors in radius → saturated
    "moderate": 2,  # 2-4 → moderate
    # 0-1 → underserved / gap (but check demand before calling opportunity)
}


def _verdict(count: int | None) -> str:
    if count is None:
        return "unknown"
    if count >= THRESHOLDS["high"]:
        return "saturated"
    if count >= THRESHOLDS["moderate"]:
        return "moderate"
    if count == 0:
        return "underserved"
    return "gap"  # 1 competitor


def analyze_gaps(
    *,
    competitor_density: dict[str, int | None],
    demand_indicators: dict[str, float | None] | None = None,
    price_snapshot: dict | None = None,
    business_category: str | None = None,
) -> dict:
    """Return gaps list + overall note, never fabricating missing data."""
    demand_indicators = demand_indicators or {}
    gaps = []
    for cat, count in competitor_density.items():
        verdict = _verdict(count)
        # Feasibility — not auto-opportunity
        feasibility = "unknown"
        limitations = []
        demand = demand_indicators.get(cat) if isinstance(demand_indicators, dict) else None
        if verdict in ("underserved", "gap"):
            if demand is not None:
                if demand >= 60:
                    feasibility = "potential opportunity — low competition + adequate demand"
                elif demand >= 40:
                    feasibility = "possible — low competition but moderate demand, verify purchasing power"
                else:
                    feasibility = "not automatically an opportunity — low demand despite low competition"
                    limitations.append("Demand evidence is weak for this category")
            else:
                feasibility = "unknown — low competition but no demand signal"
                limitations.append("No demand indicator for this category — collect local price/demand before deciding")
        elif verdict == "saturated":
            feasibility = "high competition — differentiation or nearby location needed"
        else:
            feasibility = "moderate — viable with differentiation"

        if count is None:
            limitations.append("No competitor data for this category in radius")
        if price_snapshot is None or not price_snapshot:
            limitations.append("Price information unavailable for this radius")

        gaps.append({
            "category": cat,
            "count": count,
            "verdict": verdict,
            "feasibility": feasibility,
            "demand": demand,
            "limitations": limitations,
        })

    # Sort: saturated first (risk), then underserved/gap
    order = {"saturated": 0, "moderate": 1, "gap": 2, "underserved": 3, "unknown": 4}
    gaps.sort(key=lambda x: order.get(x["verdict"], 5))

    return {
        "gaps": gaps,
        "model_version": __version__,
        "note": "A gap is not automatically an opportunity — combine with demand, accessibility, and cost. Missing data is shown as limitations, never invented.",
    }
