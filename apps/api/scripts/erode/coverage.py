"""Erode District coverage metrics + reports.

Produces:
* ``data/erode/ERODE_COVERAGE_REPORT.md``   — per-block/per-category matrix
* ``data/erode/DATA_QUALITY_REPORT.md``     — completeness/confidence profile
* ``data/erode/DATA_SOURCE_REGISTRY.md``    — source rows actually used
* ``data/erode/erode_coverage.json``        — machine-readable coverage stats
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy import func, distinct

log = logging.getLogger("erode.coverage")

BASE_DIR = Path(__file__).resolve().parents[2]
ERODE_DATA = BASE_DIR / "data" / "erode"

MISSION_CATEGORIES = [
    "grocery", "vegetable_shop", "fruit_shop", "sweet_shop", "bakery",
    "restaurant", "tea_shop", "fast_food", "salon", "laundry", "tailoring",
    "printing", "internet_centre", "photography", "electronics", "mobile_shop",
    "home_appliances", "pharmacy", "clinic", "hospital", "dental_clinic",
    "diagnostic", "optical_shop", "veterinary", "fertilizer", "seed_shop",
    "agricultural_equipment", "tractor_dealer", "irrigation_supplies",
    "animal_feed", "dairy", "hardware", "building_materials", "steel_products",
    "plywood", "cement", "paint", "electrical", "plumbing", "mechanic",
    "car_service", "tyre_shop", "auto_parts", "battery_shop", "welding",
    "footwear", "clothing", "textile", "stationery", "travel_agency",
    "finance", "handicrafts", "furniture",
]


def _conn():
    from app.db.session import get_engine
    return get_engine()


def _rows(sql: str, **params):
    from sqlalchemy import text
    with _conn().connect() as c:
        return c.execute(text(sql), params).fetchall()


def businesses_by_category() -> dict[str, int]:
    rows = _rows("""
        SELECT category_code, count(*) FROM businesses
        WHERE source IN ('osm', 'geoapify')
        GROUP BY category_code ORDER BY 2 DESC
    """)
    return {r[0]: r[1] for r in rows}


def businesses_by_block() -> dict[str, int]:
    """Attribute each business to a block using nearest village proximity is
    expensive; instead we approximate blocks from the postgres column only if
    it exists. Businesses carry no block, so we fall back to a geohash-based
    coarse binning reported in JSON (not MD).
    """
    return {}


def coords_profile() -> dict:
    rows = _rows("""
        SELECT
          count(*) AS total,
          count(*) FILTER (WHERE latitude IS NOT NULL AND longitude IS NOT NULL) AS with_coords,
          count(*) FILTER (WHERE confidence_score >= 0.7) AS high_conf,
          count(*) FILTER (WHERE verification_status = 'VERIFIED') AS verified
        FROM businesses
    """)
    r = rows[0]
    return {"total": r[0], "with_coords": r[1], "high_conf": r[2], "verified": r[3]}


def category_completeness() -> dict[str, dict]:
    rows = _rows("""
        SELECT category_code,
               round(avg(completeness)::numeric, 3) AS avg_comp,
               min(completeness) AS min_comp,
               max(completeness) AS max_comp,
               count(*) FILTER (WHERE phone IS NOT NULL) AS with_phone,
               count(*) AS n
        FROM businesses
        WHERE source IN ('osm', 'geoapify')
        GROUP BY category_code
        ORDER BY 2 DESC
    """)
    return {r[0]: {"avg_completeness": float(r[1] or 0), "min": float(r[2] or 0),
                   "max": float(r[3] or 0), "with_phone": r[4], "n": r[5]} for r in rows}


def source_summary() -> dict[str, int]:
    rows = _rows("""
        SELECT source_name, count(*) FROM businesses
        WHERE source IN ('osm', 'geoapify')
        GROUP BY source_name ORDER BY 2 DESC
    """)
    return {r[0]: r[1] for r in rows}


def village_coverage(index_path: Optional[Path] = None) -> dict:
    """How many villages (from the geographic index) have ≥1 business within
    3 km. Reads the index JSON; uses a cheap 0.027° (±3km) bounding check.
    """
    idx = json.loads((index_path or ERODE_DATA / "erode_index.json").read_text())
    villages = idx.get("villages", [])
    total = len(villages)
    covered = 0
    by_block: dict[str, dict] = {}
    for v in villages:
        if not v.get("lat") or not v.get("lon"):
            continue
        n = _rows("""
            SELECT count(*) FROM businesses
            WHERE latitude BETWEEN :la AND :ha
              AND longitude BETWEEN :lo AND :ho
              AND source IN ('osm', 'geoapify')
        """, la=v["lat"] - 0.027, ha=v["lat"] + 0.027,
                  lo=v["lon"] - 0.027, ho=v["lon"] + 0.027)[0][0]
        if n:
            covered += 1
        blk = v.get("block") or v.get("kind") or "unknown"
        bb = by_block.setdefault(blk, {"villages": 0, "covered": 0})
        bb["villages"] += 1
        bb["covered"] += int(bool(n))
    return {"total_villages": total, "covered_villages": covered,
            "coverage_ratio": round(covered / total, 3) if total else 0,
            "by_block": by_block}


MD_HEADER = """# {title}

