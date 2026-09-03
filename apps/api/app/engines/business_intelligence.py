"""Business-intelligence engines: weather sensitivity, monthly economics,
seasonal intelligence and product recommendations.

Everything in this module is deterministic and openly labelled as
assumption-driven (ESTIMATED) where it is not reading stored real data.
It is the home for the dashboard's "intelligence" layer:

* ``weather_relevance``  — how much a business category depends on climate.
* ``monthly_economics``  — canonical revenue -> COGS -> gross -> opex ->
  operating profit -> EMI -> cash surplus chain, plus break-even.
* ``seasonal_intelligence`` — monthly demand indexes, peak/low seasons,
  seasonal cash-flow risk and the inventory/working-capital implication.
* ``recommend_products`` — what to stock / offer now, with evidence.

Guarantees (see tests):
* No division by zero anywhere; a zero-revenue business yields defined values.
* ``cash_surplus = operating_profit - emi`` (never negative by flushing).
* Every ESTIMATED output carries an explicit ``is_estimate`` / provenance tag;
  nothing is promoted to REAL.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

# ---------------------------------------------------------------------------
# Weather / climate sensitivity per category
# ---------------------------------------------------------------------------
# sensitivity: VERY HIGH / HIGH / MEDIUM / LOW
# relevant: whether weather flags should even be surfaced for this category
_WEATHER_SENSITIVITY: dict[str, dict] = {
    "agriculture":        {"sensitivity": "VERY HIGH", "relevant": True,
                           "reason": "Crop income is directly tied to rainfall, temperature and soil moisture."},
    "dairy":              {"sensitivity": "HIGH", "relevant": True,
                           "reason": "Heat raises fodder needs and milk-output/chilling pressures."},
    "poultry":            {"sensitivity": "HIGH", "relevant": True,
                           "reason": "Birds are sensitive to heat stress and disease cycling."},
    "food_processing":    {"sensitivity": "HIGH", "relevant": True,
                           "reason": "Raw-material harvest timing and cold-chain needs depend on weather."},
    "fertilizer":         {"sensitivity": "HIGH", "relevant": True,
                           "reason": "Fertiliser/seed demand follows sowing calendars and rainfall."},
    "seed_shop":          {"sensitivity": "HIGH", "relevant": True,
                           "reason": "Seed sales are timed to sowing windows driven by monsoons."},
    "animal_feed":        {"sensitivity": "MEDIUM", "relevant": True,
                           "reason": "Feed demand tracks livestock cycles; price varies with fodder."},
    "veterinary":         {"sensitivity": "MEDIUM", "relevant": True,
                           "reason": "Livestock disease incidence rises around weather extremes."},
    "vegetable_shop":     {"sensitivity": "MEDIUM", "relevant": True,
                           "reason": "Vegetable supply and prices swing with growing-season weather."},
    "fruit_shop":         {"sensitivity": "MEDIUM", "relevant": True,
                           "reason": "Fruit harvest timing and perishability vary with weather."},
    "restaurant":         {"sensitivity": "LOW", "relevant": False,
                           "reason": "Footfall varies more with local events than macro weather."},
    "grocery":            {"sensitivity": "LOW", "relevant": False,
                           "reason": "Retail demand is steady; weather has limited direct exposure."},
    "mobile_shop":        {"sensitivity": "LOW", "relevant": False,
                           "reason": "Service demand does not materially depend on climate."},
    "computer_service":   {"sensitivity": "LOW", "relevant": False,
                           "reason": "Repair demand is not climate-driven."},
    "pharmacy":           {"sensitivity": "MEDIUM", "relevant": True,
                           "reason": "Seasonal illness (fever, cold) lifts demand in weather extremes."},
    "tailoring":          {"sensitivity": "LOW", "relevant": False,
                           "reason": "Demand tracks festivals and weddings, not weather."},
    "textile":            {"sensitivity": "LOW", "relevant": False,
                           "reason": "Demand tracks festivals and weddings, not weather."},
    "manufacturing":      {"sensitivity": "MEDIUM", "relevant": True,
                           "reason": "Power availability and raw-material logistics can vary seasonally."},
    "handicrafts":        {"sensitivity": "LOW", "relevant": False,
                           "reason": "Sales track festivals and tourists, not weather."},
    "other":              {"sensitivity": "LOW", "relevant": False,
                           "reason": "No category-specific climate dependence recorded."},
}


def weather_sensitivity(category_code: str) -> dict:
    """Climate-sensitivity profile for a category (never raises)."""
    return dict(_WEATHER_SENSITIVITY.get(category_code, _WEATHER_SENSITIVITY["other"]))


def weather_applicable(category_code: str) -> bool:
    """Gate: whether weather risk flags should be surfaced for this category."""
    return _WEATHER_SENSITIVITY.get(category_code, _WEATHER_SENSITIVITY["other"])["relevant"]


def apply_weather_risk(category_code: str, weather: Optional[dict]) -> dict:
    """Attach weather risk to a category only when it is actually relevant.

    For low-relevance categories the underlying weather flags are suppressed
    (not surfaced as business risk), but the recorded data availability is
    still reported for transparency.
    """
    profile = weather_sensitivity(category_code)
    if not profile["relevant"]:
        return {
            "relevant": False,
            "sensitivity": profile["sensitivity"],
            "reason": profile["reason"],
            "available": bool(weather and weather.get("available")),
            "risk": {"factors": None, "risk_delta": 0},
            "note": "Weather flags are not surfaced for this category because "
                    "its revenue is not materially climate-dependent.",
        }
    risk = (weather or {}).get("risk", {}) or {}
    return {
        "relevant": True,
        "sensitivity": profile["sensitivity"],
        "reason": profile["reason"],
        "available": bool(weather and weather.get("available")),
        "risk": risk,
        "risk_delta": risk.get("risk_delta", 0),
        "factors": risk.get("factors"),
    }


# ---------------------------------------------------------------------------
# Monthly economics (deterministic cash-flow chain)
# ---------------------------------------------------------------------------
@dataclass
class MonthlyEconomics:
    category_code: str
    monthly_revenue: float
    cogs: float
    gross_profit: float
    gross_margin_pct: float
    opex: float
    opex_pct: float
    operating_profit: float
    operating_margin_pct: float
    emi: float
    cash_surplus: float
    cash_surplus_pct: float
    break_even_revenue: float
    break_even_state: str  # "surplus" | "deficit" | "insufficient_data"
    is_estimate: bool = True
    notes: list[str] = field(default_factory=list)


def _num(value, default=0.0):
    try:
        v = float(value)
    except (TypeError, ValueError):
        return default
    return v if math.isfinite(v) else default


def _pct(part: float, whole: float) -> float:
    """Division-free-of-zero percent."""
    if whole <= 0:
        return 0.0
    return round(part / whole * 100.0, 1)


def monthly_economics(
    category_code: str = "grocery",
    *,
    monthly_revenue: Optional[float] = None,
    cogs: Optional[float] = None,
    cogs_pct: Optional[float] = None,
    opex: Optional[float] = None,
    emi: Optional[float] = 0.0,
) -> MonthlyEconomics:
    """Compute the full monthly cash-flow chain.

    Chain (deterministic, in order):
        gross_profit       = revenue - cogs
        gross_margin_pct   = gross_profit / revenue
        operating_profit   = gross_profit - opex
        cash_surplus       = operating_profit - emi
        break_even_revenue = revenue needed so operating_profit covers EMI.

    Defaults are ESTIMATED demo assumptions per category (mirroring the profit
    engine) and are always labelled as such. A zero/negative revenue case never
    divides by zero: margins become 0 and break-even returns INSUFFICIENT DATA.
    """
    defaults = _ECON_DEFAULTS.get(category_code, _ECON_DEFAULTS["other"])
    revenue = _num(monthly_revenue, defaults["monthly_revenue"])
    revenue = max(0.0, revenue)

    if cogs is not None:
        cogs_val = _num(cogs, 0.0)
        cogs_val = max(0.0, min(cogs_val, revenue if revenue > 0 else 0.0))
    elif cogs_pct is not None:
        cp = _num(cogs_pct, defaults["cogs_pct"])
        cogs_val = revenue * cp / 100.0 if revenue > 0 else 0.0
    else:
        cogs_val = revenue * defaults["cogs_pct"] / 100.0 if revenue > 0 else 0.0

    opex_val = _num(opex, defaults["opex"])
    opex_val = max(0.0, opex_val)
    emi_val = _num(emi, 0.0)
    emi_val = max(0.0, emi_val)

    gross = revenue - cogs_val
    oper = gross - opex_val
    surplus = oper - emi_val

    # Break-even: revenue at which operating_profit >= EMI, holding the gross
    # margin and fixed opex constant. Requires a positive gross margin.
    #   operating_profit = revenue*gm - opex >= emi
    #   revenue >= (opex + emi) / gm
    break_even = None
    gm_ratio = (gross / revenue) if revenue > 0 else 0.0
    if gm_ratio > 0:
        break_even = (opex_val + emi_val) / gm_ratio
    if break_even is None or revenue <= 0:
        state = "insufficient_data"
    elif surplus >= 0:
        state = "surplus"
    else:
        state = "deficit"

    notes = [
        "Monthly economics are ESTIMATED demo assumptions, not guaranteed figures.",
        "Cash surplus = operating profit minus monthly debt service (EMI).",
    ]

    return MonthlyEconomics(
        category_code=category_code,
        monthly_revenue=round(revenue, 2),
        cogs=round(cogs_val, 2),
        gross_profit=round(gross, 2),
        gross_margin_pct=_pct(gross, revenue),
        opex=round(opex_val, 2),
        opex_pct=_pct(opex_val, revenue),
        operating_profit=round(oper, 2),
        operating_margin_pct=_pct(oper, revenue),
        emi=round(emi_val, 2),
        cash_surplus=round(surplus, 2),
        cash_surplus_pct=_pct(surplus, revenue),
        break_even_revenue=round(break_even, 2) if break_even else None,
        break_even_state=state,
        notes=notes,
    )


# Default revenue / cogs_pct / opex per category (ESTIMATED demo baselines).
_ECON_DEFAULTS: dict[str, dict] = {
    "dairy":         {"monthly_revenue": 40000.0, "cogs_pct": 60.0, "opex": 10000.0},
    "poultry":       {"monthly_revenue": 40000.0, "cogs_pct": 65.0, "opex": 9000.0},
    "grocery":       {"monthly_revenue": 60000.0, "cogs_pct": 88.0, "opex": 9000.0},
    "textile":       {"monthly_revenue": 35000.0, "cogs_pct": 55.0, "opex": 11000.0},
    "food_processing": {"monthly_revenue": 60000.0, "cogs_pct": 62.0, "opex": 14000.0},
    "restaurant":    {"monthly_revenue": 80000.0, "cogs_pct": 55.0, "opex": 22000.0},
    "agriculture":   {"monthly_revenue": 50000.0, "cogs_pct": 60.0, "opex": 10000.0},
    "manufacturing": {"monthly_revenue": 90000.0, "cogs_pct": 60.0, "opex": 22000.0},
    "handicrafts":   {"monthly_revenue": 25000.0, "cogs_pct": 35.0, "opex": 7000.0},
    "mobile_shop":   {"monthly_revenue": 45000.0, "cogs_pct": 80.0, "opex": 8000.0},
    "pharmacy":      {"monthly_revenue": 50000.0, "cogs_pct": 75.0, "opex": 9000.0},
    "tea_shop":      {"monthly_revenue": 30000.0, "cogs_pct": 45.0, "opex": 10000.0},
    "bakery":        {"monthly_revenue": 40000.0, "cogs_pct": 55.0, "opex": 12000.0},
    "salon":         {"monthly_revenue": 25000.0, "cogs_pct": 20.0, "opex": 8000.0},
    "tailoring":     {"monthly_revenue": 25000.0, "cogs_pct": 30.0, "opex": 8000.0},
    "other":         {"monthly_revenue": 30000.0, "cogs_pct": 60.0, "opex": 10000.0},
}


def monthly_economics_to_dict(e: MonthlyEconomics) -> dict:
    return {
        "category_code": e.category_code,
        "is_estimate": e.is_estimate,
        "monthly_revenue": e.monthly_revenue,
        "cogs": e.cogs,
        "gross_profit": e.gross_profit,
        "gross_margin_pct": e.gross_margin_pct,
        "opex": e.opex,
        "opex_pct": e.opex_pct,
        "operating_profit": e.operating_profit,
        "operating_margin_pct": e.operating_margin_pct,
        "emi": e.emi,
        "cash_surplus": e.cash_surplus,
        "cash_surplus_pct": e.cash_surplus_pct,
        "break_even_revenue": e.break_even_revenue,
        "break_even_state": e.break_even_state,
        "notes": e.notes,
    }


# ---------------------------------------------------------------------------
# Seasonal intelligence
# ---------------------------------------------------------------------------
# month -> 1..12, 1 = January. demand_index around 1.0 = average.
_SEASON_CURVES: dict[str, list[float]] = {
    "grocery":         [0.95, 0.95, 0.98, 0.98, 1.02, 1.02, 1.00, 1.00, 1.05, 1.08, 1.10, 1.00],
    "dairy":           [1.00, 1.00, 1.02, 1.00, 0.98, 0.96, 0.96, 0.98, 1.00, 1.02, 1.05, 1.03],
    "poultry":         [0.98, 0.98, 0.97, 0.97, 0.98, 1.00, 1.00, 1.02, 1.05, 1.08, 1.05, 1.00],
    "textile":         [1.00, 1.02, 0.95, 0.92, 1.05, 1.20, 1.00, 0.98, 1.08, 1.18, 1.10, 0.98],
    "food_processing": [0.97, 0.97, 0.98, 0.98, 1.00, 1.02, 1.05, 1.10, 1.08, 1.05, 1.00, 0.97],
    "restaurant":      [0.95, 0.95, 0.98, 1.00, 1.02, 1.02, 1.00, 1.00, 1.03, 1.05, 1.05, 1.00],
    "agriculture":     [0.85, 0.85, 0.90, 0.95, 1.00, 1.08, 1.15, 1.18, 1.15, 1.05, 0.92, 0.88],
    "manufacturing":   [0.95, 0.95, 0.98, 1.00, 1.02, 1.05, 1.05, 1.08, 1.08, 1.03, 0.98, 0.95],
    "handicrafts":     [0.85, 0.90, 0.95, 0.95, 1.00, 1.05, 1.10, 1.10, 1.20, 1.18, 1.05, 0.90],
    "mobile_shop":     [1.00, 1.00, 1.00, 1.00, 1.00, 1.00, 1.00, 1.00, 1.05, 1.05, 1.00, 1.00],
    "pharmacy":        [1.05, 1.02, 1.00, 0.98, 0.98, 1.00, 1.05, 1.08, 1.05, 1.00, 0.98, 1.03],
    "other":           [1.0] * 12,
}

# Working-capital implication: how much extra stock (as a multiple of baseline)
# is prudent to hold in the run-up to the peak. Fallback = 1.0 (no change).
_WC_BUFFER: dict[str, float] = {
    "grocery": 1.25, "textile": 1.5, "food_processing": 1.3, "agriculture": 1.4,
    "manufacturing": 1.25, "handicrafts": 1.4, "poultry": 1.2, "restaurant": 1.2,
}


def seasonal_intelligence(
    category_code: str,
    month: Optional[int] = None,
    region: Optional[str] = None,
) -> dict:
    """Build seasonal demand intelligence for a category.

    - ``curve``      : 12-month demand index (1.0 = average year).
    - ``current``    : index + label for the given month (defaults to today).
    - ``peak_month`` / ``low_month`` : turning points.
    - ``peak_month_note`` : plain-language explanation.
    - ``cash_flow_risk``  : LOW / MEDIUM / HIGH seasonal cash-flow risk with a
      reason (driven by how far the curve swings around 1.0).
    - ``inventory_implication`` : recommended working-capital / stock buffer.
    """
    curve = list(_SEASON_CURVES.get(category_code, _SEASON_CURVES["other"]))
    month = (int(month) if month is not None else None)
    if month is None:
        from datetime import datetime
        month = datetime.today().month
    month = min(12, max(1, month))

    current_index = curve[month - 1]
    current_label = _demand_label(current_index)

    peak_idx = int(max(range(12), key=lambda i: curve[i]))
    low_idx = int(min(range(12), key=lambda i: curve[i]))

    swing = max(curve) - min(curve)
    if swing >= 0.25:
        cash_flow_risk = "HIGH"
        risk_reason = "Demand swings notably across the year; working capital and cash flow are exposed to seasonal troughs."
    elif swing >= 0.1:
        cash_flow_risk = "MEDIUM"
        risk_reason = "Moderate seasonal variation; buffer stock/credit care is advisable before peaks."
    else:
        cash_flow_risk = "LOW"
        risk_reason = "Demand is broadly stable through the year."

    buffer = _WC_BUFFER.get(category_code, 1.0)
    peak_index = curve[peak_idx]
    if peak_index > 1.0:
        inventory_note = (
            f"Demand peaks in month {peak_idx + 1} at {peak_index:.2f}x the average. "
            f"Holding up to a {buffer:.2f}x stock buffer before the peak is prudent "
            f"to avoid stockouts and protect margins."
        )
    else:
        inventory_note = "Demand is stable; maintain a routine working-capital buffer."

    seasonal_recommendation = _seasonal_recommendation(category_code, month, current_index)

    return {
        "category_code": category_code,
        "region": region,
        "curve": [round(x, 2) for x in curve],
        "current_month": month,
        "current_index": round(current_index, 2),
        "current_label": current_label,
        "peak_month": peak_idx + 1,
        "peak_index": round(peak_index, 2),
        "low_month": low_idx + 1,
        "low_index": round(curve[low_idx], 2),
        "cash_flow_risk": cash_flow_risk,
        "cash_flow_risk_reason": risk_reason,
        "inventory_implication": inventory_note,
        "stock_buffer_factor": buffer,
        "recommendation": seasonal_recommendation,
        "is_estimate": True,
        "note": "Seasonal indexes are ESTIMATED demo patterns, not measured sales data. "
                "Verify against the business's own records.",
    }


def _demand_label(index: float) -> str:
    if index >= 1.10:
        return "PEAK"
    if index >= 1.03:
        return "HIGH"
    if index <= 0.92:
        return "LOW"
    if index <= 0.98:
        return "SOFT"
    return "AVERAGE"


def _seasonal_recommendation(category_code: str, month: int, index: float) -> str:
    label = _demand_label(index)
    name = category_code.replace("_", " ").title()
    if label in ("PEAK", "HIGH"):
        return (f"{name} is in a {label.lower()} demand window now (index {index:.2f}). "
                f"Stock up, staff accordingly, and protect margins rather than discounting.")
    if label in ("SOFT", "LOW"):
        return (f"{name} demand is {label.lower()} right now (index {index:.2f}). "
                f"Trim stock, control costs, and focus on credit collection until the next peak.")
    return (f"{name} demand is average this month (index {index:.2f}). "
            f"Maintain routine stock and prepare working capital ahead of the peak month.")


# ---------------------------------------------------------------------------
# Product recommendation engine
# ---------------------------------------------------------------------------
@dataclass
class ProductRecommendation:
    product: str
    relevance: str  # high | medium | low
    reason: str
    confidence: str  # high | medium | low
    evidence: str
    season: Optional[str] = None


_PRODUCT_CATALOG: dict[str, list[dict]] = {
    "grocery": [
        {"product": "Festive essentials (oils, grains, sweets)", "season": "festival",
         "relevance": "high", "reason": "Edible-oil and grain demand spikes with festival and wedding season.",
         "confidence": "medium", "evidence": "Seasonal festival demand pattern (ESTIMATED demo)."},
        {"product": "Fresh milk & dairy", "season": "year-round",
         "relevance": "high", "reason": "Steady daily repeat purchase anchors regular footfall.",
         "confidence": "high", "evidence": "Consistent everyday-consumer demand (ESTIMATED demo)."},
        {"product": "Packaged snacks & beverages", "season": "summer",
         "relevance": "medium", "reason": "Cold drinks and snacks sell well in summer and exam season.",
         "confidence": "medium", "evidence": "Seasonal consumption pattern (ESTIMATED demo)."},
    ],
    "dairy": [
        {"product": "Curd & paneer", "season": "summer",
         "relevance": "high", "reason": "Cooling dairy products see rising demand in hot months.",
         "confidence": "medium", "evidence": "Seasonal consumption pattern (ESTIMATED demo)."},
        {"product": "Ghee (festive)", "season": "festival",
         "relevance": "medium", "reason": "Ghee demand lifts around festivals and weddings.",
         "confidence": "medium", "evidence": "Festival demand pattern (ESTIMATED demo)."},
    ],
    "textile": [
        {"product": "Festive & wedding wear", "season": "wedding/festival",
         "relevance": "high", "reason": "Clothing demand peaks sharply before marriages and festivals.",
         "confidence": "high", "evidence": "Strong pre-wedding/festival demand cycle (ESTIMATED demo)."},
        {"product": "School uniforms", "season": "back-to-school",
         "relevance": "medium", "reason": "Uniform demand spikes at the start of the school year.",
         "confidence": "medium", "evidence": "Back-to-school cycle (ESTIMATED demo)."},
    ],
    "agriculture": [
        {"product": "Sowing-season seeds & inputs", "season": "pre-monsoon",
         "relevance": "high", "reason": "Seed and input sales concentrate ahead of the sowing window.",
         "confidence": "high", "evidence": "Sowing-calendar demand (ESTIMATED demo)."},
        {"product": "Post-harvest storage & packaging", "season": "harvest",
         "relevance": "medium", "reason": "Storage and packing needs rise at harvest time.",
         "confidence": "medium", "evidence": "Harvest-cycle demand (ESTIMATED demo)."},
    ],
    "other": [
        {"product": "Core service / core product", "season": "year-round",
         "relevance": "medium", "reason": "Focus on consistent core offering with a modest seasonal buffer.",
         "confidence": "low", "evidence": "No category-specific product data (ESTIMATED demo)."},
    ],
}


def recommend_products(
    category_code: str,
    season: Optional[str] = None,
    month: Optional[int] = None,
) -> list[dict]:
    """Recommend products to stock/offer, each with relevance/reason/confidence/evidence."""
    catalog = _PRODUCT_CATALOG.get(category_code, _PRODUCT_CATALOG["other"])
    recs = [dict(x) for x in catalog]
    for r in recs:
        r["is_estimate"] = True
        r["provenance"] = "ESTIMATED"
    return recs
