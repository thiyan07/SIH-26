"""Early warning engine — deterministic rules, not LLM."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

__version__ = "1.0.0"

# Severity mapping
SEVERITY_LOW = "LOW"
SEVERITY_MEDIUM = "MEDIUM"
SEVERITY_HIGH = "HIGH"
SEVERITY_CRITICAL = "CRITICAL"


def evaluate_risks(
    *,
    business_id: str,
    metrics: dict[str, Any],  # {revenue, revenue_prev, profit, profit_prev, expenses, expenses_prev, cash_surplus, demand_score, competition_count, competition_prev, market_score, emi, forecast_trend}
    business_type: str | None = None,
    as_of: datetime | None = None,
) -> list[dict]:
    """Return list of risk dicts — each with type, severity, metrics, threshold, explanation, action."""
    now = as_of or datetime.now(timezone.utc)
    alerts: list[dict] = []

    def _add(alert_type: str, severity: str, metrics: dict, threshold: dict, explanation: str, action: str):
        dedupe_key = f"{business_id}:{alert_type}:{severity}:{now.date().isoformat()}"
        # Use date-level dedupe — prevents daily dupes for same underlying event
        alerts.append({
            "alert_type": alert_type,
            "severity": severity,
            "detected_at": now,
            "metrics": metrics,
            "threshold": threshold,
            "explanation": explanation,
            "recommended_action": action,
            "dedupe_key": dedupe_key,
            "model_version": __version__,
        })

    rev = metrics.get("revenue")
    rev_prev = metrics.get("revenue_prev")
    profit = metrics.get("profit")
    profit_prev = metrics.get("profit_prev")
    exp = metrics.get("expenses")
    exp_prev = metrics.get("expenses_prev")
    cash = metrics.get("cash_surplus")
    demand = metrics.get("demand_score")
    comp = metrics.get("competition_count")
    comp_prev = metrics.get("competition_prev")
    emi = metrics.get("emi")
    forecast_trend = metrics.get("forecast_trend")

    # 1. Sustained revenue decline (>10% MoM, or >15% over 2 months if we had history)
    if rev is not None and rev_prev and rev_prev > 0:
        change = (rev - rev_prev) / rev_prev * 100
        if change <= -15:
            _add("revenue_decline", SEVERITY_HIGH, {"revenue": rev, "prev": rev_prev, "change_pct": round(change,1)}, {"threshold": -10}, f"Revenue declined {abs(change):.0f}% (₹{rev_prev:,.0f} → ₹{rev:,.0f}).", "Review pricing, demand, and market gaps; consider a smaller production batch.")
        elif change <= -8:
            _add("revenue_decline", SEVERITY_MEDIUM, {"revenue": rev, "prev": rev_prev, "change_pct": round(change,1)}, {"threshold": -10}, f"Revenue fell {abs(change):.0f}%.", "Check sales channels and competitor activity.")

    # 2. Profit decline
    if profit is not None and profit_prev and profit_prev != 0:
        change = (profit - profit_prev) / abs(profit_prev) * 100
        if change <= -20:
            _add("profit_decline", SEVERITY_HIGH, {"profit": profit, "prev": profit_prev, "change_pct": round(change,1)}, {"threshold": -10}, f"Profit declined {abs(change):.0f}%.", "Cut non-essential expenses and revisit pricing.")

    # 3. Expense increase
    if exp is not None and exp_prev and exp_prev > 0:
        change = (exp - exp_prev) / exp_prev * 100
        if change >= 12:
            _add("expense_increase", SEVERITY_MEDIUM, {"expenses": exp, "prev": exp_prev, "change_pct": round(change,1)}, {"threshold": 10}, f"Operating expenses increased {change:.0f}%.", "Audit recurring costs; negotiate supplier rates.")

    # 4. Negative cash flow
    if cash is not None and cash < 0:
        sev = SEVERITY_CRITICAL if cash < -10000 else SEVERITY_HIGH if cash < -5000 else SEVERITY_MEDIUM
        _add("negative_cashflow", sev, {"cash_surplus": cash}, {"threshold": 0}, f"Cash surplus is negative (₹{cash:,.0f}).", "Tighten working capital and defer non-urgent inventory.")

    # 5. EMI stress — cash vs EMI
    if cash is not None and emi and emi > 0:
        coverage = cash / emi if emi else 0
        if cash < emi:
            sev = SEVERITY_CRITICAL if coverage < 0.5 else SEVERITY_HIGH
            _add("emi_stress", sev, {"cash_surplus": cash, "emi": emi, "coverage": round(coverage,2)}, {"threshold": 1.0}, f"Projected surplus ₹{cash:,.0f} may not cover EMI ₹{emi:,.0f} (coverage {coverage:.1f}x).", "Discuss tenure extension or lower loan with lender; reduce opex.")

    # 6. Competition increase
    if comp is not None and comp_prev is not None and comp > comp_prev:
        inc = comp - comp_prev
        if inc >= 3:
            _add("competition_increase", SEVERITY_MEDIUM, {"competition": comp, "prev": comp_prev, "increase": inc}, {"threshold": 2}, f"Nearby competitors increased by {inc} ({comp_prev}→{comp}).", "Differentiate offering or test an underserved category.")

    # 7. Demand decline (if demand_score available)
    if demand is not None and demand < 40:
        sev = SEVERITY_HIGH if demand < 30 else SEVERITY_MEDIUM
        _add("demand_decline", sev, {"demand_score": demand}, {"threshold": 40}, f"Demand health is low ({demand:.0f}/100).", "Check market gaps and local purchasing power signals.")

    # 8. Worsening forecast
    if forecast_trend == "down":
        _add("forecast_worsening", SEVERITY_MEDIUM, {"forecast_trend": forecast_trend}, {"threshold": "flat"}, "Forecast trend is downward.", "Prepare buffer stock and conserve cash for the low month.")

    # 9. Abnormal change — sudden >30% revenue swing
    if rev is not None and rev_prev and abs((rev - rev_prev) / rev_prev) > 0.3:
        _add("abnormal_change", SEVERITY_MEDIUM, {"revenue": rev, "prev": rev_prev}, {"threshold": 0.3}, "Sudden abnormal business change detected (>30% swing).", "Verify data entry and investigate cause (season, supply, price).")

    return alerts
