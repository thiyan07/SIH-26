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
# Canonical revenue derivation: Demand × Transaction × Operating Days
# ---------------------------------------------------------------------------
# Per-category operating days (realistic days business is open per month).
_OPERATING_DAYS: dict[str, int] = {
    "grocery": 30, "dairy": 30, "poultry": 26, "restaurant": 26,
    "food_processing": 26, "agriculture": 22, "manufacturing": 26,
    "textile": 26, "tailoring": 26, "handicrafts": 22, "other": 26,
    "mobile_shop": 26, "pharmacy": 30, "tea_shop": 30, "bakery": 26, "salon": 26,
}

# Per-category baseline customers/day and transaction value (ESTIMATED).
# These are conservative fallbacks when no local evidence exists.
_REVENUE_ASSUMPTIONS: dict[str, dict] = {
    "grocery":      {"customers_per_day": 40, "transaction_value": 50,  "confidence": "low", "source": "Category baseline (ESTIMATED)"},
    "dairy":        {"customers_per_day": 25, "transaction_value": 55,  "confidence": "low", "source": "Category baseline (ESTIMATED)"},
    "poultry":      {"customers_per_day": 15, "transaction_value": 90,  "confidence": "low", "source": "Category baseline (ESTIMATED)"},
    "textile":      {"customers_per_day": 8,  "transaction_value": 150, "confidence": "low", "source": "Category baseline (ESTIMATED)"},
    "tailoring":    {"customers_per_day": 5,  "transaction_value": 180, "confidence": "low", "source": "Category baseline (ESTIMATED)"},
    "restaurant":   {"customers_per_day": 35, "transaction_value": 80,  "confidence": "low", "source": "Category baseline (ESTIMATED)"},
    "food_processing": {"customers_per_day": 20, "transaction_value": 100, "confidence": "low", "source": "Category baseline (ESTIMATED)"},
    "agriculture":  {"customers_per_day": 12, "transaction_value": 140, "confidence": "low", "source": "Category baseline (ESTIMATED)"},
    "manufacturing":{"customers_per_day": 10, "transaction_value": 300, "confidence": "low", "source": "Category baseline (ESTIMATED)"},
    "handicrafts":  {"customers_per_day": 6,  "transaction_value": 140, "confidence": "low", "source": "Category baseline (ESTIMATED)"},
    "other":        {"customers_per_day": 15, "transaction_value": 70,  "confidence": "low", "source": "Category baseline (ESTIMATED)"},
}


@dataclass
class RevenueDerivation:
    customers_per_day: float
    transaction_value: float
    operating_days: int
    estimated_revenue: float
    is_estimate: bool
    confidence: str
    provenance: str
    assumptions: list[str]
    fallback_reason: str | None = None


