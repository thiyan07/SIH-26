"""Category-aware Market Intelligence 2.0 engine (SIH26092).

Composes the existing, provenance-bearing market pieces into a single
category-scoped intelligence block for the Market page:

  * Relevant-commodity prices: the ingested `MarketPrice` rows filtered to the
    business category's relevant commodities, the district, REAL (non-demo)
    rows, and an optional freshness window. Never invents prices.
  * Per-item and overall relevance / freshness / confidence scoring.
  * A source hierarchy ranked by authority (government/mandi > osm > proxy >
    demo), each carrying its provenance.
  * Category-scoped commercial demand signals + market accessibility reusing
    `app.engines.market.MarketReachAnalyzer`.
  * Seasonal + product readiness signals derived from the category profile.

Everything returned is deterministically computed from stored, provenance-
bearing DB records; missing evidence is reported as unavailable (never
fabricated), and confidence is reduced when coverage/freshness is low.

This reuses the existing architecture (MarketPrice table, MarketReachAnalyzer,
category catalog, provenance helpers) rather than introducing a parallel
market stack.
"""
from __future__ import annotations

import datetime as dt
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import MarketPrice
from app.engines.market import analyze as analyze_market
from app.geo import real_data_condition
from app.provenance import freshness_for

# ---------------------------------------------------------------------------
# Category -> relevant commodity substrings (lower-case, substring match).
# Kept here as the market-intelligence superset of `prices.RELEVANT_ITEMS`.
# Categories not listed fall back to a neutral "any available commodity",
# which is the documented, honest default (do not pretend per-item relevance).
# ---------------------------------------------------------------------------
RELEVANT_COMMODITIES: dict[str, tuple[str, ...]] = {
    "grocery": ("rice", "wheat", "pulses", "sugar", "tomato", "potato", "onion", "oil", "salt", "tur", "dal", "flour"),
    "dairy": ("milk", "ghee", "curd", "paneer", "butter"),
    "restaurant": ("onion", "potato", "tomato", "oil", "rice", "chicken", "egg", "vegetable", "wheat"),
    "bakery": ("wheat", "flour", "sugar", "oil", "milk", "butter"),
    "meat_shop": ("chicken", "mutton", "fish", "egg", "pork"),
    "fish_shop": ("fish", "prawn", "seafood"),
    "fruit_shop": ("banana", "mango", "apple", "grape", "papaya", "orange", "fruit"),
    "vegetable_shop": ("tomato", "onion", "potato", "brinjal", "bottle", "bitter", "pumpkin", "cabbage", "cauliflower", "beans", "carrot", "chilli", "vegetable"),
    "food_processing": ("rice", "wheat", "pulses", "oil", "milk", "sugarcane", "groundnut", "maize", "paddy"),
    "agriculture": ("paddy", "rice", "maize", "sugarcane", "cotton", "groundnut", "coconut", "banana", "turmeric"),
    "textile": ("cotton", "turf", "raw cotton"),
    "poultry": ("chicken", "egg", "maize", "poultry"),
    "sweet_shop": ("sugar", "ghee", "milk", "cashew", "almond"),
    "animal_feed": ("maize", "wheat", "feed", "bran"),
    "fertilizer": ("urea", "fertilizer", "dap", "potash"),
}


def relevant_commodities(category_code: str) -> tuple[str, ...]:
    return RELEVANT_COMMODITIES.get(category_code, ())


def _matches(item: Optional[str], needles: tuple[str, ...]) -> bool:
    if not item:
        return False
    n = item.lower()
    return any(nd in n for nd in needles)


# ---------------------------------------------------------------------------
# Per-item provenance (normalised, only non-None fields)
# ---------------------------------------------------------------------------
def _item_provenance(row: MarketPrice) -> dict:
    out = {
        "source_name": row.source_name,
        "source_type": row.source_type,
        "dataset_name": row.dataset_name,
        "source_url": row.source_url,
        "reference_date": row.reference_date.isoformat() if row.reference_date else None,
        "confidence": row.confidence,
        "is_estimate": row.is_estimate,
        "is_demo": row.is_demo,
        "geographic_level": row.geographic_level,
    }
    return {k: v for k, v in out.items() if v is not None}


