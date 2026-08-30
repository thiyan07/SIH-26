"""DB-backed category profiles (plan §14).

Each business category carries operating intelligence that used to live only
in engine code: required inputs, demand-signal codes, direct competitor
categories, cost/revenue components, risk factors and seasonality. The
canonical registry below is seeded into `business_categories` by
`scripts/db/init_schema.py`; `get_category_profile()` reads the DB row first
and falls back to the registry when a table hasn't been seeded or a field is
empty, mirroring the scheme-routing pattern in `app/api/financial.py`.
"""
from __future__ import annotations

from sqlalchemy import select

from app.db.models import BusinessCategory
from app.engines.market import DEFAULT_SIGNAL_CODES
from app.engines.profit import _MODELS, CATEGORY_OSM_TAGS, known_categories

PROFILE_FIELDS = (
    "required_inputs",
    "demand_signals",
    "competition_categories",
    "cost_components",
    "revenue_components",
    "risk_factors",
    "seasonality",
)

_DEFAULT_SIGNALS = list(DEFAULT_SIGNAL_CODES)


def _expected_cost_items(code: str) -> list[str]:
    if code == "dairy":
        return ["feed_cost", "labour_cost", "electricity", "transportation",
                "maintenance", "veterinary_cost", "other_operating_cost"]
    if code == "grocery":
        return ["rent", "staff_cost", "utilities", "other_operating_cost"]
    return ["monthly_operating_cost"]


def _expected_revenue_items(code: str) -> list[str]:
    if code == "dairy":
        return ["milk_sales"]
    if code == "grocery":
        return ["monthly_sales"]
    return ["monthly_revenue"]


def _competitors(code: str) -> list[str]:
    return {
        "dairy": ["dairy"],
        "poultry": ["poultry"],
        "grocery": ["grocery"],
        "textile": ["textile"],
        "food_processing": ["food_processing"],
        "restaurant": ["restaurant", "food_processing"],
        "agriculture": ["agriculture"],
        "manufacturing": ["manufacturing"],
        "handicrafts": ["handicrafts", "textile"],
        "other": [],
    }[code]


def _risk_factors(code: str) -> list[dict]:
    return {
        "dairy": [
            {"factor": "Fodder & feed price volatility", "level": "medium",
             "note": "Feed is a large share of dairy operating cost and prices move seasonally."},
            {"factor": "Milk spoilage / cold-chain", "level": "medium",
             "note": "Unpasteurised milk spoils fast; requires daily collection and chilling."},
        ],
        "poultry": [
            {"factor": "Bird disease risk", "level": "medium",
             "note": "Outbreaks can wipe flocks; biosecurity and veterinary support matter."},
            {"factor": "Feed price volatility", "level": "medium",
             "note": "Poultry feed is the dominant cost and is commodity-priced."},
        ],
        "grocery": [
            {"factor": "Thin margins", "level": "medium",
             "note": "Retail grocery operates on small per-item margins; volume matters."},
            {"factor": "Credit risk to regulars", "level": "medium",
             "note": "Popular book-credit practice can strain working capital."},
        ],
        "textile": [
            {"factor": "Fashion-cycle demand", "level": "medium",
             "note": "Demand shifts with seasons and festivals; inventory can stale."},
            {"factor": "Skilled labour turnover", "level": "medium",
             "note": "Tailoring quality depends on trained staff."},
        ],
        "food_processing": [
            {"factor": "Raw-material seasonality", "level": "medium",
             "note": "Agricultural raw inputs are harvested seasonally; storage needed."},
            {"factor": "Perishability", "level": "medium",
             "note": "Finished product shelf life limits distribution distance."},
        ],
        "restaurant": [
            {"factor": "High operating leverage", "level": "medium",
             "note": "Rent, staff and utilities are fixed; slow periods still cost money."},
            {"factor": "Footfall dependence", "level": "medium",
             "note": "Revenue closely tracks local footfall and competition."},
        ],
        "agriculture": [
            {"factor": "Weather risk", "level": "medium",
             "note": "Rainfall variability directly affects yields and incomes."},
            {"factor": "Price realisation risk", "level": "medium",
             "note": "Farm-gate prices can diverge from mandi prices at harvest."},
        ],
        "manufacturing": [
            {"factor": "Working-capital intensity", "level": "medium",
             "note": "Raw material batches and receivable delays tie up cash."},
            {"factor": "Power dependence", "level": "medium",
             "note": "Production is sensitive to power availability and cost."},
        ],
        "handicrafts": [
            {"factor": "Local-market saturation", "level": "medium",
             "note": "Craft demand is niche; relies on buyers / tourism."},
            {"factor": "Slow inventory turnover", "level": "medium",
             "note": "Artisan output sells slowly; cash can be locked in stock."},
        ],
        "other": [
            {"factor": "Category-specific risk", "level": "unknown",
             "note": "No profile data; assess per venture."},
        ],
    }[code]


