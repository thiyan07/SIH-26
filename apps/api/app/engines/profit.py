"""Category-specific business profit simulator.

Deterministic operating model. Outputs are labelled "Estimated operating
model" — never guaranteed profit. Users can change assumptions (what-if).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

# Category → inputs schema + default inputs + formulas.
# These are demo assumptions (is_estimate=True) and clearly labelled.


@dataclass
class ModelResult:
    category_code: str
    inputs: dict[str, float]
    outputs: dict[str, float]
    is_estimate: bool = True
    label: str = "Estimated operating model"
    notes: list[str] = field(default_factory=list)


def _clamp(value, default, minimum=0.0):
    try:
        v = float(value)
    except (TypeError, ValueError):
        return default
    return max(v, minimum)


DAIRY_DEFAULTS = {
    "number_of_animals": 2.0,
    "milk_per_animal_per_day": 6.0,   # litres
    "selling_price": 40.0,            # ₹/litre
    "feed_cost": 120.0,               # ₹/animal/day
    "labour_cost": 3000.0,            # ₹/month
    "electricity": 500.0,
    "transportation": 1500.0,
    "maintenance": 800.0,
    "veterinary_cost": 600.0,
    "other_operating_cost": 1000.0,
}


def _dairy(inputs, defaults=None):
    animals = _clamp(inputs.get("number_of_animals"), DAIRY_DEFAULTS["number_of_animals"])
    litres_per_day = _clamp(inputs.get("milk_per_animal_per_day"), DAIRY_DEFAULTS["milk_per_animal_per_day"])
    price = _clamp(inputs.get("selling_price"), DAIRY_DEFAULTS["selling_price"])
    per_animal_daily_cost = _clamp(inputs.get("feed_cost"), DAIRY_DEFAULTS["feed_cost"])

    daily_milk = animals * litres_per_day
    daily_revenue = daily_milk * price
    monthly_revenue = daily_revenue * 30

    # monthly operating cost
    monthly_costs = {
        "feed": per_animal_daily_cost * animals * 30,
        "labour": _clamp(inputs.get("labour_cost"), DAIRY_DEFAULTS["labour_cost"]),
        "electricity": _clamp(inputs.get("electricity"), DAIRY_DEFAULTS["electricity"]),
        "transportation": _clamp(inputs.get("transportation"), DAIRY_DEFAULTS["transportation"]),
        "maintenance": _clamp(inputs.get("maintenance"), DAIRY_DEFAULTS["maintenance"]),
        "veterinary": _clamp(inputs.get("veterinary_cost"), DAIRY_DEFAULTS["veterinary_cost"]),
        "other": _clamp(inputs.get("other_operating_cost"), DAIRY_DEFAULTS["other_operating_cost"]),
    }
    monthly_operating_cost = sum(monthly_costs.values())
    monthly_operating_profit = monthly_revenue - monthly_operating_cost

    outputs = {
        "daily_revenue": round(daily_revenue, 2),
        "monthly_revenue": round(monthly_revenue, 2),
        "monthly_operating_cost": round(monthly_operating_cost, 2),
        "estimated_monthly_operating_profit": round(monthly_operating_profit, 2),
        "operating_margin_pct": round(
            (monthly_operating_profit / monthly_revenue * 100) if monthly_revenue else 0.0, 1
        ),
    }
    return {
        "cost_breakdown": {k: round(v, 2) for k, v in monthly_costs.items()},
        **outputs,
    }


def _grocery(inputs, defaults=None):
    monthly_sales = _clamp(inputs.get("monthly_sales"), 60000.0)
    margin_pct = _clamp(inputs.get("margin_pct"), 12.0)
    rent = _clamp(inputs.get("rent"), 3000.0)
    staff = _clamp(inputs.get("staff_cost"), 5000.0)
    utilities = _clamp(inputs.get("utilities"), 1000.0)
    other = _clamp(inputs.get("other_operating_cost"), 2000.0)

    gross_profit = monthly_sales * (margin_pct / 100.0)
    monthly_operating_cost = rent + staff + utilities + other
    monthly_profit = gross_profit - monthly_operating_cost

    outputs = {
        "daily_revenue": round(monthly_sales / 30, 2),
        "monthly_revenue": round(monthly_sales, 2),
        "monthly_operating_cost": round(monthly_operating_cost, 2),
        "estimated_monthly_operating_profit": round(monthly_profit, 2),
        "operating_margin_pct": round(margin_pct, 1),
    }
    return {"cost_breakdown": {"rent": rent, "staff": staff, "utilities": utilities, "other": other}, **outputs}


def _generic(inputs, defaults=None):
    """Generic service business: monthly revenue minus operating costs."""
    monthly_revenue = _clamp(inputs.get("monthly_revenue"), defaults.get("monthly_revenue", 30000.0) if defaults else 30000.0)
    operating_cost = _clamp(inputs.get("monthly_operating_cost"), defaults.get("monthly_operating_cost", 15000.0))
    profit = monthly_revenue - operating_cost
    return {
        "cost_breakdown": {"monthly_operating_cost": round(operating_cost, 2)},
        "daily_revenue": round(monthly_revenue / 30, 2),
        "monthly_revenue": round(monthly_revenue, 2),
        "monthly_operating_cost": round(operating_cost, 2),
        "estimated_monthly_operating_profit": round(profit, 2),
        "operating_margin_pct": round((profit / monthly_revenue * 100) if monthly_revenue else 0.0, 1),
    }


_MODELS = {
    "dairy": {
        "name": "Dairy",
        "inputs_schema": list(DAIRY_DEFAULTS.keys()),
        "defaults": DAIRY_DEFAULTS,
        "fn": _dairy,
    },
    "poultry": {
        "name": "Poultry",
        "inputs_schema": ["number_of_birds", "monthly_revenue", "monthly_operating_cost"],
        "defaults": {"number_of_birds": 200.0, "monthly_revenue": 40000.0, "monthly_operating_cost": 28000.0},
        "fn": _generic,
    },
    "grocery": {
        "name": "Grocery/Retail",
        "inputs_schema": ["monthly_sales", "margin_pct", "rent", "staff_cost", "utilities", "other_operating_cost"],
        "defaults": {
            "monthly_sales": 60000.0,
            "margin_pct": 12.0,
            "rent": 3000.0,
            "staff_cost": 5000.0,
            "utilities": 1000.0,
            "other_operating_cost": 2000.0,
        },
        "fn": _grocery,
    },
    "textile": {
        "name": "Textile/Tailoring",
        "inputs_schema": ["monthly_revenue", "monthly_operating_cost"],
        "defaults": {"monthly_revenue": 35000.0, "monthly_operating_cost": 18000.0},
        "fn": _generic,
    },
    "food_processing": {
        "name": "Food Processing",
        "inputs_schema": ["monthly_revenue", "monthly_operating_cost"],
        "defaults": {"monthly_revenue": 60000.0, "monthly_operating_cost": 42000.0},
        "fn": _generic,
    },
    "restaurant": {
        "name": "Restaurant/Food Service",
        "inputs_schema": ["monthly_revenue", "monthly_operating_cost"],
        "defaults": {"monthly_revenue": 80000.0, "monthly_operating_cost": 56000.0},
        "fn": _generic,
    },
    "agriculture": {
        "name": "Agriculture-related",
        "inputs_schema": ["monthly_revenue", "monthly_operating_cost"],
        "defaults": {"monthly_revenue": 50000.0, "monthly_operating_cost": 35000.0},
        "fn": _generic,
    },
    "manufacturing": {
        "name": "Small Manufacturing",
        "inputs_schema": ["monthly_revenue", "monthly_operating_cost"],
        "defaults": {"monthly_revenue": 90000.0, "monthly_operating_cost": 68000.0},
        "fn": _generic,
    },
    "handicrafts": {
        "name": "Handicrafts",
        "inputs_schema": ["monthly_revenue", "monthly_operating_cost"],
        "defaults": {"monthly_revenue": 25000.0, "monthly_operating_cost": 12000.0},
        "fn": _generic,
    },
    "other": {
        "name": "Other",
        "inputs_schema": ["monthly_revenue", "monthly_operating_cost"],
        "defaults": {"monthly_revenue": 30000.0, "monthly_operating_cost": 18000.0},
        "fn": _generic,
    },
}

# OSM tag mapping for competitor detection per category
CATEGORY_OSM_TAGS = {
    "dairy": [{"shop": "dairy"}, {"shop": "dairy_farm"}],
    "poultry": [{"shop": "poultry"}, {"farm": "poultry"}],
    "grocery": [{"shop": "convenience"}, {"shop": "general"}, {"shop": "grocery"}],
    "textile": [{"shop": "tailor"}, {"shop": "clothes"}, {"craft": "textile"}],
    "food_processing": [{"craft": None, "man_made": None}],  # heuristic; ingest requires a food keyword
    "restaurant": [{"amenity": "restaurant"}],
    "agriculture": [{"shop": "farm"}, {"landuse": "farmland"}],
    "manufacturing": [{"man_made": "works"}, {"industrial": "factory"}],
    "handicrafts": [{"craft": "handicraft"}, {"shop": "art"}],
    "other": [],
}


def simulate_model(category_code: str, inputs: Optional[dict[str, Any]] = None) -> ModelResult:
    """Run a category's operating model with provided (or default) inputs."""
    model = _MODELS.get(category_code)
    if model is None:
        raise ValueError(f"unknown category_code: {category_code}")

    merged = dict(model["defaults"])
    if inputs:
        for k, v in inputs.items():
            if k in model["inputs_schema"]:
                merged[k] = v

    outputs_raw = model["fn"](dict(merged), model["defaults"])
    notes = [
        "Outputs are an estimated operating model, not guaranteed profit.",
        "Default assumptions are demo estimates (is_estimate=True).",
    ]
    return ModelResult(
        category_code=category_code,
        inputs=merged,
        outputs=outputs_raw,
        notes=notes,
    )


def model_inputs_schema(category_code: str) -> dict:
    model = _MODELS.get(category_code)
    if model is None:
        return {"inputs_schema": [], "defaults": {}}
    return {"inputs_schema": model["inputs_schema"], "defaults": model["defaults"]}


def known_categories() -> list[dict]:
    return [
        {"code": "dairy", "name": "Dairy"},
        {"code": "poultry", "name": "Poultry"},
        {"code": "grocery", "name": "Grocery/Retail"},
        {"code": "textile", "name": "Textile/Tailoring"},
        {"code": "food_processing", "name": "Food Processing"},
        {"code": "restaurant", "name": "Restaurant/Food Service"},
        {"code": "agriculture", "name": "Agriculture-related enterprise"},
        {"code": "manufacturing", "name": "Small manufacturing"},
        {"code": "handicrafts", "name": "Handicrafts"},
        {"code": "other", "name": "Other"},
    ]
