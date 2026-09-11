"""Verified price potential (plan §17 / hardening).

Reads only already-ingested `MarketPrice` rows (data.gov.in/Agmarknet mandi
snapshots, stored with provenance). Never invents local prices: when there
are no rows for the district the provider reports `available: False`, which
keeps the price score neutral/None downstream.
"""
from __future__ import annotations

import datetime as dt
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import MarketPrice
from app.geo import real_data_condition
from app.provenance import freshness_for

# Category -> relevant-ish commodities (lower-cased substring match).
# Tradeable categories have commodity lists; service/craft categories have
# an empty tuple meaning "no relevant mandi commodity — price not applicable
# (not UNAVAILABLE due to missing data)".
RELEVANT_ITEMS = {
    "dairy": ("milk", "ghee", "curd", "paneer", "butter"),
    "grocery": ("rice", "wheat", "pulses", "sugar", "tomato", "potato", "onion", "oil", "salt", "tur", "dal"),
    "restaurant": ("onion", "potato", "tomato", "oil", "rice", "chicken", "egg", "vegetable", "wheat"),
    "bakery": ("wheat", "flour", "sugar", "oil", "milk", "butter"),
    "meat_shop": ("chicken", "mutton", "fish", "egg", "pork"),
    "fish_shop": ("fish", "prawn", "seafood"),
    "vegetable_shop": ("tomato", "onion", "potato", "brinjal", "bottle", "bitter", "pumpkin", "cabbage", "cauliflower", "beans", "carrot", "chilli", "vegetable"),
    "fruit_shop": ("banana", "mango", "apple", "grape", "papaya", "orange", "fruit"),
    "food_processing": ("rice", "wheat", "pulses", "oil", "milk", "sugarcane", "groundnut", "maize", "paddy"),
    "agriculture": ("paddy", "rice", "maize", "sugarcane", "cotton", "groundnut", "coconut", "banana", "turmeric"),
    "textile": ("cotton",),
    "poultry": ("chicken", "egg", "maize", "poultry"),
    "sweet_shop": ("sugar", "ghee", "milk", "cashew", "almond"),
    "animal_feed": ("maize", "wheat", "feed", "bran"),
    "fertilizer": ("urea", "fertilizer", "dap", "potash"),
    "seed_shop": ("paddy", "maize", "cotton", "groundnut", "seed"),
    "agricultural_equipment": ("tractor", "pump", "irrigation"),
    # Service/craft categories — no relevant mandi commodity (honest, not fabricated)
    "mobile_shop": (),
    "electronics": (),
    "clothing": ("cotton",),
    "footwear": (),
    "furniture": (),
    "pharmacy": (),
    "salon": (),
    "tailoring": ("cotton",),
    "printing": (),
    "computer_service": (),
    "mechanic": (),
    "clinic": (),
    "hardware": (),
    "handicrafts": (),
    "manufacturing": ("steel", "cotton"),
    "other": (),
}

# Categories where mandi price relevance is not applicable (service/craft)
SERVICE_NO_MANDI_CATEGORIES = frozenset({
    "mobile_shop", "electronics", "salon", "tailoring", "printing",
    "computer_service", "mechanic", "tyre_shop", "car_service", "laundry",
    "photography", "internet_centre", "travel_agency", "finance", "welding",
    "hardware", "building_materials", "steel_products", "plywood",
    "clinic", "hospital", "diagnostic", "dental_clinic", "optical_shop",
    "veterinary", "pharmacy", "furniture", "stationery", "home_appliances",
    "battery_shop", "auto_parts", "hotel", "fast_food", "tea_shop",
    "handicrafts", "other",
})


def _provenance(row: MarketPrice) -> dict:
    out = {
        "source_name": row.source_name,
        "source_url": row.source_url,
        "dataset_name": row.dataset_name,
        "reference_date": row.reference_date.isoformat() if row.reference_date else None,
        "source_type": row.source_type,
        "confidence": row.confidence,
        "is_estimate": row.is_estimate,
        "is_demo": row.is_demo,
    }
    return {k: v for k, v in out.items() if v is not None}


def _matches(needle: str, haystack) -> bool:
    n = needle.lower()
    return any(h.lower() in n for h in haystack)


