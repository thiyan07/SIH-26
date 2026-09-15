"""Business Health Score 0-100 — deterministic, 10 dimensions, versioned weights."""
from __future__ import annotations

from datetime import date

__version__ = "1.0.0"

DEFAULT_WEIGHTS_V1 = {
    "revenue": 0.15,
    "expense": 0.10,
    "profit": 0.15,
    "cashflow": 0.10,
    "demand": 0.10,
    "market": 0.08,
    "competition": 0.07,
    "production": 0.05,
    "repayment": 0.12,
    "forecast": 0.08,
}

WEIGHTS_VERSION = "v1"


def _score_0_100(value: float | None, good: float, bad: float, invert: bool = False) -> float:
    """Map value to 0-100: good→100, bad→0, linear, invert if lower is better (e.g. expenses)."""
    if value is None:
        return 50.0  # neutral when missing — not fabricated, but not penalized heavily
    if invert:
        # lower is better: value=bad →0, value=good→100
        if value <= good:
            return 100.0
        if value >= bad:
            return 0.0
        return max(0, min(100, 100 - (value - good) / (bad - good) * 100))
    else:
        if value >= good:
            return 100.0
        if value <= bad:
            return 0.0
        return max(0, min(100, (value - bad) / (good - bad) * 100))


def compute_health(
    *,
    revenue: float | None = None,
    revenue_prev: float | None = None,
    expenses: float | None = None,
    expenses_prev: float | None = None,
    profit: float | None = None,
    profit_prev: float | None = None,
    cash_surplus: float | None = None,
    cash_prev: float | None = None,
    demand_score: float | None = None,
    market_score: float | None = None,
    competition_level: str | None = None,
    production_pct: float | None = None,  # 0..100 capacity utilization
    repayment_health: str | None = None,  # Healthy/Moderate/High Risk
    forecast_trend: str | None = None,  # up|flat|down
    as_of: date | None = None,
    weights: dict | None = None,
) -> dict:
    w = {**DEFAULT_WEIGHTS_V1, **(weights or {})}
    dims: dict[str, dict] = {}

    # Revenue health — YoY or MoM change
    rev_change = None
    if revenue is not None and revenue_prev:
        rev_change = (revenue - revenue_prev) / revenue_prev * 100
        dims["revenue"] = {"value": revenue, "prev": revenue_prev, "change_pct": round(rev_change, 1), "score": round(_score_0_100(rev_change, 10, -20), 1)}
    else:
        dims["revenue"] = {"value": revenue, "score": round(_score_0_100(revenue, 50000, 0), 1) if revenue is not None else 50.0}

    # Expense — lower is better
    exp_change = None
    if expenses is not None and expenses_prev:
        exp_change = (expenses - expenses_prev) / expenses_prev * 100
        dims["expense"] = {"value": expenses, "change_pct": round(exp_change, 1), "score": round(_score_0_100(exp_change, -10, 20, invert=True), 1)}
    else:
        dims["expense"] = {"value": expenses, "score": 50.0 if expenses is None else round(_score_0_100(expenses, 10000, 50000, invert=True), 1)}

    # Profit
    profit_change = None
    if profit is not None and profit_prev:
        profit_change = (profit - profit_prev) / abs(profit_prev) * 100 if profit_prev else 0
        dims["profit"] = {"value": profit, "change_pct": round(profit_change, 1), "score": round(_score_0_100(profit_change, 10, -20), 1)}
    else:
        dims["profit"] = {"value": profit, "score": round(_score_0_100(profit, 20000, -5000), 1) if profit is not None else 50.0}

    # Cashflow
    dims["cashflow"] = {"value": cash_surplus, "score": round(_score_0_100(cash_surplus, 15000, -5000), 1) if cash_surplus is not None else 50.0}

    # Demand, market, competition, production, repayment, forecast — already 0..100 or mapped
    dims["demand"] = {"value": demand_score, "score": round(demand_score, 1) if demand_score is not None else 50.0}
    dims["market"] = {"value": market_score, "score": round(market_score, 1) if market_score is not None else 50.0}
    comp_map = {"low": 85, "medium": 60, "high": 35}
    dims["competition"] = {"value": competition_level, "score": comp_map.get((competition_level or "medium").lower(), 50)}
    dims["production"] = {"value": production_pct, "score": round(production_pct, 1) if production_pct is not None else 50.0}
    repay_map = {"Healthy": 90, "Moderate": 60, "High Risk": 30, "N/A": 50, None: 50}
    dims["repayment"] = {"value": repayment_health, "score": repay_map.get(repayment_health, 50)}
    forecast_map = {"up": 80, "flat": 60, "down": 30}
    dims["forecast"] = {"value": forecast_trend, "score": forecast_map.get((forecast_trend or "flat").lower(), 50)}

    # Weighted overall
    overall = sum(dims[k]["score"] * w.get(k, 0.1) for k in dims) / sum(w.get(k, 0.1) for k in dims)
    overall = max(0, min(100, round(overall, 1)))

    # Drivers — largest fall vs prev or lowest scores
    drivers: list[str] = []
    # Find biggest negative change
    changes = []
    for k in ["revenue", "expense", "profit", "cashflow"]:
        if "change_pct" in dims[k]:
            changes.append((dims[k]["change_pct"], k))
    changes.sort(key=lambda x: x[0])
    for change, k in changes[:2]:
        if k == "revenue" and change < -5:
            drivers.append(f"Revenue fell {abs(change):.0f}%")
        elif k == "expense" and change > 5:
            drivers.append(f"Operating expenses increased {change:.0f}%")
        elif k == "profit" and change < -5:
            drivers.append(f"Profit declined {abs(change):.0f}%")
        elif k == "cashflow" and dims[k]["value"] is not None and dims[k]["value"] < 0:
            drivers.append(f"Cash surplus is negative (₹{dims[k]['value']:,.0f})")
    # Add low scores
    low = sorted([(dims[k]["score"], k) for k in dims if dims[k]["score"] < 40], key=lambda x: x[0])
    for score, k in low[:1]:
        if len(drivers) < 3:
            drivers.append(f"{k.capitalize()} health is low ({score:.0f}/100)")
    if not drivers:
        # Positive case
        top = sorted([(dims[k]["score"], k) for k in dims], key=lambda x: -x[0])
        for score, k in top[:2]:
            if score >= 70:
                drivers.append(f"{k.capitalize()} is strong ({score:.0f}/100)")
    if not drivers:
        drivers.append("Steady — no major change detected")

    explanation = f"Health is {overall:.0f}/100. " + "; ".join(drivers[:3]) + "."

    return {
        "score": overall,
        "as_of": as_of.isoformat() if as_of else date.today().isoformat(),
        "dimensions": dims,
        "weights_version": WEIGHTS_VERSION,
        "drivers": drivers[:3],
        "explanation": explanation,
    }