def _seasonality(code: str) -> dict:
    return {
        "dairy": {"note": "Milk output and demand are relatively steady year-round.",
                  "considerations": ["Summer output dip", "Festival demand bumps"]},
        "poultry": {"note": "Egg and meat demand peaks around festivals.",
                    "considerations": ["Festival peaks", "Feed cost cycles"]},
        "grocery": {"note": "Retail demand lifts with festivals and harvest income.",
                    "considerations": ["Festival peaks", "Post-harvest village income"]},
        "textile": {"note": "Tailoring/clothing demand peaks before festivals and weddings.",
                    "considerations": ["Wedding/festival season", "Back-to-school"]},
        "food_processing": {"note": "Input availability follows harvest seasons.",
                            "considerations": ["Harvest timing", "Festival consumption peaks"]},
        "restaurant": {"note": "Footfall varies with festivals and local events.",
                       "considerations": ["Festival peaks", "Lean weekday periods"]},
        "agriculture": {"note": "Income is concentrated around harvests.",
                        "considerations": ["Monsoon dependence", "Harvest-season cash inflow"]},
        "manufacturing": {"note": "Demand often mirrors agricultural seasons for rural buyers.",
                          "considerations": ["Post-harvest demand", "Pre-festival orders"]},
        "handicrafts": {"note": "Craft sales peak ahead of festivals and tourist seasons.",
                        "considerations": ["Festival demand", "Tourist season"]},
        "other": {"note": "No category-specific seasonality recorded.",
                  "considerations": []},
    }[code]


def build_category_profiles() -> dict[str, dict]:
    """Assemble the canonical registry (names follow `known_categories()`)."""
    profiles = {}
    for entry in known_categories():
        code, name = entry["code"], entry["name"]
        model = _MODELS.get(code, {})
        profiles[code] = {
            "code": code,
            "name": name,
            "description": model.get("name", name),
            "required_inputs": list(model.get("inputs_schema", [])),
            "default_inputs": model.get("defaults", {}),
            "demand_signals": list(_DEFAULT_SIGNALS),
            "competition_categories": _competitors(code),
            "cost_components": _expected_cost_items(code),
            "revenue_components": _expected_revenue_items(code),
            "risk_factors": _risk_factors(code),
            "seasonality": _seasonality(code),
            "osm_tags": CATEGORY_OSM_TAGS.get(code, []),
        }
    return profiles


CATEGORY_PROFILES = build_category_profiles()


def seed_category_profiles(db) -> int:
    """Upsert profile fields onto business_categories rows (idempotent)."""
    n = 0
    for code, profile in CATEGORY_PROFILES.items():
        row = db.execute(select(BusinessCategory).where(BusinessCategory.code == code)).scalars().first()
        if row is None:
            row = BusinessCategory(code=code, name=profile["name"], description=profile["description"])
            db.add(row)
            n += 1
        for field in PROFILE_FIELDS:
            if getattr(row, field, None) is None:
                setattr(row, field, profile[field])
        if row.osm_tags is None and profile.get("osm_tags"):
            row.osm_tags = profile["osm_tags"]
    return n


def get_category_profile(db, code: str) -> dict:
    """DB-backed profile with registry fallback; never raises for known codes."""
    defaults = dict(CATEGORY_PROFILES.get(code, {}))
    row = db.execute(select(BusinessCategory).where(BusinessCategory.code == code)).scalars().first()
    if row is None:
        return defaults
    profile = dict(defaults)
    profile["name"] = row.name or defaults.get("name")
    profile["description"] = row.description or defaults.get("description")
    backed = False
    for field in PROFILE_FIELDS:
        value = getattr(row, field, None)
        if value:
            profile[field] = value
            backed = True
    profile["db_backed"] = backed
    return profile
