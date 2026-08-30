"""Opportunity scoring engine + confidence + GO/MODIFY/AVOID.

Deterministic, transparent "Prototype Opportunity Index". Weights are
configurable. Missing inputs reduce confidence instead of being fabricated.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

DEFAULT_WEIGHTS = {
    "demand": 0.25,
    "competition": 0.20,
    "accessibility": 0.15,
    "price": 0.15,
    "financial_fit": 0.15,
    "risk": 0.10,
}


@dataclass
class ConfidenceFactors:
    population_freshness: Optional[int] = None  # years since reference
    business_coverage: str = "medium"
    price_freshness: Optional[int] = None
    weather_freshness: Optional[int] = None
    geo_precision: str = "point"
    source_reliability: str = "medium"
    data_missing: list[str] = field(default_factory=list)


@dataclass
class OpportunityResult:
    overall_score: float
    demand_score: float
    competition_score: float
    accessibility_score: float
    price_score: float
    financial_fit_score: float
    risk_score: float
    confidence_score: float
    confidence_label: str
    confidence_factors: dict
    recommendation: str  # GO | MODIFY | AVOID
    recommendation_reason: str
    component_breakdown: dict
    weights: dict
    indicators: dict = field(default_factory=dict)


def _norm(value: Optional[float], default: float = 50.0) -> float:
    """Normalize a 0-100 score, defaulting middle when missing."""
    if value is None:
        return default
    return max(0.0, min(100.0, float(value)))


def confidence_label(score: float) -> str:
    if score >= 70:
        return "high"
    if score >= 40:
        return "medium"
    return "low"


def _confidence_score(factors: ConfidenceFactors, missing_penalty: int, present_indicators: int, total_indicators: int) -> tuple[float, dict]:
    reasons = []
    score = 80.0

    if factors.population_freshness is not None and factors.population_freshness > 5:
        score -= 15
        reasons.append(f"Population data is {factors.population_freshness} years old (Census baseline).")
    elif factors.population_freshness is not None:
        reasons.append("Population data is recent.")

    if factors.business_coverage == "low":
        score -= 15
        reasons.append("Business coverage from OSM is low.")
    elif factors.business_coverage == "medium":
        score -= 8
        reasons.append("Business coverage from OSM is medium.")
    else:
        reasons.append("Business coverage from OSM is high.")

    if factors.price_freshness is not None and factors.price_freshness > 2:
        score -= 8
        reasons.append("Price data is not recent.")
    elif factors.price_freshness is not None:
        reasons.append("Price data is recent.")

    if factors.weather_freshness is not None and factors.weather_freshness > 2:
        score -= 5
        reasons.append("Weather data is not recent.")
    elif factors.weather_freshness is not None:
        reasons.append("Weather data is recent.")

    if factors.geo_precision == "point":
        reasons.append("Location precision is point-level.")
    elif factors.geo_precision == "centroid":
        score -= 6
        reasons.append("Location precision is approximate (centroid).")

    if factors.source_reliability == "low":
        score -= 10
        reasons.append("Some sources have low reliability.")

    # completeness penalty
    completeness_ratio = (present_indicators / total_indicators) if total_indicators else 1.0
    missing_count = total_indicators - present_indicators
    if missing_count:
        score -= min(20, missing_count * 3)
        reasons.append(f"{missing_count} indicator type(s) missing/insufficient: {', '.join(factors.data_missing[:5])}.")

    score -= missing_penalty
    score = max(0.0, min(100.0, score))
    return round(score, 1), {
        "score": score,
        "reasons": reasons,
        "coverage_ratio": round(completeness_ratio, 2),
        "covered_indicators": present_indicators,
        "total_indicators": total_indicators,
    }


def compute_opportunity(
    *,
    demand: Optional[float] = None,
    competition: Optional[float] = None,
    accessibility: Optional[float] = None,
    price: Optional[float] = None,
    financial_fit: Optional[float] = None,
    risk: Optional[float] = None,  # higher = more risk
    weights: Optional[dict[str, float]] = None,
    confidence_factors: Optional[ConfidenceFactors] = None,
    indicators: Optional[dict] = None,
) -> OpportunityResult:
    w = {**DEFAULT_WEIGHTS, **(weights or {})}

    demand_s = _norm(demand)
    competition_s = _norm(competition)
    accessibility_s = _norm(accessibility)
    price_s = _norm(price)
    financial_s = _norm(financial_fit)
    risk_s = _norm(risk)
    risk_non_risk = 100.0 - risk_s

    overall = (
        w["demand"] * demand_s
        + w["competition"] * competition_s
        + w["accessibility"] * accessibility_s
        + w["price"] * price_s
        + w["financial_fit"] * financial_s
        + w["risk"] * risk_non_risk
    )
    overall = max(0.0, min(100.0, round(overall, 1)))

    components = {
        "demand": round(demand_s, 1),
        "competition": round(competition_s, 1),
        "accessibility": round(accessibility_s, 1),
        "price": round(price_s, 1),
        "financial_fit": round(financial_s, 1),
        "risk": round(risk_s, 1),
    }

    # Confidence
    factors = confidence_factors or ConfidenceFactors()
    present = sum(1 for v in [demand, competition, accessibility, price, financial_fit, risk] if v is not None)
    total = 6
    missing_penalty = 0
    missing_list = []
    mapping = {
        "demand": demand, "competition": competition, "accessibility": accessibility,
        "price": price, "financial_fit": financial_fit, "risk": risk,
    }
    for k, v in mapping.items():
        if v is None:
            missing_list.append(k)
            missing_penalty += 4
    factors.data_missing = missing_list

    conf_score, conf_detail = _confidence_score(factors, missing_penalty, present, total)
    conf_label = confidence_label(conf_score)

    # Recommendation
    recommendation, reason = _recommend(overall, financial_s, risk_s, conf_label)
    result = OpportunityResult(
        overall_score=overall,
        demand_score=components["demand"],
        competition_score=components["competition"],
        accessibility_score=components["accessibility"],
        price_score=components["price"],
        financial_fit_score=components["financial_fit"],
        risk_score=components["risk"],
        confidence_score=conf_score,
        confidence_label=conf_label,
        confidence_factors=conf_detail,
        recommendation=recommendation,
        recommendation_reason=reason,
        component_breakdown=components,
        weights=w,
        indicators=indicators or {},
    )
    from app.log import log_event

    log_event("score", overall=overall, confidence=conf_label,
              recommendation=recommendation, components=components)
    return result


def _recommend(overall: float, financial_s: float, risk_s: float, conf_label: str) -> tuple[str, str]:
    # Guarded by confidence - low confidence forces MODIFY/AVOID language.
    if conf_label == "low":
        return "MODIFY", (
            "Evidence is insufficient/low-confidence. Treat any GO/AVOID as provisional; "
            "collect current local data before deciding."
        )
    if overall >= 65 and financial_s >= 60 and risk_s <= 55:
        return "GO", "Potentially suitable based on available indicators (demand, accessibility, financial fit)."
    if overall < 45 or risk_s >= 80 or financial_s < 40:
        return "AVOID", "Current evidence indicates significant risk or poor financial fit."
    return "MODIFY", "Potentially viable, but revisit business model, scale, or capital before proceeding."