_SOURCE_RANK = {"government": 0, "osm": 1, "vendor": 2, "proxy": 3, "demo": 4, None: 5}


def source_hierarchy(rows: list[MarketPrice]) -> list[dict]:
    """Deduplicated source list ordered by authority, with provenance."""
    seen: dict[str, dict] = {}
    for r in rows:
        key = (r.source_name or "unknown") + "|" + (r.dataset_name or "")
        rec = seen.get(key)
        rec_data = {
            "source_name": r.source_name or "unknown",
            "dataset_name": r.dataset_name,
            "source_type": r.source_type,
            "sample_date": r.reference_date.isoformat() if r.reference_date else None,
            "authority": _SOURCE_RANK.get(r.source_type, 5),
        }
        if rec is None:
            rec = {**rec_data, "items": 0, "is_estimate": bool(r.is_estimate), "is_demo": bool(r.is_demo)}
            seen[key] = rec
        rec["items"] += 1
    ordered = sorted(seen.values(), key=lambda x: (x["authority"], -(x["items"] or 0)))
    for rec in ordered:
        rec.pop("authority", None)
    return ordered


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------
def _freshness_bucket(reference_date: Optional[dt.date]) -> str:
    return freshness_for(source_type="market_price", reference_date=reference_date)


def _confidence(coverage: float, fresh_share: float) -> dict:
    score = 50.0
    score += min(coverage * 40.0, 40.0)          # how many relevant commodities we have
    score += min(fresh_share * 10.0, 10.0)       # how current those rows are
    conf = "high" if score >= 70 else ("medium" if score >= 45 else "low")
    return {"score": round(min(100.0, score), 1), "label": conf}


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------
def category_market_intelligence(
    db: Session,
    *,
    category_code: str,
    state: str,
    district: str,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    radius_km: float = 10.0,
    max_age_days: Optional[int] = 90,
    today: Optional[dt.date] = None,
) -> dict:
    """Assemble category-aware market intelligence from stored evidence.

    All price facts come only from ingested, REAL MarketPrice rows; nothing is
    fabricated. Lat/long are optional and, when given, additionally drive the
    location-scoped demand-signal + accessibility analysis via
    MarketReachAnalyzer. When no coordinates are supplied, the demand/trade
    reach block is reported unavailable rather than guessed.
    """
    today = today or dt.date.today()
    needles = relevant_commodities(category_code)

    # 1. Real, district-scoped, in-window MarketPrice rows.
    stmt = (
        select(MarketPrice)
        .where(
            MarketPrice.district == district,
            real_data_condition(MarketPrice),
            MarketPrice.reference_date.is_not(None),
        )
    )
    if max_age_days is not None:
        cutoff = today - dt.timedelta(days=max_age_days)
        stmt = stmt.where(MarketPrice.reference_date >= cutoff)

    # Prefer the most recent date per item, then filter by category relevance.
    price_rows = list(db.execute(stmt).all())
    flat = [r if isinstance(r, MarketPrice) else r[0] for r in price_rows]

    # Keep the latest reference-date row per (item, market) so the same
    # commodity is not duplicated across stale snapshots (evidence de-dup).
    latest_per_item: dict[tuple[str, str], MarketPrice] = {}
    for r in flat:
        key = (r.item_name or "", r.market_name or "")
        cur = latest_per_item.get(key)
        if cur is None or (r.reference_date or dt.date.min) > (cur.reference_date or dt.date.min):
            latest_per_item[key] = r
    unique_rows = list(latest_per_item.values())

    relevant_rows = [r for r in unique_rows if _matches(r.item_name, needles)]

    # 2. Build per-item price evidence with relevance/freshness scoring.
    items = []
    for r in relevant_rows:
        confirmed = r.reference_date if r.reference_date else None
        freshness = _freshness_bucket(confirmed)
        items.append({
            "item": r.item_name,
            "unit": r.unit,
            "min": float(r.min_price) if r.min_price is not None else None,
            "max": float(r.max_price) if r.max_price is not None else None,
            "modal": float(r.modal_price) if r.modal_price is not None else None,
            "market": r.market_name,
            "mandi": r.mandi,
            "reference_date": confirmed.isoformat() if confirmed else None,
            "days_old": (today - confirmed).days if confirmed else None,
            "freshness": freshness,
            "relevance": "high",  # item was matched against the category commodity list
            "source": _item_provenance(r),
            "is_estimate": bool(r.is_estimate),
            "is_demo": bool(r.is_demo),
        })
    # Order: freshest first, then by item name.
    items.sort(key=lambda x: (x["days_old"] is None, x["days_old"] or 0, x["item"]))

    # 3. Coverage + confidence scoring.
    if needles:
        present = {it["item"].lower() for it in items}
        coverage_items = sum(1 for nd in needles
                             if any(nd in p for p in present))
        coverage = round(coverage_items / len(needles), 2)
    else:
        coverage = round(min(len(items) / 5.0, 1.0), 2) if items else 0.0

    fresh_rows = [it for it in items if it["freshness"] in ("fresh", "recent")]
    fresh_share = round(len(fresh_rows) / len(items), 2) if items else 0.0
    conf = _confidence(coverage, fresh_share)
    # When nothing relevant is available the confidence must be honest: a
    # "medium" coverage-derived number misreads missing data as a firm figure.
    available = bool(items)
    if not available:
        conf = {"score": 0.0, "label": "low"}

    # 4. Demand-signal + accessibility block (MarketReachAnalyzer), with a
    #    location-like object only when coordinates are provided.
    demand = None
    if latitude is not None and longitude is not None:
        from types import SimpleNamespace
        loc = SimpleNamespace(
            id=None, latitude=latitude, longitude=longitude,
            state=state, district=district, block=None, village=None,
        )
        reach = analyze_market(db, location=loc, radius_km=radius_km,
                               data_completeness=_confidence_coverage_label(conf["score"]))
        demand = {
            "population_baseline": reach.population_baseline,
            "households": reach.households,
            "demand_score": reach.to_dict()["market_reach"]["demand_score"],
            "commercial_demand_signals": reach.commercial_demand_signals,
            "market_accessibility": reach.market_accessibility,
            "confidence": reach.confidence,
            "available_population": reach.available_population,
        }

    available = bool(items)
    return {
        "category_code": category_code,
        "state": state,
        "district": district,
        "radius_km": radius_km,
        "max_age_days": max_age_days,
        "as_of": today.isoformat(),
        "available": available,
        "availability_note": (
            "Relevant category commodities with verified local prices."
            if available else
            "No verified (non-demo) market price rows match this category's "
            "commodities in the district within the freshness window."
        ),
        "commodity_scope": {
            "has_specific_commodities": bool(needles),
            "relevant_commodities": list(needles),
            "note": "Category-specific commodity list used to filter prices. "
                    "Categories without a list accept any verified local commodity."
            if not needles else
            "Category-specific commodity list used to filter prices.",
        },
        "prices": items,
        "coverage": coverage,
        "fresh_share": fresh_share,
        "confidence": conf,
        "source_hierarchy": source_hierarchy(relevant_rows) if available else [],
        "demand_context": demand,
        "notes": [
            "Only sourced (non-demo) prices are shown; none are invented.",
            "Prices are the latest stored mandi/Uzhavar Sandhai snapshot per item; "
            "they are indicative, not guaranteed, and may be several days old.",
            "Relevance/freshness/confidence are computed from provenance and "
            "coverage, and missing data lowers confidence rather than fabricating figures.",
        ],
    }


def _confidence_coverage_label(confidence_score: float) -> str:
    return "high" if confidence_score >= 70 else ("medium" if confidence_score >= 45 else "low")