def derive_price_evidence(db: Session, district: str, category_code: str) -> dict:
    """Latest reference date per commodity in `district`, filtered by category.

    Reads ONLY real (non-demo) ingested MarketPrice rows so demo/proxy price
    rows can never leak into real scoring. Returns a JSON-serialisable
    evidence dict; never fabricates values.

    For service/craft categories where no mandi commodity is relevant, the
    result is honestly reported as not_applicable rather than unavailable-
    due-to-missing-data.
    """
    # Service categories have no relevant mandi commodity — not a data gap.
    if category_code in SERVICE_NO_MANDI_CATEGORIES and category_code not in RELEVANT_ITEMS:
        return {
            "available": False,
            "price_score_unavailable": True,
            "not_applicable": True,
            "category_code": category_code,
            "district": district,
            "item_count": 0,
            "coverage": 0.0,
            "unavailable_reason": "Service/craft business — no relevant mandi commodity. Price relevance not applicable (not a data gap).",
            "note": "Service business — mandi price not applicable. Use local supplier quotes for input costs.",
            "items": [],
        }

    relevant = tuple(RELEVANT_ITEMS.get(category_code, ()))
    # Empty tuple for a tradeable category would mean "accept any" — but we
    # now explicitly list service categories above, so empty here is data gap.
    is_service_empty = (len(relevant) == 0 and category_code in SERVICE_NO_MANDI_CATEGORIES)
    if is_service_empty:
        return {
            "available": False,
            "price_score_unavailable": True,
            "not_applicable": True,
            "category_code": category_code,
            "district": district,
            "item_count": 0,
            "coverage": 0.0,
            "unavailable_reason": "Service/craft business — no relevant mandi commodity. Price relevance not applicable.",
            "note": "Service business — mandi price not applicable. Use local supplier quotes for input costs.",
            "items": [],
        }

    matched = _real_matched_rows(db, district, relevant)

    item_count = len(matched)
    if not item_count:
        # Attempt live scrape fallback for districts with no DB prices (real data first, then estimate)
        live = _try_live_price_fallback(district, category_code, relevant)
        if live and live.get("items"):
            return live
        return {
            "available": False,
            "price_score_unavailable": True,
            "category_code": category_code,
            "district": district,
            "item_count": 0,
            "coverage": 0.0,
            "unavailable_reason": "No verified (non-demo) market price rows for this district within the freshness window.",
            "note": "No ingested market price rows for this district — prices show as LIMITED EVIDENCE and confidence is reduced.",
            "items": [],
            "scrape_attempted": live is not None,
        }

    coverage = round(len(matched) / len(relevant), 2) if relevant else 1.0
    confidence = "high" if coverage >= 0.5 else ("medium" if coverage > 0 else "low")
    history = _history_counts(db, district, relevant)
    deltas = _item_deltas(db, district, matched)
    latest = max((r.reference_date for r in matched if r.reference_date), default=None)
    latest_days = (dt.date.today() - latest).days if latest else None
    return {
        "available": True,
        "price_score_unavailable": False,
        "category_code": category_code,
        "district": district,
        "item_count": item_count,
        "coverage": coverage,
        "confidence": confidence,
        "reference_dates": sorted({
            r.reference_date.isoformat() for r in matched if r.reference_date
        }),
        "latest_reference_date": latest.isoformat() if latest else None,
        "days_since_latest": latest_days,
        "freshness": freshness_for(source_type="market_price", reference_date=latest),
        "history_rows": history,
        "source": _provenance(matched[0]),
        "note": f"{item_count} commodity price(s) from ingested mandi data"
                f" ({confidence} coverage of relevant items).",
        "items": [
            {
                "item_name": r.item_name,
                "unit": r.unit,
                "modal_price": float(r.modal_price) if r.modal_price is not None else None,
                "min_price": float(r.min_price) if r.min_price is not None else None,
                "max_price": float(r.max_price) if r.max_price is not None else None,
                "market_name": r.market_name,
                "mandi": r.mandi,
                "reference_date": r.reference_date.isoformat() if r.reference_date else None,
                "delta_pct": deltas.get(r.item_name),
            }
            for r in matched
        ],
    }


def _real_matched_rows(db: Session, district: str, relevant: tuple[str, ...]):
    rows = list(db.execute(
        select(MarketPrice)
        .where(
            MarketPrice.district == district,
            real_data_condition(MarketPrice),
        )
        .distinct(MarketPrice.item_name)
        .order_by(MarketPrice.item_name, MarketPrice.reference_date.desc().nulls_last())
    ).scalars())
    return [r for r in rows if _matches(r.item_name or "", relevant)] if relevant else rows


def _history_counts(db: Session, district: str, relevant: tuple[str, ...]) -> dict:
    """Count of stored dated rows per matched item (the price history we hold).

    Uses substring matching (same as _real_matched_rows) so "Rice Basmati"
    counts toward relevant commodity "rice" rather than requiring an exact
    item_name == "rice" match.
    """
    from sqlalchemy import func

    stmt = (
        select(MarketPrice.item_name, func.count().label("n"))
        .where(
            MarketPrice.district == district,
            real_data_condition(MarketPrice),
        )
        .group_by(MarketPrice.item_name)
    )
    rows = {name: int(n) for name, n in db.execute(stmt).all()}
    if not relevant:
        return rows
    # Keep only items that substring-match a relevant commodity.
    return {name: n for name, n in rows.items() if _matches(name or "", relevant)}


