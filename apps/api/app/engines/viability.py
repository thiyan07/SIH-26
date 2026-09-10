"""Deterministic Business Viability Decision (GO/MODIFY/AVOID).

Reuses the existing opportunity-score framework and thresholds instead of
inventing a second scoring system. Inputs include demand, competition,
accessibility, price, financial fit, risk, profitability, repayment health,
seasonal intelligence, and data confidence.

All logic is deterministic and evidence-first; the LLM only explains.
"""
from __future__ import annotations

DECISION_GO = "GO"
DECISION_MODIFY = "MODIFY"
DECISION_AVOID = "AVOID"


def _safe(v, default=0.0):
    try:
        return float(v) if v is not None else default
    except (TypeError, ValueError):
        return default


def viability_decision(
    *,
    opportunity_score: float | None = None,
    confidence_label: str | None = None,
    financial_fit_score: float | None = None,
    risk_score: float | None = None,
    profitability: dict | None = None,  # monthly_economics dict
    repayment_health: dict | None = None,
    seasonal: dict | None = None,
    competition: dict | None = None,
    demand_score: float | None = None,
    accessibility_score: float | None = None,
    price_score: float | None = None,
    data_quality: dict | None = None,
) -> dict:
    """Produce a deterministic GO/MODIFY/AVOID with score, confidence, factors.

    Reuses opportunity-score thresholds from app.engines.score._recommend but
    extends them with profitability and repayment health evidence.
    """
    opp = _safe(opportunity_score, 50)
    fin_fit = _safe(financial_fit_score, 50)
    risk = _safe(risk_score, 50)

    # Extract profitability signals.
    op_profit = None  # noqa: F841 - retained for audit trace
    cash_surplus = None
    break_even_state = None  # noqa: F841
    gross_margin = None
    if profitability:
        op_profit = profitability.get("operating_profit")
        cash_surplus = profitability.get("cash_surplus")
        break_even_state = profitability.get("break_even_state")
        gross_margin = profitability.get("gross_margin_pct")

    # Repayment health.
    health_label = None
    coverage_ratio = None  # noqa: F841
    if repayment_health:
        health_label = repayment_health.get("label") or repayment_health.get("health_label")
        coverage_ratio = repayment_health.get("coverage_ratio")

    # Seasonal risk.
    seasonal_risk = None
    if seasonal:
        seasonal_risk = seasonal.get("cash_flow_risk")

    # --- Deterministic decision matrix ---
    # Start from opportunity score thresholds (mirrors score.py).
    # GO requires all of: opp >=70, fin_fit >=60, risk <=35, profitable, healthy repayment.
    # AVOID if opp <40 OR risk >=70 OR fin_fit <30 OR cash_surplus deeply negative with high risk.
    # Otherwise MODIFY.
    # Low confidence (low) degrades GO -> MODIFY, never fabricates AVOID without evidence.

    # Check hard AVOID triggers.
    avoid_reasons: list[str] = []
    go_reasons: list[str] = []
    modify_reasons: list[str] = []

    # Low confidence is not auto-AVOID; it caps at MODIFY unless other risks exist.
    confidence = (confidence_label or "medium").lower()

    if opp < 40:
        avoid_reasons.append(f"Low opportunity score {opp:.0f}/100")
    if risk >= 70:
        avoid_reasons.append(f"High risk score {risk:.0f}/100")
    if fin_fit < 30:
        avoid_reasons.append(f"Weak financial fit {fin_fit:.0f}/100")

    # Profitability hard check.
    if cash_surplus is not None and cash_surplus < 0 and opp < 55:
        # Deeply unprofitable + weak opportunity = avoid.
        if cash_surplus < -5000:
            avoid_reasons.append(f"Modelled cash surplus is negative (₹{cash_surplus:,.0f})")
    if gross_margin is not None and gross_margin < 8 and cash_surplus is not None and cash_surplus < 0:
        avoid_reasons.append(f"Low gross margin {gross_margin:.0f}% with negative cash surplus")

    # Repayment health.
    if health_label == "High Risk" and (cash_surplus is not None and cash_surplus < 0):
        avoid_reasons.append("Repayment health is High Risk and business shows negative cash surplus")
    elif health_label == "High Risk":
        # High risk alone pushes toward MODIFY, not necessarily AVOID, unless combined.
        modify_reasons.append("Repayment health is High Risk")

    # Seasonal risk HIGH + low margin = elevate risk.
    if seasonal_risk == "HIGH" and fin_fit < 50:
        modify_reasons.append("Seasonal cash-flow risk is HIGH with moderate financial fit")

    # Competition high + low demand.
    comp_level = (competition or {}).get("competition_level") or (competition or {}).get("competitionLevel")
    if comp_level == "high" and demand_score is not None and demand_score < 45:
        avoid_reasons.append("High competition with weak local demand evidence")
    elif comp_level == "high":
        modify_reasons.append("High competition — location choice matters")

    # Positive factors.
    if opp >= 70:
        go_reasons.append(f"Strong opportunity score {opp:.0f}/100")
    if demand_score is not None and demand_score >= 65:
        go_reasons.append(f"Adequate local demand ({demand_score:.0f}/100)")
    if cash_surplus is not None and cash_surplus > 5000 and health_label in ("Healthy", "Moderate", None):
        go_reasons.append(f"Positive modelled cash surplus ₹{cash_surplus:,.0f}")
    if health_label == "Healthy":
        go_reasons.append("Repayment health is Healthy")
    if risk < 35:
        go_reasons.append(f"Low risk score {risk:.0f}/100")
    if accessibility_score is not None and accessibility_score >= 65:
        go_reasons.append(f"Good accessibility ({accessibility_score:.0f}/100)")

    # Determine decision.
    if avoid_reasons:
        decision = DECISION_AVOID
        score = opp  # noqa: F841
        reason = "; ".join(avoid_reasons[:3])
    elif confidence == "low" and opp < 60:
        decision = DECISION_MODIFY
        score = opp  # noqa: F841
        reason = "Evidence confidence is low; a modified approach or more local data is needed."
    elif opp >= 70 and fin_fit >= 60 and risk <= 35 and (health_label in ("Healthy", None) or (cash_surplus is not None and cash_surplus >= 0)):
        # GO requires profitability unless no EMI (self-funded).
        if cash_surplus is not None and cash_surplus < 0 and health_label == "High Risk":
            decision = DECISION_MODIFY
            reason = "Strong opportunity but current capital/scale shows repayment strain — consider smaller scale or more own capital."
        else:
            decision = DECISION_GO
            reason = "Local evidence indicates adequate demand, manageable competition, and viable economics."
    else:
        decision = DECISION_MODIFY
        score = opp  # noqa: F841
        # Build MODIFY reason from strongest signals.
        parts = []
        if fin_fit < 60:
            parts.append("capital/scale needs adjustment")
        if risk >= 45:
            parts.append("moderate risk")
        if health_label == "High Risk":
            parts.append("repayment capacity is stretched")
        if comp_level == "high":
            parts.append("high competition")
        if not parts:
            parts.append("some indicators need improvement before a confident GO")
        reason = "Potentially viable, but " + ", ".join(parts) + "."

        # Degrade if low confidence.
        if confidence == "low":
            reason += " Evidence confidence is low — verify locally."

    # Confidence for decision: combine opportunity confidence with data quality.
    conf_score = 70.0
    if confidence == "high":
        conf_score = 80.0
    elif confidence == "medium":
        conf_score = 65.0
    elif confidence == "low":
        conf_score = 40.0

    if cash_surplus is not None and cash_surplus < 0:
        conf_score = max(30, conf_score - 10)

    # Top positive/negative factors (up to 3 each, deterministic).
    all_positives = go_reasons[:3] if go_reasons else ["Evidence gathered"]
    all_negatives: list[str] = []
    if avoid_reasons:
        all_negatives = avoid_reasons[:3]
    elif modify_reasons:
        all_negatives = modify_reasons[:3]
    else:
        # Synthesize negatives from weakest scores.
        weakest: list[tuple[float, str]] = []
        if demand_score is not None and demand_score < 50:
            weakest.append((demand_score, f"Demand evidence is weak ({demand_score:.0f}/100)"))
        if fin_fit < 50:
            weakest.append((fin_fit, f"Financial fit is moderate ({fin_fit:.0f}/100)"))
        if risk > 50:
            weakest.append((100 - risk, f"Risk is elevated ({risk:.0f}/100)"))
        if health_label == "High Risk":
            weakest.append((20, "Repayment capacity is constrained"))
        weakest.sort(key=lambda x: x[0])
        all_negatives = [w[1] for w in weakest[:3]]

    # Recommended actions (deterministic, practical).
    actions: list[str] = []
    if decision == DECISION_AVOID:
        actions.append("Consider an alternate business category or location with stronger demand and lower competition.")
        if fin_fit < 40:
            actions.append("Increase own capital or choose a smaller scale to reduce financing need.")
        if risk > 60:
            actions.append("Investigate risk mitigations (storage, alternate supply, off-season income).")
    elif decision == DECISION_MODIFY:
        if fin_fit < 60:
            actions.append("Start at a smaller scale (micro) or reduce initial inventory to lower project cost.")
        if comp_level == "high":
            actions.append("Consider a nearby location with fewer mapped competitors or a differentiated offering.")
        if health_label == "High Risk":
            actions.append("Improve repayment health by lowering loan amount or extending tenure (discuss with lender).")
        if not actions:
            actions.append("Revisit business plan with updated local price and demand information.")
        actions.append("Collect 2-3 local price points before finalizing.")
    else:  # GO
        actions.append("Proceed with detailed lender discussion; bring this estimate and local evidence.")
        actions.append("Secure supply-chain contacts and buffer stock for the first 2 months.")
        if seasonal_risk == "HIGH":
            actions.append("Plan working-capital buffer for the seasonal low month.")

    return {
        "decision": decision,
        "score": round(opp, 1),
        "confidence": confidence,
        "confidence_score": round(conf_score, 1),
        "reason": reason,
        "top_positive_factors": all_positives,
        "top_negative_factors": all_negatives,
        "recommended_actions": actions,
        "inputs_used": {
            "opportunity_score": opp,
            "financial_fit": fin_fit,
            "risk_score": risk,
            "demand_score": demand_score,
            "competition_level": comp_level,
            "cash_surplus": cash_surplus,
            "repayment_health": health_label,
            "seasonal_risk": seasonal_risk,
        },
    }
