"""Deterministic constraint summary — "What is limiting my business?"

Ranks the most important factors limiting viability without inventing reasons.
Every constraint is evidence-backed.
"""
from __future__ import annotations


def rank_constraints(
    *,
    financial_plan: dict | None = None,
    competition: dict | None = None,
    market_intelligence: dict | None = None,
    monthly_economics: dict | None = None,
    repayment: dict | None = None,
    seasonal: dict | None = None,
    infrastructure: dict | None = None,
    data_quality: dict | None = None,
    location_suitability: dict | None = None,
) -> dict:
    """Return ranked limiting constraints with severity HIGH/MEDIUM/LOW."""
    constraints: list[dict] = []

    # 1. Capital gap
    if financial_plan:
        required = financial_plan.get("required_financing") or 0
        own = financial_plan.get("own_contribution") or financial_plan.get("capital_available") or 0
        shortfall = financial_plan.get("shortfall") or 0
        project_cost = financial_plan.get("project_cost") or 0
        if shortfall > 0:
            sev = "HIGH" if shortfall > project_cost * 0.15 else "MEDIUM"
            constraints.append({
                "factor": "Insufficient own capital",
                "severity": sev,
                "detail": f"Required: ₹{required:,.0f}; own capital: ₹{own:,.0f}; shortfall: ₹{shortfall:,.0f}",
                "evidence": f"Project cost ₹{project_cost:,.0f}; financing need exceeds scheme contribution floor.",
                "action": "Reduce project scale or increase own capital before borrowing.",
            })
        elif required > 0 and own < project_cost * 0.1:
            constraints.append({
                "factor": "Insufficient own capital",
                "severity": "MEDIUM",
                "detail": f"Own capital ₹{own:,.0f} is below 10% of project cost ₹{project_cost:,.0f}",
                "evidence": "Scheme expects ≥10% beneficiary contribution.",
                "action": "Add own capital or choose smaller scale.",
            })

    # 2. Excessive financing / scheme cap
    if financial_plan:
        max_loan = financial_plan.get("max_loan")
        required = financial_plan.get("required_financing") or 0
        if max_loan is not None and required > max_loan:
            remaining = required - max_loan
            constraints.append({
                "factor": "Financing cap exceeded",
                "severity": "HIGH",
                "detail": f"Financing need ₹{required:,.0f} exceeds scheme maximum ₹{max_loan:,.0f}; gap ₹{remaining:,.0f}",
                "evidence": "Scheme routing caps loan per project cost bracket.",
                "action": "Reduce project cost (smaller scale) or arrange additional own capital.",
            })

    # 3. Competition
    if competition:
        c5 = competition.get("mapped_competitors_5km") or competition.get("mapped_competitors") or 0
        level = competition.get("competition_level", "low")
        if level == "high" or c5 >= 15:
            constraints.append({
                "factor": "High competition",
                "severity": "HIGH" if c5 >= 15 else "MEDIUM",
                "detail": f"{c5} mapped competitors within 5 km",
                "evidence": "Mapped competitor counts from OpenStreetMap (may be incomplete).",
                "action": "Consider alternate location or differentiated offering.",
            })
        elif level == "moderate" or c5 >= 5:
            constraints.append({
                "factor": "Moderate competition",
                "severity": "MEDIUM",
                "detail": f"{c5} mapped competitors within 5 km",
                "evidence": "Mapped competitor counts from OpenStreetMap.",
                "action": "Validate pricing power and footfall locally.",
            })

    # 4. Weak demand evidence
    if financial_plan is None and competition is None:
        pass
    # Check via data_quality or market intelligence coverage
    if market_intelligence and not market_intelligence.get("available"):
        constraints.append({
            "factor": "Weak market evidence",
            "severity": "MEDIUM",
            "detail": market_intelligence.get("availability_note") or "No verified market prices for this category",
            "evidence": "Market price rows filtered by category relevance.",
            "action": "Collect 2-3 local mandi/wholesale price points.",
        })
    elif market_intelligence and market_intelligence.get("confidence", {}).get("label") == "low":
        constraints.append({
            "factor": "Weak market evidence",
            "severity": "LOW",
            "detail": f"Market confidence is low (score {market_intelligence['confidence'].get('score', 0)})",
            "evidence": "Limited relevant commodity coverage in district.",
            "action": "Verify input costs locally.",
        })

    # 5. Low gross margin
    if monthly_economics:
        gm = monthly_economics.get("gross_margin_pct")
        cs = monthly_economics.get("cash_surplus")
        if gm is not None and gm < 10 and (cs is not None and cs < 0):
            constraints.append({
                "factor": "Low gross margin",
                "severity": "HIGH" if gm < 5 else "MEDIUM",
                "detail": f"Gross margin {gm:.1f}% with negative cash surplus ₹{cs:,.0f}",
                "evidence": f"Revenue ₹{monthly_economics.get('monthly_revenue', 0):,.0f}; COGS ₹{monthly_economics.get('cogs', 0):,.0f}",
                "action": "Re-evaluate pricing or input costs; consider higher-margin products.",
            })
        elif gm is not None and gm < 10:
            constraints.append({
                "factor": "Low gross margin",
                "severity": "LOW",
                "detail": f"Gross margin {gm:.1f}% is thin",
                "evidence": "Thin margin leaves little buffer for price swings.",
                "action": "Negotiate input costs or adjust product mix.",
            })

    # 6. High operating expenses
    if monthly_economics:
        opex = monthly_economics.get("opex") or 0
        rev = monthly_economics.get("monthly_revenue") or 1
        opex_pct = (opex / rev * 100) if rev else 0
        if opex_pct > 50:
            constraints.append({
                "factor": "High operating expenses",
                "severity": "MEDIUM",
                "detail": f"Opex is {opex_pct:.0f}% of revenue (₹{opex:,.0f})",
                "evidence": "Operating expenses include rent, staff, utilities.",
                "action": "Look for lower-rent location or leaner staffing initially.",
            })

    # 7. Poor repayment capacity
    if repayment:
        label = repayment.get("health_label") or repayment.get("label")
        coverage = repayment.get("coverage_ratio")
        emi = repayment.get("monthly_emi") or repayment.get("monthly_emi_effective") or 0
        if label == "High Risk":
            constraints.append({
                "factor": "Poor repayment capacity",
                "severity": "HIGH",
                "detail": f"EMI ₹{emi:,.0f} vs coverage ratio {coverage} — operating profit may not cover debt service",
                "evidence": "Modelled operating profit compared to monthly debt service.",
                "action": "Reduce loan amount, extend tenure, or improve operating profit before borrowing.",
            })
        elif label == "Moderate":
            constraints.append({
                "factor": "Moderate repayment capacity",
                "severity": "LOW",
                "detail": f"EMI ₹{emi:,.0f}; coverage ratio {coverage}",
                "evidence": "Repayment health is Moderate — thin buffer.",
                "action": "Maintain cost discipline and keep working-capital buffer.",
            })

    # 8. Seasonal risk
    if seasonal:
        risk = seasonal.get("cash_flow_risk")
        if risk == "HIGH":
            constraints.append({
                "factor": "Seasonal risk",
                "severity": "MEDIUM",
                "detail": "Demand swings notably across the year",
                "evidence": seasonal.get("cash_flow_risk_reason") or "Seasonal curve shows high variance.",
                "action": seasonal.get("inventory_implication") or "Hold buffer stock ahead of peak.",
            })
        elif risk == "MEDIUM":
            constraints.append({
                "factor": "Seasonal risk",
                "severity": "LOW",
                "detail": "Moderate seasonal variation",
                "evidence": "Seasonal curve shows moderate swing.",
                "action": "Plan working capital for low months.",
            })

    # 9. Accessibility
    if infrastructure:
        nm = infrastructure.get("nearest_market_km")
        nh = infrastructure.get("nearest_health_km")
        if nm is not None and nm > 15:
            constraints.append({
                "factor": "Location accessibility",
                "severity": "MEDIUM",
                "detail": f"Nearest market {nm:.1f} km away",
                "evidence": "Market distance from infrastructure points.",
                "action": "Factor transport costs; consider location closer to market hub.",
            })
        if nh is not None and nh > 15:
            constraints.append({
                "factor": "Weak health infrastructure",
                "severity": "LOW",
                "detail": f"Nearest health facility {nh:.1f} km away",
                "evidence": "Health facility proximity may affect location attractiveness.",
                "action": None,
            })

    # 10. Data confidence
    if data_quality:
        label = data_quality.get("confidence_label") or data_quality.get("label") or ""
        if label.lower() == "low":
            constraints.append({
                "factor": "Insufficient data confidence",
                "severity": "MEDIUM",
                "detail": "Data confidence is low; evidence is incomplete",
                "evidence": "; ".join((data_quality.get("reasons") or [])[:2]) or "Missing indicators.",
                "action": "Collect current local data before final decision.",
            })

    # Sort by severity: HIGH first, then MEDIUM, then LOW.
    order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    constraints.sort(key=lambda c: order.get(c["severity"], 9))

    return {
        "constraints": constraints,
        "count": len(constraints),
        "top_constraint": constraints[0] if constraints else None,
        "has_high": any(c["severity"] == "HIGH" for c in constraints),
    }
