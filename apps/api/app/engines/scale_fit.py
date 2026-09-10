"""Business scale fit — which scale best matches the entrepreneur's capital.

Direct outcome of project-cost + financial-fit + profitability calculations;
no generic recommendation engine.
"""
from __future__ import annotations


def evaluate_scale_fit(
    category_code: str,
    capital_available: float,
    scales: tuple[str, ...] = ("micro", "small", "medium"),
    location_factor: float = 1.0,
) -> dict:
    """Evaluate each scale and recommend the best fit."""
    from app.engines.business_intelligence import monthly_economics
    from app.engines.cost_templates import get_total_template_cost
    from app.engines.finance import derive_financial_plan
    from app.engines.repayment import build_schedule, repayment_health

    results: list[dict] = []
    for scale in scales:
        try:
            project_cost = get_total_template_cost(category_code, scale, location_factor)
        except Exception:
            continue
        plan = derive_financial_plan(project_cost, capital_available)
        loan = plan.loan_amount
        emi = 0.0
        health_label = "N/A"
        coverage = None
        cash_surplus = None
        operating_profit = None
        # Get modelled economics for this scale's revenue baseline.
        # We use the generic revenue baseline per category; scale influences project_cost only here.
        try:
            econ = monthly_economics(category_code, emi=0)
            operating_profit = econ.operating_profit
            # If loan exists, compute EMI and cash surplus.
            if plan.scheme and loan > 0:
                sched = build_schedule(loan, plan.scheme.interest_rate, plan.scheme.tenure_years,
                                       plan.scheme.moratorium_months, plan.scheme.moratorium_mode)
                emi = sched.monthly_emi_effective
                h = repayment_health(operating_profit, emi)
                health_label = h["label"]
                coverage = h["coverage_ratio"]
                cash_surplus = operating_profit - emi
            else:
                health_label = "Healthy" if capital_available >= project_cost else "N/A"
                coverage = None
                cash_surplus = operating_profit
        except Exception:
            health_label = "unknown"

        # Fit score: higher is better. Penalise large gap, high financing, poor health.
        required_fin = plan.required_financing
        gap_ratio = (required_fin / project_cost) if project_cost else 1
        health_penalty = {"Healthy": 0, "Moderate": 0.15, "High Risk": 0.40, "N/A": 0}.get(health_label, 0.2)
        fit = max(0, 100 - gap_ratio * 50 - health_penalty * 100 - (plan.shortfall / project_cost * 100 if project_cost and plan.shortfall else 0))

        results.append({
            "scale": scale,
            "project_cost": round(project_cost, 2),
            "capital_available": round(capital_available, 2),
            "required_financing": round(required_fin, 2),
            "loan_amount": round(loan, 2),
            "shortfall": round(plan.shortfall, 2),
            "emi": round(emi, 2),
            "repayment_health": health_label,
            "coverage_ratio": coverage,
            "cash_surplus": round(cash_surplus, 2) if cash_surplus is not None else None,
            "operating_profit": round(operating_profit, 2) if operating_profit is not None else None,
            "fit_score": round(fit, 1),
            "scheme": plan.scheme.code if plan.scheme else None,
            "notes": plan.notes[:2],
        })

    # Rank by fit_score (higher is better), then prefer smaller scale on ties.
    results.sort(key=lambda r: (-r["fit_score"], r["project_cost"]))

    recommended = results[0]["scale"] if results else None
    reason = None
    if recommended and results:
        best = results[0]
        if best["repayment_health"] == "Healthy":
            reason = f"{recommended} scale fits capital ₹{capital_available:,.0f} with healthy repayment (gap ₹{best['required_financing']:,.0f})."
        elif best["repayment_health"] == "Moderate":
            reason = f"{recommended} scale is the best compromise; repayment is moderate — monitor cash flow."
        else:
            reason = f"{recommended} scale is the least constrained, but repayment health is {best['repayment_health']} — consider increasing capital or alternate category."

    return {
        "category_code": category_code,
        "capital_available": round(capital_available, 2),
        "scales": results,
        "recommended_scale": recommended,
        "reason": reason,
        "note": "Direct outcome of project-cost, financing gap, and repayment health calculations.",
    }