def derive_revenue(
    category_code: str,
    *,
    customers_per_day: float | None = None,
    transaction_value: float | None = None,
    operating_days: int | None = None,
    local_evidence: dict | None = None,
) -> RevenueDerivation:
    """Canonical revenue derivation: demand × transaction × operating days.

    Evidence-aware: when local_evidence contains population / competition /
    price signals they adjust the baseline assumptions.  When evidence is
    absent we fall back to the conservative category baseline and label the
    result ESTIMATED with explicit provenance.

    Returns a RevenueDerivation that explains every assumption.
    """
    defaults = _REVENUE_ASSUMPTIONS.get(category_code, _REVENUE_ASSUMPTIONS["other"])
    base_customers = float(defaults["customers_per_day"])
    base_txn = float(defaults["transaction_value"])
    base_days = _OPERATING_DAYS.get(category_code, 26)

    # Resolve inputs or fall back to baseline.
    cpd = float(customers_per_day) if customers_per_day is not None else base_customers
    txn = float(transaction_value) if transaction_value is not None else base_txn
    days = int(operating_days) if operating_days is not None else base_days

    assumptions: list[str] = []
    is_estimate = True
    confidence = defaults["confidence"]
    provenance = defaults["source"]
    fallback_reason = None

    # LEVEL 1: User-provided values are real evidence, not estimates.
    user_provided = []
    if customers_per_day is not None:
        user_provided.append(f"User-provided customers/day: {customers_per_day}")
        is_estimate = False
        confidence = "high"
        provenance = "User-provided"
    if transaction_value is not None:
        user_provided.append(f"User-provided transaction value: ₹{transaction_value}")
        is_estimate = False
        confidence = "high"
        provenance = "User-provided"
    if operating_days is not None:
        user_provided.append(f"User-provided operating days: {operating_days}/month")
    if user_provided:
        assumptions.extend(user_provided)
        # If all three are user-provided, provenance is fully user-driven.
        if customers_per_day is not None and transaction_value is not None and operating_days is not None:
            provenance = "User-provided (all inputs)"
            fallback_reason = None

    # Evidence adjustments (deterministic, never fabricates).
    if local_evidence:
        pop = local_evidence.get("population")
        comp_5km = local_evidence.get("competitors_5km")
        price_modal = local_evidence.get("price_modal")
        # Population evidence: larger catchment -> modest demand uplift.
        if pop and pop > 0:
            # +10% customers if population >5000, capped at +30%.
            pop_factor = min(0.30, max(0, (pop - 3000) / 20000))
            if pop_factor > 0 and customers_per_day is None:
                cpd = round(cpd * (1 + pop_factor), 1)
                assumptions.append(f"Population-adjusted demand: {pop:,} catchment → customers/day adjusted by +{pop_factor*100:.0f}% (ESTIMATED).")
        # Competition: high density is treated as risk/confidence evidence.
        # Where a quantitative scenario adjustment is retained it is kept
        # conservative and labelled as a scenario assumption, not a precise
        # lost-customer count.
        if comp_5km is not None and comp_5km >= 3 and customers_per_day is None:
            comp_factor = min(0.15, comp_5km * 0.015)
            cpd = round(max(1, cpd * (1 - comp_factor)), 1)
            assumptions.append(f"Competition scenario adjustment (conservative): {comp_5km} mapped competitors within 5km → customers/day reduced by {comp_factor*100:.0f}% as a risk scenario (ESTIMATED; not a precise lost-customer count).")
        # Price evidence: if a relevant modal price exists, use it as transaction anchor.
        if price_modal and transaction_value is None:
            # Treat modal price as evidence for transaction value only when within 0.5x-2x of baseline.
            if 0.5 * base_txn <= price_modal <= 2 * base_txn:
                old_txn = txn
                txn = float(price_modal)
                is_estimate = False
                confidence = "medium"
                provenance = "Local market price evidence (modal price)"
                assumptions.append(f"Transaction value anchored to local market modal price ₹{price_modal:.0f} (was baseline ₹{old_txn:.0f}).")

    if not assumptions:
        fallback_reason = "No sufficient local evidence; using conservative category baseline (ESTIMATED)."
        assumptions.append(fallback_reason)
        assumptions.append(f"Baseline: {cpd:.0f} customers/day × ₹{txn:.0f} × {days} operating days.")
    elif user_provided and len(assumptions) == len(user_provided):
        # Only user inputs, no local evidence adjustments — still note baseline context.
        fallback_reason = None
        assumptions.append(f"Revenue: {cpd:.0f} customers/day × ₹{txn:.0f} × {days} operating days (user-provided, not estimated).")

    estimated_revenue = round(cpd * txn * days, 2)

    return RevenueDerivation(
        customers_per_day=cpd,
        transaction_value=txn,
        operating_days=days,
        estimated_revenue=estimated_revenue,
        is_estimate=is_estimate,
        confidence=confidence,
        provenance=provenance,
        assumptions=assumptions,
        fallback_reason=fallback_reason,
    )


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
    revenue_derivation: dict | None = None
    assumption: str | None = None
    confidence: str = "low"
    source: str | None = None
    fallback_reason: str | None = None


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
    customers_per_day: Optional[float] = None,
    transaction_value: Optional[float] = None,
    operating_days: Optional[int] = None,
    local_evidence: Optional[dict] = None,
) -> MonthlyEconomics:
    """Compute the full monthly cash-flow chain.

    Canonical pipeline (Phase 1):
        demand / customer estimate × expected transaction value × operating days
        → estimated revenue

        Revenue − COGS/raw material → gross profit
        Gross profit − opex → operating profit
        Operating profit − EMI → cash surplus

    Revenue derivation:
        When monthly_revenue is provided explicitly it is used verbatim.
        Otherwise it is derived via the canonical demand×price×days pipeline
        (derive_revenue) which is evidence-aware and always labelled ESTIMATED
        when falling back to category baselines.

    Defaults are ESTIMATED demo assumptions per category and are always
    labelled as such. A zero/negative revenue case never divides by zero:
    margins become 0 and break-even returns INSUFFICIENT DATA.
    """
    defaults = _ECON_DEFAULTS.get(category_code, _ECON_DEFAULTS["other"])
    derivation: RevenueDerivation | None = None
    is_estimate = True
    confidence = "low"
    source: str | None = None
    fallback_reason: str | None = None

    if monthly_revenue is not None:
        revenue = _num(monthly_revenue, defaults["monthly_revenue"])
        revenue = max(0.0, revenue)
        # Still produce derivation for explainability when evidence available.
        if local_evidence or customers_per_day or transaction_value:
            try:
                derivation = derive_revenue(
                    category_code,
                    customers_per_day=customers_per_day,
                    transaction_value=transaction_value,
                    operating_days=operating_days,
                    local_evidence=local_evidence,
                )
            except Exception:
                derivation = None
    else:
        derivation = derive_revenue(
            category_code,
            customers_per_day=customers_per_day,
            transaction_value=transaction_value,
            operating_days=operating_days,
            local_evidence=local_evidence,
        )
        revenue = derivation.estimated_revenue
        is_estimate = derivation.is_estimate
        confidence = derivation.confidence
        source = derivation.provenance
        fallback_reason = derivation.fallback_reason

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
    if derivation:
        notes.append(
            f"Revenue derived via: {derivation.customers_per_day} customers/day × ₹{derivation.transaction_value:.0f} × {derivation.operating_days} days = ₹{derivation.estimated_revenue:,.0f} (confidence: {derivation.confidence}, source: {derivation.provenance})."
        )
        for a in derivation.assumptions:
            notes.append(a)

    rev_deriv_dict = None
    if derivation:
        rev_deriv_dict = {
            "customers_per_day": derivation.customers_per_day,
            "transaction_value": derivation.transaction_value,
            "operating_days": derivation.operating_days,
            "estimated_revenue": derivation.estimated_revenue,
            "is_estimate": derivation.is_estimate,
            "confidence": derivation.confidence,
            "provenance": derivation.provenance,
            "assumptions": derivation.assumptions,
            "fallback_reason": derivation.fallback_reason,
        }

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
        is_estimate=is_estimate,
        notes=notes,
        revenue_derivation=rev_deriv_dict,
        assumption=rev_deriv_dict["assumptions"][0] if rev_deriv_dict and rev_deriv_dict.get("assumptions") else None,
        confidence=confidence,
        source=source,
        fallback_reason=fallback_reason,
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
        "revenue_derivation": e.revenue_derivation,
        "assumption": e.assumption,
        "confidence": e.confidence,
        "source": e.source,
        "fallback_reason": e.fallback_reason,
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
