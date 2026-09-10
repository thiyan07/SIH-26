"""Derive Erode district Location rows from scraped Google Maps coverage.

The ``locations`` table is the source behind the location picker
(``/locations/search``). It is only sparsely seeded, so the picker shows a
handful of towns while the scraped competitor data actually covers the whole
district.

This script backfills the missing towns from the *real, already-ingested*
Google Maps business coordinates (``data/scrape/google_maps/*.jsonl``): each
record is tagged to the Erode town named in the query that scraped it, and the
town's representative coordinate is the *median* of its businesses' points
(``geo_precision="centroid"``). This is used to *locate* the town, never to
claim point precision.

Honesty notes
-------------
* ``geo_precision="centroid"`` and ``is_demo=False``; the coordinate is a
  centroid of scraped listings for that town, clearly the median of its
  recorded business locations, not an official Census coordinate.
* Covers only towns the scraper actually queried in Erode district, so the
  picker shows where the app genuinely has coverage.
* Upserts are idempotent and ``--dry-run`` is read-only.

Usage
-----
    python -m scripts.seed_locations.derive_erode_locations [--dry-run]
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

log = logging.getLogger("seed.erode_locations")

STATE = "Tamil Nadu"
DISTRICT = "Erode"
# Towns the Erode scraper queried, ordered so more-specific names are matched
# before their prefixes (e.g. bhavanisagar before bhavani).
TOWN_KEYS = [
    "perundurai", "anthiyur", "sathyamangalam", "modakkurichi",
    "gobichettipalayam", "bhavanisagar", "bhavani", "chennimalai",
    "nambiyur", "ammapet", "talavadi", "kodumudi",
    "thookanaickenpalayam", "avalpoondurai", "erode",
]

DATA_DIR = Path(__file__).resolve().parents[3] / "data" / "scrape" / "google_maps"

DATASET_NAME = "google_maps_scrape"
SOURCE_NAME = "Google Maps scraper (crowd-sourced listings)"
SOURCE_TYPE = "vendor"
SOURCE_URL = "https://www.google.com/maps"


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _tag_town(query: str) -> str | None:
    """Return the named Erode town in a scrape query, or None."""
    q = _norm(query)
    for t in TOWN_KEYS:
        if t not in q:
            continue
        # Bare "erode" only counts when no more specific town is named.
        if t == "erode" and any(k in q for k in TOWN_KEYS if k != "erode"):
            continue
        # Prevent "bhavani" stealing "bhavanisagar" points unless the query is
        # really about bhavani (bhavanisagar is checked first anyway).
        if t == "bhavani" and q.startswith("bhavanisagar"):
            continue
        return t
    return None


def derive() -> dict[str, dict]:
    """Compute one centroid (median lat/lon) per scraper-queried Erode town."""
    lat: dict[str, list[float]] = defaultdict(list)
    lon: dict[str, list[float]] = defaultdict(list)
    for f in sorted(DATA_DIR.glob("*.jsonl")):
        m = re.search(r"__(\d{8}T\d{6})__(.*)\.jsonl$", f.name)
        if not m:
            continue
        tag = _tag_town(urllib.parse.unquote(m.group(2)))
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

    cents = {}
    for t in TOWN_KEYS:
        if lat.get(t):
            cents[t] = {
                "latitude": round(statistics.median(lat[t]), 6),
                "longitude": round(statistics.median(lon[t]), 6),
                "n": len(lat[t]),
            }
    return cents


def upsert(cents: dict[str, dict], *, dry_run: bool) -> dict:
    """Upsert a Location row per town. Returns per-action tallies."""
    stats = {"created": 0, "updated": 0, "kept": 0}
    with session_scope() as db:
        # Match existing rows case-insensitively so we never duplicate a town
        # that already exists with different casing (e.g. test-seeded
        # "Perundurai" vs derived "perundurai").
        existing_rows = list(db.execute(
            select(Location).where(Location.state == STATE,
                                   Location.district == DISTRICT,
                                   Location.village.isnot(None))
        ).scalars())
        existing = {l.village.lower(): l for l in existing_rows}
        for town, c in cents.items():
            loc = existing.get(town.lower())
            values = dict(
                block=town, village=town,
                latitude=c["latitude"], longitude=c["longitude"],
                geo_precision="centroid",
                source_name=SOURCE_NAME, source_url=SOURCE_URL,
                dataset_name=DATASET_NAME, source_type=SOURCE_TYPE,
                retrieved_at=dt.datetime.now(dt.timezone.utc),
                geographic_level="village", confidence="medium",
                is_estimate=True, is_demo=False,
                methodology=("Coordinate is the median centroid of the Google "
                             "Maps scraped listings queried for this town in "
                             "Erode district; a locator, not a precise point."),
                metadata_json={"scraped_listing_count": c["n"],
                               "derived_from": "google_maps_scrape"},
            )
            if loc is None:
                if not dry_run:
                    db.add(Location(state=STATE, district=DISTRICT, **values))
                stats["created"] += 1
            else:
                # Refresh the derived centroid. Preserve the pre-existing
                # (canonically-cased) display name so the picker stays tidy.
                if (loc.latitude != c["latitude"] or loc.longitude != c["longitude"]):
                    if not dry_run:
                        loc.latitude, loc.longitude = c["latitude"], c["longitude"]
                        loc.geo_precision = "centroid"
                        loc.metadata_json = values["metadata_json"]
                        if not loc.source_name:
                            loc.source_name = SOURCE_NAME
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
    ap = argparse.ArgumentParser(description="Backfill Erode Location rows from scraped GM coverage")
    ap.add_argument("--dry-run", action="store_true", help="report only, write nothing")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    cents = derive()
    if not cents:
        log.error("no scraped GM data found under %s", DATA_DIR)
        return 1
    log.info("derived %d Erode towns from scraped Google Maps coordinates", len(cents))
    for t, c in cents.items():
        log.info("  %-22s n=%-5d centroid=(%.5f, %.5f)", t, c["n"], c["latitude"], c["longitude"])

    stats = upsert(cents, dry_run=args.dry_run)
    mode = "dry-run (read-only)" if args.dry_run else "applied"
    log.info("locations %s: created=%d updated=%d kept=%d",
             mode, stats["created"], stats["updated"], stats["kept"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
