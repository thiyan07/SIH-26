"""Six-month forecasting — hierarchy by data availability, with uncertainty."""
from __future__ import annotations

from datetime import date, timedelta
from statistics import mean, stdev

__version__ = "1.0.0"


def _add_months(d: date, n: int) -> date:
    y = d.year + (d.month - 1 + n) // 12
    m = (d.month - 1 + n) % 12 + 1
    return date(y, m, 1)


def _baseline_forecast(history: list[dict], horizon: int = 6) -> tuple[dict, str]:
    """Transparent baseline: seasonal naive or simple mean, with explicit uncertainty."""
    # history is list of {period: date, revenue, expenses, profit, cash_surplus}
    if not history:
        # No data — range estimation with wide uncertainty
        return {
            "revenue": [50000.0] * horizon,
            "expenses": [30000.0] * horizon,
            "profit": [20000.0] * horizon,
            "cash_surplus": [5000.0] * horizon,
            "demand": [50.0] * horizon,
        }, "range"

    # Extract series
    rev = [float(x.get("revenue") or 0) for x in history]
    exp = [float(x.get("expenses") or 0) for x in history]
    prof = [float(x.get("profit") or (r - e)) for x, r, e in zip(history, rev, exp)]
    cash = [float(x.get("cash_surplus") or 0) for x in history]

    n = len(history)
    if n >= 12:
        # Sufficient — trend + seasonal (simple: last 3 mean + linear trend)
        model = "statistical"
        # Trend per month (last 6 vs first 6 if n>=12 else last 3)
        recent = rev[-3:]
        older = rev[:3] if n >= 6 else rev[:1]
        trend = (mean(recent) - mean(older)) / max(1, (n - 3))
        base = mean(recent)
    elif n >= 3:
        model = "baseline"
        base = mean(rev[-3:])
        trend = 0
        # Add seasonal naive if we have 12+? already handled
    else:
        model = "range"
        base = mean(rev) if rev else 50000
        trend = 0

    # Build horizon
    out_rev, out_exp, out_prof, out_cash = [], [], [], []
    for i in range(horizon):
        r = max(0, base + trend * (i + 1))
        # Simple: expenses stable, profit = rev - exp, cash = profit - emi(assume 5000)
        e = mean(exp[-3:]) if exp else 30000
        p = r - e
        c = p - 5000  # placeholder emi; real emi from loan will override in API
        out_rev.append(round(r, 2))
        out_exp.append(round(e, 2))
        out_prof.append(round(p, 2))
        out_cash.append(round(c, 2))

    return {"revenue": out_rev, "expenses": out_exp, "profit": out_prof, "cash_surplus": out_cash, "demand": [50.0] * horizon}, model


def _uncertainty(values: list[float], model: str) -> dict:
    """p10/p50/p90. Wider for range model."""
    if not values:
        return {"p10": [], "p50": [], "p90": [], "width": "wide"}
    m = mean(values)
    try:
        sd = stdev(values) if len(values) > 1 else m * 0.2
    except Exception:
        sd = m * 0.2
    width = "narrow" if model == "statistical" else "medium" if model == "baseline" else "wide"
    factor = 0.5 if model == "statistical" else 1.0 if model == "baseline" else 1.5
    p10 = [round(max(0, v - sd * factor), 2) for v in values]
    p90 = [round(v + sd * factor, 2) for v in values]
    return {"p10": p10, "p50": values, "p90": p90, "width": width, "sd": round(sd, 2)}


def forecast_6m(
    *,
    history: list[dict],
    horizon: int = 6,
    target_from: date | None = None,
    business_type: str | None = None,
) -> dict:
    """Return forecast with horizon, model, outputs, uncertainty, and metadata."""
    if target_from is None:
        # Next month
        today = date.today()
        target_from = _add_months(date(today.year, today.month, 1), 1)

    outputs, model = _baseline_forecast(history, horizon=horizon)
    # Enrich with business-specific placeholders (AG: yield, Textile: production, etc.)
    # Keep deterministic and simple — real models can be plugged later via model_key
    if business_type == "agriculture":
        outputs["yield"] = [round(1000 + i * 10, 2) for i in range(horizon)]
        outputs["market_price"] = [round(50 + i, 2) for i in range(horizon)]
    elif business_type == "textile":
        outputs["production"] = [round(100 + i * 5, 2) for i in range(horizon)]
        outputs["raw_material_cost"] = [round(30 + i, 2) for i in range(horizon)]
    elif business_type == "restaurant":
        outputs["competition"] = [round(5 + i * 0.2, 2) for i in range(horizon)]

    # Uncertainty per metric
    uncertainty = {}
    for k, vals in outputs.items():
        if isinstance(vals, list) and vals and isinstance(vals[0], (int, float)):
            uncertainty[k] = _uncertainty(vals, model)

    target_to = _add_months(target_from, horizon - 1)
    return {
        "horizon_months": horizon,
        "model_key": model,
        "model_version": __version__,
        "target_from": target_from.isoformat(),
        "target_to": target_to.isoformat(),
        "training_from": history[0]["period"].isoformat() if history and history[0].get("period") else None,
        "training_to": history[-1]["period"].isoformat() if history else None,
        "inputs": {"history_count": len(history), "business_type": business_type},
        "outputs": outputs,
        "uncertainty": uncertainty,
        "note": "Forecast is an estimate with uncertainty, not a guarantee. Model: " + model + ".",
    }
