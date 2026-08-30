"""Verified price potential (plan §17 / hardening).

Reads only already-ingested `MarketPrice` rows (data.gov.in/Agmarknet mandi
snapshots, stored with provenance). Never invents local prices: when there
are no rows for the district the provider reports `available: False`, which
keeps the price score neutral/None downstream.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import MarketPrice

# Category -> relevant-ish commodities (lower-cased substring match).
# An empty tuple means "any item available in the district" is accepted.
RELEVANT_ITEMS = {
    "dairy": ("milk", "ghee", "curd", "paneer", "butter"),
    "grocery": ("rice", "wheat", "pulses", "sugar", "tomato", "potato", "onion", "oil"),
}


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
    return any(n in h for h in haystack)


def derive_price_evidence(db: Session, district: str, category_code: str) -> dict:
    """Latest reference date per commodity in `district`, filtered by category.

    Returns a JSON-serialisable evidence dict; never fabricates values.
    """
    relevant = tuple(RELEVANT_ITEMS.get(category_code, ()))
    rows = list(db.execute(
        select(MarketPrice)
        .where(MarketPrice.district == district)
        .distinct(MarketPrice.item_name)
        .order_by(MarketPrice.item_name, MarketPrice.reference_date.desc().nulls_last())
    ).scalars())

    matched = [r for r in rows if _matches(r.item_name or "", relevant)] if relevant else rows
    item_count = len(matched)
    if not item_count:
        return {
            "available": False,
            "price_score_unavailable": True,
            "category_code": category_code,
            "district": district,
            "item_count": 0,
            "coverage": 0.0,
            "note": "No ingested market price rows for this district.",
            "items": [],
        }

    coverage = round(len(matched) / len(relevant), 2) if relevant else 1.0
    confidence = "high" if coverage >= 0.5 else ("medium" if coverage > 0 else "low")
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
            }
            for r in matched
        ],
    }


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
