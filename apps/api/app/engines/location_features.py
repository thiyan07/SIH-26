"""Location-scoped MSME / industrial evidence (UDYAM + factories).

Fills the ``location_features`` evidence block with:

  * ``nearby_msmes``   count of UDYAM units whose **pincode centroid** falls
                       within radius (approximate - pincode centroid, NOT point
                       location; clearly labelled)
  * ``relevant_msmes`` subset filtered by the category's NIC/industry signal
                       (when the category profile defines one) at district scope
  * ``industrial_units``  district-level registered-factory aggregate, when the
                       source has been ingested
  * ``data_confidence``   a small quality summary for this block

Honesty rules (plan §10 / data-quality policy):
  - UDYAM units carry no exact lat/lng. We locate them at their pincode
    centroid and say so; ``geo_resolution`` is ``pincode``.
  - These counts are context for demand/competition reasoning; they are never
    used as point-radius competitor tallies (that role stays with OSM).
  - Missing data returns ``available=False`` / empty lists - never fabricated.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import func, select

from app.db.models import IndustrialUnit, UdyamUnit
from app.geo import find_nearby, real_data_condition


def _category_nic_signals(profile: dict) -> list[str]:
    """Derive NIC-prefix signals from a category profile if present."""
    signals = (profile or {}).get("demand_signals") or []
    out = []
    for s in signals:
        if not isinstance(s, str):
            continue
        low = s.lower()
        if low.startswith("nic:"):
            out.append(s.split(":", 1)[1].strip())
    return out


def location_features(db, *, state: str, district: str, latitude: float,
                      longitude: float, radius_km: float = 10.0,
                      profile: Optional[dict] = None) -> dict:
    """Compute pincode-centroid MSME evidence + district industrial context."""

    # 1. Nearby UDYAM units by pincode centroid (approximate).
    nearby = find_nearby(db, UdyamUnit, latitude, longitude, radius_km,
                         real_only=True, limit=500)
    nic_signals = _category_nic_signals(profile)

    # 2. Relevant = same district + NIC-category match (when defined).
    relevant = 0
    if nic_signals:
        stmt = select(func.count(UdyamUnit.id)).where(
            real_data_condition(UdyamUnit),
            UdyamUnit.district == district,
            UdyamUnit.state == state,
        )
        # NIC codes match by prefix (first 2 digits = division).
        conditions = [UdyamUnit.nic_code.like(f"{prefix}%") for prefix in nic_signals]
        stmt = stmt.where(*conditions) if conditions else stmt
        relevant = db.execute(stmt).scalar() or 0

    # 3. Weighted activity composition from nearby units (sector split).
    sector_counts: dict[str, int] = {}
    for u in nearby:
        key = (u.sector or "unknown").lower()
        sector_counts[key] = sector_counts.get(key, 0) + 1

    # 4. District-level industrial aggregate (e.g. registered small-scale
    #    industries). District-scoped; NOT point-radius.
    ind_rows = db.execute(
        select(IndustrialUnit)
        .where(real_data_condition(IndustrialUnit),
               IndustrialUnit.state == state,
               IndustrialUnit.district == district)
    ).scalars().all()
    ind_total = sum(r.count or 0 for r in ind_rows)
    ind_breakdown = [
        {"unit_type": r.unit_type, "reference_year": r.reference_year,
         "count": r.count}
        for r in ind_rows if r.count
    ]

    return {
        "geo_resolution": "pincode",
        "geo_resolution_note": ("UDYAM units are located at their pincode "
                                "centroid - distances are approximate and NOT "
                                "point-precise."),
        "nearby_msmes": len(nearby),
        "nearby_msmes_within_km": radius_km,
        "relevant_msmes": relevant,
        "relevant_filter": "district + NIC-2008 division prefix" if nic_signals else "none",
        "industrial_units": {
            "available": bool(ind_rows),
            "district_level": True,
            "note": ("Registered small-scale / factory aggregates are "
                     "district-scoped (not point-precise)."),
            "total_units": ind_total,
            "by_type": ind_breakdown,
        },
        "sector_composition": sector_counts,
        "available": bool(nearby or relevant),
        "source_name": "UDYAM (Ministry of MSME, via data.gov.in)",
        "source_type": "government",
        "confidence": "medium",
        "record_sample": [
            {"name": u.enterprise_name, "district": u.district,
             "pincode": u.pincode, "nic_code": u.nic_code,
             "sector": u.sector, "category": u.category}
            for u in nearby[:10]
        ],
    }


def to_dict(features: dict) -> dict:
    return features
