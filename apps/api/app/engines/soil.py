"""Soil Health Card evidence engine (MOAFW nutrient analysis).

Reads ONLY real (non-demo) `SoilHealthStatistic` rows and turns them into a
small, deterministic risk contribution for agriculture input/cost exposure:

- rows geo-resolved to the location OR kept at district admin path are used
  (unresolved villages still carry district text, so district queries work);
- per-nutrient summaries use the most recent sample year present;
- a nutrient reading of *low*/*deficient* raises the fertiliser/input-cost
  burden (risk), a majority-healthy sample very slightly lowers it, and
  missing data changes nothing (risk is never invented).
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.db.models import SoilHealthStatistic
from app.geo import real_data_condition

DEFICIENT_LEVELS = {"low", "deficient"}
MAX_RISK_DELTA = 12.0
RISK_LADDER = 25.0  # deficient_share * ladder => capped contribution
HEALTHY_RELIEF = -3.0  # small discount when a majority of samples are healthy


def _norm_level(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    return str(raw).strip().lower()


def soil_health_evidence(
    db: Session,
    *,
    state: Optional[str] = None,
    district: Optional[str] = None,
    block: Optional[str] = None,
    village: Optional[str] = None,
    location_id: Optional[str] = None,
) -> dict:
    """Evidence dict for a location, aggregating stored SHC nutrient rows.

    Never fabricates values: with no real rows `available` is False and
    `risk_delta` is 0.
    """
    if not district and not location_id:
        return _empty("No district or location given for soil health lookup.")

    cond = real_data_condition(SoilHealthStatistic)
    scope = []
    if location_id:
        admin = and_(
            (SoilHealthStatistic.state == state) if state else True,
            (SoilHealthStatistic.district == district) if district else True,
        )
        scope.append(or_(
            SoilHealthStatistic.location_id == location_id,
            and_(admin, SoilHealthStatistic.district.is_not(None)),
        ))
    else:
        if district:
            scope.append(SoilHealthStatistic.district == district)
        if block:
            scope.append(or_(SoilHealthStatistic.block == block,
                             SoilHealthStatistic.block.is_(None)))
        if village:
            scope.append(SoilHealthStatistic.village == village)

    stmt = select(SoilHealthStatistic).where(cond, *scope)
    rows = list(db.execute(stmt).scalars())
    if not rows:
        return _empty("No real Soil Health Card rows for this location yet.")

    # aggregate per nutrient over the most recent sample year
    latest_year = max((r.sample_year for r in rows if r.sample_year), default=None)
    by_nutrient: dict[str, dict] = {}
    for r in rows:
        if r.sample_year != latest_year:
            continue
        name = (r.nutrient_name or "unknown").strip()
        agg = by_nutrient.setdefault(name, {
            "name": name, "nutrient_type": r.nutrient_type, "values": [],
            "levels": [], "sample_year": latest_year,
        })
        if r.value is not None:
            agg["values"].append(float(r.value))
        lvl = _norm_level(r.nutrient_level)
        if lvl:
            agg["levels"].append(lvl)

    nutrients = []
    deficient_total = 0
    total = 0
    for name in sorted(by_nutrient):
        agg = by_nutrient[name]
        level = None
        # reference level = most common classified reading, else None
        if agg["levels"]:
            from collections import Counter
            level, _ = Counter(agg["levels"]).most_common(1)[0]
            total += 1
            if level in DEFICIENT_LEVELS:
                deficient_total += 1
        nutrients.append({
            "nutrient": agg["name"],
            "nutrient_type": agg["nutrient_type"],
            "level": level,
            "value": round(sum(agg["values"]) / len(agg["values"]), 2) if agg["values"] else None,
            "samples": len(agg["values"]) or len(agg["levels"]),
        })

    deficient_share = (deficient_total / total) if total else 0.0
    if deficient_share > 0.65:
        note = (f"{deficient_total}/{total} nutrients are low/deficient in the latest "
                f"sample year ({latest_year}) - elevated input/fertiliser cost burden.")
    elif deficient_share >= 0.25:
        note = (f"Some nutrients ({deficient_total}/{total}) read low/deficient in "
                f"sample year {latest_year} - moderate input-cost risk.")
    else:
        note = (f"Most sampled nutrients are balanced (sample year {latest_year}) - "
                "no elevated input-cost burden detected.")
    risk_delta = min(MAX_RISK_DELTA, deficient_share * RISK_LADDER)
    health_adj = HEALTHY_RELIEF if (deficient_share <= 0.25 and total >= 3) else 0.0
    risk_delta = round(risk_delta + health_adj, 1)

    return {
        "available": True,
        "sample_year": latest_year,
        "records": len(rows),
        "nutrients": nutrients,
        "deficient_share": round(deficient_share, 2),
        "risk_delta": risk_delta,
        "note": note,
    }


def _empty(reason: str) -> dict:
    return {
        "available": False,
        "sample_year": None,
        "records": 0,
        "nutrients": [],
        "deficient_share": 0.0,
        "risk_delta": 0.0,
        "note": reason,
    }
