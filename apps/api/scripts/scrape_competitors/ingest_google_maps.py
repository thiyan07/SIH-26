"""Import scraped Google Maps competitor JSONL into the ``businesses`` table.

Reads the JSONL produced by ``scrape_google_maps.py`` (``data/scrape/google_maps/*.jsonl``)
and upserts real competitor rows with ``source="google_maps"``.

Rules
-----
* Coordinates are required (a listing without lat/lon cannot feed geo queries).
* Dedupe is conservative, mirroring the OSM/Geoapify path: an existing row with
  the same normalized name within ~100 m is updated with any *richer* contact
  detail instead of inserting a duplicate (avoids inflating competitor counts).
* All rows are ``is_demo=False`` and carry transparent provenance + confidence.
* Rating / review count (current-day user signal) are stored in ``metadata_json``
  and surfaced through the API's ``metadata`` for map popups.

Usage
-----
    python -m scripts.scrape_competitors.ingest_google_maps [--category restaurant] [--dry-run]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import sys
from pathlib import Path
from typing import Optional

from sqlalchemy import select

from app.db.models import Business
from app.db.session import session_scope
from app.geo import haversine_km

log = logging.getLogger("ingest.google_maps")

SOURCE = "google_maps"
SOURCE_NAME = "Google Maps"
DATASET_NAME = "google_maps_scrape"
SOURCE_TYPE = "vendor"
MERGE_DISTANCE_M = 100.0
NOW = dt.datetime.now(dt.timezone.utc)

DATA_DIR = Path(__file__).resolve().parents[3] / "data" / "scrape" / "google_maps"


def iter_files(category: Optional[str]) -> list[Path]:
    if not DATA_DIR.exists():
        return []
    return sorted(DATA_DIR.glob(f"{category or '*'}_*.jsonl"))


def _norm(s: Optional[str]) -> str:
    return (s or "").lower().strip()


def _scrub(s: Optional[str]) -> Optional[str]:
    """Drop Google Maps private-use glyphs (e.g. U+F54A renders as a heart)
    that sneak into scraped name/address strings."""
    if not s:
        return s
    return "".join(ch for ch in s if not (0xE000 <= ord(ch) <= 0xF8FF)).strip()


def _existing_by_name_close(db, name: str, lat: float, lon: float) -> Optional[Business]:
    """Existing business (any source) with same normalized name within ~100 m."""
    rows = db.execute(
        select(Business).where(Business.normalized_name == _norm(name))
    ).scalars().all()
    for r in rows:
        try:
            d = haversine_km(r.latitude, r.longitude, lat, lon) * 1000.0
        except TypeError:
            continue
        if d <= MERGE_DISTANCE_M:
            return r
    return None


def ingest_one(row: dict, dry_run: bool) -> dict:
    name = _scrub(row.get("name") or "") or ""
    lat = row.get("latitude")
    lon = row.get("longitude")
    src_id = row.get("source_record_id") or row.get("google_id") or row.get("cid_seed") or row.get("place_url")
    if not name or lat is None or lon is None or not src_id:
        return {"action": "skip", "reason": "no_name_or_coords", "name": name}
    row["address"] = _scrub(row.get("address"))
    row["google_category"] = _scrub(row.get("google_category"))
    norm = _norm(row.get("normalized_name") or name)
    category = row.get("category_code") or "other"
    rating = row.get("rating")
    reviews = row.get("review_count")
    meta = {
        "rating": rating,
        "review_count": reviews,
        "google_category": row.get("google_category"),
        "opening_hours_state": row.get("opening_hours_state"),
        "google_id": row.get("google_id"),
        "cid_seed": row.get("cid_seed"),
        "scrape_queried_at": row.get("queried_at"),
    }
    meta = {k: v for k, v in meta.items() if v is not None and v != []}

    if dry_run:
        return {"action": "would_insert", "name": name, "category": category}

    with session_scope() as db:
        existing_src = db.execute(
            select(Business).where(Business.source == SOURCE, Business.source_id == src_id)
        ).scalars().first()
        if existing_src is not None:
            changed = False
            for field, val in (("phone", row.get("phone")), ("website", row.get("website")),
                               ("opening_hours", row.get("opening_hours")),
                               ("address", row.get("address"))):
                if val and not getattr(existing_src, field):
                    setattr(existing_src, field, val)
                    changed = True
            if row.get("rating") is not None:
                m = dict(existing_src.metadata_json or {})
                new = dict(meta)
                new.update(m)  # keep previously stored extras
                existing_src.metadata_json = new
                changed = True
            existing_src.last_seen_at = NOW
            existing_src.retrieved_at = NOW
            return {"action": "updated", "name": name, "category": category, "merged_into": existing_src.id}

        dup = _existing_by_name_close(db, name, lat, lon)
        merge_into = None
        if dup is not None:
            # Enrich the existing row with exact contact data (no duplicate).
            changed = False
            for field, val in (("address", row.get("address")), ("phone", row.get("phone")),
                               ("website", row.get("website"))):
                if val and not getattr(dup, field):
                    setattr(dup, field, val)
                    changed = True
            if row.get("rating") is not None:
                m = dict(dup.metadata_json or {})
                m.update(meta)
                dup.metadata_json = m
                changed = True
            if changed:
                dup.confidence = "medium"
                dup.verification_status = dup.verification_status or "PARTIALLY_VERIFIED"
            dup.last_seen_at = NOW
            merge_into = dup.id

        if merge_into is None:
            db.add(Business(
                name=name,
                normalized_name=norm,
                category_code=category,
                subcategory=row.get("google_category"),
                latitude=float(lat),
                longitude=float(lon),
                address=row.get("address"),
                phone=row.get("phone"),
                website=row.get("website"),
                opening_hours=row.get("opening_hours"),
                brand=None,
                source=SOURCE,
                source_id=src_id,
                source_type=SOURCE_TYPE,
                source_name=SOURCE_NAME,
                dataset_name=DATASET_NAME,
                source_url=row.get("place_url"),
                retrieved_at=NOW,
                source_updated_at=NOW,
                first_seen_at=NOW,
                last_seen_at=NOW,
                confidence_score=0.9 if rating is not None else 0.6,
                verification_status="PARTIALLY_VERIFIED",
                confidence="high" if rating is not None else "medium",
                is_demo=False,
                is_estimate=False,
                completeness=0.8 if rating is not None else 0.6,
                metadata_json=meta or None,
                tags={"source": SOURCE},
            ))
            return {"action": "inserted", "name": name, "category": category}
        return {"action": "merged", "name": name, "category": category, "merged_into": merge_into}


def main(argv=None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    ap = argparse.ArgumentParser(description="Import Google Maps scraper JSONL -> businesses")
    ap.add_argument("--category", default=None, help="limit to one category (file prefix)")
    ap.add_argument("--dry-run", action="store_true", help="report what would happen only")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    files = iter_files(args.category)
    if not files:
        log.error("no scraped JSONL found under %s (run scrape_google_maps.py first)", DATA_DIR)
        return 1

    stats = {"inserted": 0, "updated": 0, "merged": 0, "skip": 0}
    for f in files:
        n = 0
        with f.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    log.warning("bad JSON line in %s", f)
                    continue
                res = ingest_one(row, dry_run=args.dry_run)
                action = res["action"]
                if action in ("inserted", "would_insert"):
                    stats["inserted"] += 1
                elif action == "updated":
                    stats["updated"] += 1
                elif action == "merged":
                    stats["merged"] += 1
                else:
                    stats["skip"] += 1
                n += 1
        log.info("%s: %d records (%s)", f.name, n, ("dry-run" if args.dry_run else "imported"))

    log.info("summary: %s", stats)
    return 0


if __name__ == "__main__":
    sys.exit(main())