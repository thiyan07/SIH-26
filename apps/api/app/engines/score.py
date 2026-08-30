"""Opportunity scoring engine + confidence + GO/MODIFY/AVOID.

Deterministic, transparent "Prototype Opportunity Index". Weights are
configurable. Missing inputs reduce confidence instead of being fabricated.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from app.config import settings

DEFAULT_WEIGHTS = {
    "demand": 0.25,
    "competition": 0.20,
    "accessibility": 0.15,
    "price": 0.15,
    "financial_fit": 0.15,
    "risk": 0.10,
}

# Decision labels (Phase 12): opportunity vs data-confidence separation.
DECISION_GO = "GO"
DECISION_MODIFY = "MODIFY"
DECISION_AVOID = "AVOID"
DECISION_INSUFFICIENT = "INSUFFICIENT DATA"


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


def confidence_label(score: float,
                     medium_at: Optional[float] = None,
                     high_at: Optional[float] = None) -> str:
    medium_at = settings.confidence_medium_at if medium_at is None else medium_at
    high_at = settings.confidence_high_at if high_at is None else high_at
    if score >= high_at:
        return "high"
    if score >= medium_at:
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


def _recommend(
    overall: float,
    financial_s: float,
    risk_s: float,
    conf_label: str,
    *,
    go_above: Optional[float] = None,
    avoid_below: Optional[float] = None,
    finance_fit_go_min: Optional[float] = None,
    risk_go_max: Optional[float] = None,
    risk_avoid_above: Optional[float] = None,
    finance_avoid_below: Optional[float] = None,
) -> tuple[str, str]:
    """Decision matrix (Phase 12): opportunity score vs data confidence.

    Four states:
      - GO                 high score, reliable evidence, financial fit
      - MODIFY             viable but needs a different model/scale/capital
      - AVOID              current evidence indicates significant risk
      - INSUFFICIENT DATA  evidence too thin to judge — decide is deferred,
                           never fabricated. Low confidence forces this state.
    All thresholds come from config/env and are overridable for tests.
    """
    go = settings.opportunity_go_above if go_above is None else go_above
    avoid = settings.opportunity_avoid_below if avoid_below is None else avoid_below
    fin_go = settings.finance_fit_go_min if finance_fit_go_min is None else finance_fit_go_min
    r_max = settings.risk_go_max if risk_go_max is None else risk_go_max
    r_avoid = settings.risk_avoid_above if risk_avoid_above is None else risk_avoid_above
    f_avoid = settings.finance_avoid_below if finance_avoid_below is None else finance_avoid_below

    if conf_label == "low":
        return DECISION_INSUFFICIENT, (
            "Evidence is insufficient/low-confidence. Decide only after "
            "collecting current local data; any GO/AVOID here would be provisional."
        )
    if overall >= go and financial_s >= fin_go and risk_s <= r_max:
        return DECISION_GO, (
            "Potentially suitable based on available indicators "
            "(demand, accessibility, financial fit)."
        )
    if overall < avoid or risk_s >= r_avoid or financial_s < f_avoid:
        return DECISION_AVOID, "Current evidence indicates significant risk or poor financial fit."
    return DECISION_MODIFY, (
        "Potentially viable, but revisit business model, scale, or capital before proceeding."
    )
