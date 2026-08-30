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

    Reads ONLY real (non-demo) ingested MarketPrice rows so demo/proxy price
    rows can never leak into real scoring. Returns a JSON-serialisable
    evidence dict; never fabricates values.
    """
    relevant = tuple(RELEVANT_ITEMS.get(category_code, ()))
    matched = _real_matched_rows(db, district, relevant)

    item_count = len(matched)
    if not item_count:
        return {
            "available": False,
            "price_score_unavailable": True,
            "category_code": category_code,
            "district": district,
            "item_count": 0,
            "coverage": 0.0,
            "unavailable_reason": "No verified (non-demo) market price rows for this district.",
            "note": "No ingested market price rows for this district.",
            "items": [],
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
    """Count of stored dated rows per matched item (the price history we hold)."""
    from sqlalchemy import func

    stmt = (
        select(MarketPrice.item_name, func.count().label("n"))
        .where(
            MarketPrice.district == district,
            real_data_condition(MarketPrice),
        )
        .group_by(MarketPrice.item_name)
    )
    if relevant:
        stmt = stmt.where(MarketPrice.item_name.in_(relevant))
    return {name: int(n) for name, n in db.execute(stmt).all()}


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
