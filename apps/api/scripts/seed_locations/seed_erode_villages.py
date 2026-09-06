"""Seed Erode district village-level ``Location`` rows from the Census 2011 directory.

The ``locations`` table is the source behind the location picker
(``/locations/search``). It currently holds town/block-level rows only; this
script adds the real Census villages (``data/scrape/erode_villages/*.jsonl``),
each tagged with its block so the picker can offer village granularity.

Coordinate honesty
------------------
The Census directory has no coordinates, so each village inherits the *median
centroid* of the scraped Google Maps business points for its CD block
(``geo_precision="village"``, ``is_estimate=True``). The coordinate locates the
block, not the exact village point. The authoritative Census identity (census
code, population, households, gram panchayat) is preserved in ``metadata_json``.

Villages whose name equals the block name (the block HQ: Anthiyur, Bhavani,
Chennimalai, Talavadi) collide with the existing town rows (block=village=name)
and are skipped -- the town row already represents that place.

Usage
-----
    python -m scripts.seed_locations.seed_erode_villages [--dry-run]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import re
import statistics
import sys
import urllib.parse
from collections import defaultdict
from pathlib import Path

from sqlalchemy import select

from app.db.models import Location
from app.db.session import session_scope

log = logging.getLogger("seed.erode_villages")

STATE = "Tamil Nadu"
DISTRICT = "Erode"

TOWN_KEYS = [
    "perundurai", "anthiyur", "sathyamangalam", "modakkurichi",
    "gobichettipalayam", "bhavanisagar", "bhavani", "chennimalai",
    "nambiyur", "ammapet", "talavadi", "kodumudi",
    "thookanaickenpalayam", "avalpoondurai", "erode",
]
# Census block name -> town query key used to carve the centroid from the scrape.
BLOCK_TO_KEY = {
    "Ammapet": "ammapet", "Anthiyur": "anthiyur", "Bhavani": "bhavani",
    "Bhavanisagar": "bhavanisagar", "Chennimalai": "chennimalai",
    "Erode": "erode", "Gobichettipalayam": "gobichettipalayam",
    "Kodumudi": "kodumudi", "Modakkurichi": "modakkurichi",
    "Nambiyur": "nambiyur", "Perundurai": "perundurai",
    "Sathyamangalam": "sathyamangalam", "Talavadi": "talavadi",
    "Thookanaickenpalayam": "thookanaickenpalayam",
}

GM_DIR = Path(__file__).resolve().parents[3] / "data" / "scrape" / "google_maps"
CENSUS_FILE = Path(__file__).resolve().parents[2] / "data" / "scrape" / \
    "erode_villages" / "erode_villages.jsonl"

DATASET_NAME = "census_2011_erode_villages"
SOURCE_NAME = "Census of India 2011 (Erode district village directory)"
SOURCE_TYPE = "government"
SOURCE_URL = "https://censusindia.gov.in/"


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _block_centroids() -> dict[str, dict]:
    """Median centroid per CD block from the scraped Google Maps listings."""
    lat: dict[str, list[float]] = defaultdict(list)
    lon: dict[str, list[float]] = defaultdict(list)
    for f in sorted(GM_DIR.glob("*.jsonl")):
        m = re.search(r"__(\d{8}T\d{6})__(.*)\.jsonl$", f.name)
        if not m:
            continue
        q = _norm(urllib.parse.unquote(m.group(2)))
        tag = None
        for t in TOWN_KEYS:
            if t not in q:
                continue
            if t == "erode" and any(k in q for k in TOWN_KEYS if k != "erode"):
                continue
            if t == "bhavani" and q.startswith("bhavanisagar"):
                continue
            tag = t
            break
        if not tag:
            continue
        with f.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if row.get("latitude") is None or row.get("longitude") is None:
                    continue
                lat[tag].append(float(row["latitude"]))
                lon[tag].append(float(row["longitude"]))
    out = {}
    for t in TOWN_KEYS:
        if lat.get(t):
            out[t] = {
                "latitude": round(statistics.median(lat[t]), 6),
                "longitude": round(statistics.median(lon[t]), 6),
                "n": len(lat[t]),
            }
    return out


def _census_villages():
    if not CENSUS_FILE.exists():
        raise FileNotFoundError(f"missing census village file: {CENSUS_FILE}")
    with CENSUS_FILE.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def upsert(*, dry_run: bool) -> dict:
    cents = _block_centroids()
    stats = {"created": 0, "updated": 0, "kept": 0, "skipped_block_hq": 0, "no_coords": 0}

    with session_scope() as db:
        existing_rows = list(db.execute(
            select(Location).where(Location.state == STATE,
                                   Location.district == DISTRICT,
                                   Location.block.isnot(None),
                                   Location.village.isnot(None))
        ).scalars())
        existing = {(_norm(r.block), _norm(r.village)): r for r in existing_rows}

        for r in _census_villages():
            block = r.get("block")
            village = r.get("village")
            if not block or not village:
                continue
            if _norm(block) == _norm(village):
                stats["skipped_block_hq"] += 1
                continue
            key = BLOCK_TO_KEY.get(block)
            c = cents.get(key) if key else None
            if not c:
                stats["no_coords"] += 1
                log.warning("no centroid for block %s (village %s); skipped", block, village)
                continue
            loc = existing.get((_norm(block), _norm(village)))
            values = dict(
                block=block, village=r["village"],
                latitude=c["latitude"], longitude=c["longitude"],
                geo_precision="village",
                source_name=SOURCE_NAME, source_url=SOURCE_URL,
                dataset_name=DATASET_NAME, source_type=SOURCE_TYPE,
                reference_year=int(r.get("census_year", 2011)),
                retrieved_at=dt.datetime.now(dt.timezone.utc),
                geographic_level="village", confidence="medium",
                is_estimate=True, is_demo=False,
                methodology=("Coordinate is the median centroid of the scraped "
                             "Google Maps listings for this village's CD block; "
                             "locates the block, not the village point."),
                metadata_json={
                    "census_code": r.get("census_code"),
                    "population": r.get("population"),
                    "households": r.get("households"),
                    "area_ha": r.get("area_ha"),
                    "gram_panchayat": r.get("gram_panchayat"),
                    "census_year": r.get("census_year"),
                    "block_listing_count": c["n"],
                    "derived_from": "google_maps_scrape",
                },
            )
            if loc is None:
                if not dry_run:
                    db.add(Location(state=STATE, district=DISTRICT, **values))
                stats["created"] += 1
            else:
                if (loc.latitude != c["latitude"] or loc.longitude != c["longitude"]):
                    if not dry_run:
                        loc.latitude, loc.longitude = c["latitude"], c["longitude"]
                        loc.geo_precision = "village"
                        loc.metadata_json = values["metadata_json"]
                    stats["updated"] += 1
                else:
                    stats["kept"] += 1

        if not dry_run:
            db.commit()
        else:
            db.rollback()
    return stats


def main(argv=None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    ap = argparse.ArgumentParser(description="Seed Erode village Location rows from Census 2011")
    ap.add_argument("--dry-run", action="store_true", help="report only, write nothing")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    stats = upsert(dry_run=args.dry_run)
    mode = "dry-run (read-only)" if args.dry_run else "applied"
    log.info("villages %s: created=%d updated=%d kept=%d skipped_block_hq=%d no_coords=%d",
             mode, stats["created"], stats["updated"], stats["kept"],
             stats["skipped_block_hq"], stats["no_coords"])
    return 0


if __name__ == "__main__":
    sys.exit(main())