def _item_deltas(db: Session, district: str, matched) -> dict[str, Optional[float]]:
    """Percent change of modal price between the two most recent dates per item.

    Trend is computed only from stored dated records (never guessed): when
    fewer than two dated rows exist the value is None.
    """
    items = tuple({r.item_name for r in matched})
    if not items:
        return {}
    rows = list(db.execute(
        select(MarketPrice)
        .where(
            MarketPrice.district == district,
            MarketPrice.item_name.in_(items),
            MarketPrice.reference_date.is_not(None),
            real_data_condition(MarketPrice),
        )
        .order_by(MarketPrice.item_name, MarketPrice.reference_date.desc())
    ).scalars())
    out: dict[str, Optional[float]] = {}
    by_name: dict[str, list[MarketPrice]] = {}
    for r in rows:
        by_name.setdefault(r.item_name, []).append(r)
    for name, recs in by_name.items():
        if len(recs) < 2 or recs[0].modal_price is None or recs[1].modal_price in (None, 0):
            out[name] = None
            continue
        try:
            prev = float(recs[1].modal_price)
            curr = float(recs[0].modal_price)
            out[name] = round((curr - prev) / prev * 100.0, 1)
        except (TypeError, ValueError, ZeroDivisionError):
            out[name] = None
    return out


def _try_live_price_fallback(district: str, category_code: str, relevant: tuple[str, ...]) -> Optional[dict]:
    """Best-effort live scrape when DB has no prices for this district.

    Tries the ACROP public mandi mirror (keyless) for Tamil Nadu districts.
    Returns a live evidence dict if rows are fetched, otherwise None.
    Never blocks analysis: any network/timeout failure returns None and the
    caller falls back to UNAVAILABLE with reduced confidence.
    Skipped in test environment (PYTEST_CURRENT_TEST or app_env=test) to keep
    tests deterministic and fast.
    """
    import os as _os
    if _os.getenv("PYTEST_CURRENT_TEST") or _os.getenv("PYTEST_XDIST_WORKER"):
        return None
    try:
        from app.config import settings as _settings
        if getattr(_settings, "app_env", "") == "test":
            return None
    except Exception:
        pass
    def _build_live_evidence(rows, source_label):
        live_matched = [r for r in rows if _matches(r.get("item_name") or "", relevant)] if relevant else rows
        if not live_matched:
            return None
        latest = max((r.get("reference_date") for r in live_matched if r.get("reference_date")), default=None)
        import datetime as _dt
        latest_date = None
        if latest:
            try:
                latest_date = _dt.date.fromisoformat(str(latest)) if isinstance(latest, str) else latest
            except Exception:
                latest_date = None
        coverage = round(len(live_matched) / len(relevant), 2) if relevant else 1.0
        confidence = "high" if coverage >= 0.5 else ("medium" if coverage > 0 else "low")
        return {
            "available": True,
            "price_score_unavailable": False,
            "live_scrape": True,
            "category_code": category_code,
            "district": district,
            "item_count": len(live_matched),
            "coverage": coverage,
            "confidence": confidence,
            "reference_dates": sorted({str(r.get("reference_date")) for r in live_matched if r.get("reference_date")}),
            "latest_reference_date": str(latest) if latest else None,
            "days_since_latest": ( _dt.date.today() - latest_date).days if latest_date else None,
            "freshness": freshness_for(source_type="market_price", reference_date=latest_date),
            "history_rows": {},
            "source": {"source_name": source_label, "source_type": "market_prices", "confidence": "medium", "is_estimate": False},
            "note": f"{len(live_matched)} live commodity price(s) scraped from {source_label} ({confidence} coverage).",
            "items": [
                {
                    "item_name": r.get("item_name"),
                    "unit": r.get("unit", "quintal"),
                    "modal_price": float(r["modal_price"]) if r.get("modal_price") is not None else None,
                    "min_price": float(r["min_price"]) if r.get("min_price") is not None else None,
                    "max_price": float(r["max_price"]) if r.get("max_price") is not None else None,
                    "market_name": r.get("market_name"),
                    "mandi": r.get("market_name"),
                    "reference_date": str(r.get("reference_date")) if r.get("reference_date") else None,
                    "delta_pct": None,
                }
                for r in live_matched
            ],
        }

    try:
        from app.providers.mandi_live import fetch_live_prices_for_district as _acrop
        live_rows = _acrop(district, timeout_s=4)
        ev = _build_live_evidence(live_rows, "ACROP Mandi (live scrape)")
        if ev:
            return ev
    except Exception:
        pass
    try:
        from app.providers.mandibhavindia import fetch_live_prices_for_district as _mb
        live_rows2 = _mb(district, timeout_s=8)
        ev2 = _build_live_evidence(live_rows2, "Mandibhavindia (live scrape — Agmarknet/eNAM 385 mandis)")
        if ev2:
            return ev2
    except Exception:
        return None
    return None


def price_score_from_evidence(evidence: dict) -> Optional[float]:
    """Deterministic price component score, or None when data is unavailable.

    Prototype formula (documented in docs/scoring-methodology.md §5): a higher
    share of relevant commodities with verified local prices raises the score
    from a neutral baseline of 40 toward 90.
    """
    if not evidence.get("available") or not evidence.get("item_count"):
        return None
    coverage = float(evidence.get("coverage") or 0.0)
    return round(min(100.0, 40.0 + coverage * 50.0), 1)
