"""Location suitability — compact score derived from existing evidence.

Not a new scoring system; re-uses demand/competition/accessibility/infra
evidence already computed for the opportunity score.
"""
from __future__ import annotations


def location_suitability(
    *,
    competition: dict | None = None,
    infrastructure: dict | None = None,
    population: dict | None = None,
    market_intelligence: dict | None = None,
    demand_score: float | None = None,
    accessibility_score: float | None = None,
) -> dict:
    """Return a 0-100 suitability score with strengths and concerns.

    Derived transparently from existing evidence; weighted blend so no single
    factor dominates.
    """
    comp_score = 50.0
    if competition:
        # competition_score already inverted (higher = less competition = better)
        comp_score = float(competition.get("competition_score") or competition.get("competitionScore") or 50)

    acc_score = float(accessibility_score or 50)
    dem_score = float(demand_score or 50)

    # Price/market evidence: medium confidence if available, low if not.
    market_strength = 50.0
    market_concern = None
    if market_intelligence:
        if market_intelligence.get("available"):
            conf = market_intelligence.get("confidence", {})
            label = conf.get("label", "low")
            market_strength = {"high": 75, "medium": 60, "low": 40}.get(label, 40)
        else:
            market_strength = 30
            market_concern = "Limited market evidence for this category/location"

    # Infra: nearest market/transport/health.
    infra_strength = 50.0
    if infrastructure:
        nm = infrastructure.get("nearest_market_km")
        nt = infrastructure.get("nearest_transport_km")
        # closer = better
        infra_strength = 50
        if nm is not None:
            if nm <= 3:
                infra_strength += 20
            elif nm <= 10:
                infra_strength += 10
            else:
                infra_strength -= 15
        if nt is not None and nt <= 5:
            infra_strength += 10
        infra_strength = max(0, min(100, infra_strength))

    # Blend: competition 30%, accessibility 30%, demand 20%, infra 10%, market 10%.
    suitability = round(
        0.30 * comp_score + 0.30 * acc_score + 0.20 * dem_score + 0.10 * infra_strength + 0.10 * market_strength,
        1,
    )
    suitability = max(0, min(100, suitability))

    # Confidence: reduce if population is historical or competition coverage low.
    confidence = "medium"
    reasons: list[str] = []
    if population and population.get("is_historical"):
        reasons.append("Population is historical Census 2011 baseline — not current.")
        if suitability > 70:
            confidence = "medium"
    if competition and competition.get("data_completeness") == "low":
        confidence = "low"
        reasons.append("Competition data completeness is low.")
    if market_concern:
        reasons.append(market_concern)
        confidence = "low" if confidence == "medium" else confidence

    # Strengths / concerns (deterministic, top 3).
    strengths: list[str] = []
    concerns: list[str] = []
    if acc_score >= 65:
        strengths.append("Good accessibility (near market/transport)")
    elif acc_score < 45:
        concerns.append("Limited accessibility — distant from market hub")

    if comp_score >= 65:
        strengths.append("Low to moderate competition in catchment")
    elif comp_score < 45:
        concerns.append("High mapped competition — site selection will matter")

    if dem_score >= 65:
        strengths.append("Strong surrounding population evidence")
    elif dem_score < 45:
        concerns.append("Weak demand evidence for this catchment")

    if infra_strength >= 65:
        strengths.append("Nearby market/transport infrastructure")
    if market_concern:
        concerns.append(market_concern)
    if not strengths:
        strengths.append("No strong location advantages identified in current evidence")
    if not concerns:
        concerns.append("No major location concerns detected")

    return {
        "suitability_score": suitability,
        "confidence": confidence,
        "strengths": strengths[:3],
        "concerns": concerns[:3],
        "breakdown": {
            "competition": comp_score,
            "accessibility": acc_score,
            "demand": dem_score,
            "infrastructure": infra_strength,
            "market": market_strength,
        },
        "reasons": reasons,
        "note": "Derived from existing competition, accessibility, demand and market evidence (not a separate model).",
    }