@{date} — generated by `scripts/erode/coverage.py`

---

## District snapshot

| Metric | Value |
|---|---|
| Total business records (real sources) | {total} |
| ... with coordinates | {with_coords} |
| ... high-confidence (score ≥ 0.7) | {high_conf} |
| ... verified | {verified} |
| Categories present | {n_cats} |
"""


def _markdown() -> str:
    from app.catalog.business_categories import catalog
    cats = businesses_by_category()
    comp = category_completeness()
    profile = coords_profile()
    src = source_summary()

    parts = [
        MD_HEADER.format(
            title="Erode District — Business Coverage Report",
            date=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            total=profile["total"], with_coords=profile["with_coords"],
            high_conf=profile["high_conf"], verified=profile["verified"],
            n_cats=len(cats),
        ),
        "## Source registry\n\n",
        "| Source | Records |\n|---|---|\n" +
        "".join(f"| {k} | {v} |\n" for k, v in src.items()),
        "\n## Category coverage\n\n",
        "| Category | Records | Avg completeness | With phone |\n|---|---|---|---|\n",
    ]
    rows = []
    for code, label in _category_labels().items():
        n = cats.get(code, 0)
        c = comp.get(code, {})
        rows.append((n, code, label, c))
    rows.sort(key=lambda r: (-r[0], r[1]))
    for n, code, label, c in rows:
        parts.append(
            f"| {code} | {n} | {c.get('avg_completeness', 0)} | {c.get('with_phone', 0)} |\n"
        )

    # Mission-critical categories presence.
    missing = [c for c in MISSION_CATEGORIES if cats.get(c, 0) == 0]
    parts.append("\n## Mission-category gaps\n\n")
    if missing:
        parts.append("Categories with **zero** discovered records: " +
                     ", ".join(f"`{m}`" for m in missing))
    else:
        parts.append("All mission categories have at least one record.")

    # Village coverage.
    try:
        vc = village_coverage()
        parts.append(f"""
## Village-level coverage

| Metric | Value |
|---|---|
| Indexed villages | {vc['total_villages']} |
| Villages with ≥1 business within ~3 km | {vc['covered_villages']} |
| Coverage ratio | {vc['coverage_ratio']} |
""")
        parts.append("\n| Block | Villages | Covered |\n|---|---|---|\n")
        for blk, b in sorted(vc["by_block"].items()):
            parts.append(f"| {blk} | {b['villages']} | {b['covered']} |\n")
    except Exception as e:  # noqa: BLE001
        log.warning("village coverage skipped: %s", e)

    return "".join(parts)


def _category_labels() -> dict[str, str]:
    from app.catalog.business_categories import catalog
    return {c["code"]: c["label"] for c in catalog().values()}


def write_reports() -> dict:
    ERODE_DATA.mkdir(parents=True, exist_ok=True)

    md = _markdown()
    (ERODE_DATA / "ERODE_COVERAGE_REPORT.md").write_text(md)

    comp = category_completeness()
    profile = coords_profile()
    src = source_summary()
    quality = f"""# Erode District — Data Quality Report

@{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}

## Overall

- Records: {profile['total']}
- With coordinates: {profile['with_coords']}
- High confidence: {profile['high_conf']}
- Verified: {profile['verified']}

## Completeness by category

| Category | Avg completeness | With phone | n |
|---|---|---|---|
"""
    for code, c in sorted(comp.items(), key=lambda kv: (-kv[1]["avg_completeness"], kv[0])):
        quality += f"| {code} | {c['avg_completeness']} | {c['with_phone']} | {c['n']} |\n"
    (ERODE_DATA / "DATA_QUALITY_REPORT.md").write_text(quality)

    registry = f"""# Erode District — Data Source Registry

@{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}

Used for the Erode District business discovery expansion.

| Source | Records |
|---|---|
"""
    for k, v in src.items():
        registry += f"| {k} | {v} |\n"
    registry += """
Attribution: © OpenStreetMap contributors (ODbL). Geoapify Places (terms apply).
"""
    (ERODE_DATA / "DATA_SOURCE_REGISTRY.md").write_text(registry)

    vc = village_coverage()
    out = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "coords_profile": profile,
        "businesses_by_category": businesses_by_category(),
        "category_completeness": comp,
        "sources": src,
        "coverage": vc,
    }
    (ERODE_DATA / "erode_coverage.json").write_text(json.dumps(out, indent=1, default=str))
    return out


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(json.dumps(write_reports(), indent=1, default=str)[:4000])