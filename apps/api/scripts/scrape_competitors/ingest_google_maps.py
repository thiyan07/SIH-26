"""Import scraped Google Maps competitor JSONL into the ``businesses`` table.

Reads the JSONL produced by ``scrape_google_maps.py`` (``data/scrape/google_maps/*.jsonl``)
and upserts real competitor rows with ``source="google_maps"``.

Rules
-----
* Coordinates are required (a listing without lat/lon cannot feed geo queries).
* Dedupe is conservative, mirroring the OSM/Geoapify path: an existing row with
  the same normalized name within ~100 m is updated with any *richer* contact
  detail instead of inserting a duplicate (avoids inflating competitor counts).
* Cross-source provenance is preserved on merge: when a scraped Google Maps
  record matches an existing canonical row (e.g. an OpenStreetMap business for
  the same physical store), Google Maps is recorded as an *additional*
  confirming source on that row (``tags["sources"]`` + ``metadata_json["google_maps"]``)
  rather than a second row, so the answer to "OSM only / GM only / both" stays
  truthful and competitor counts are not inflated by the same store.
* All rows are ``is_demo=False`` and carry transparent provenance + confidence.
* Rating / review count (current-day user signal) are stored in ``metadata_json``
  and surfaced through the API's ``metadata`` for map popups.
* ``--dry-run`` is DB-aware and read-only: it reports would-insert/would-update/
  would-merge/would-skip/would-noop from real DB state without writing anything.

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


class ExistingIndex:
    """In-memory lookup over existing ``Business`` rows.

    The naive per-record ``select`` path costs one remote round-trip per row
    (~5000 over a remote DB), which makes the full ingest take many minutes.
    Instead we load every existing row once and resolve the two extra probes
    (is this ``(source, source_id)`` already known? does another source have
    this name within ~100 m?) entirely in memory:

    * ``by_src_id``      : ``(source, source_id) -> Business``  (idempotency)
    * ``by_norm_name``   : ``normalized_name  -> [Business]``   (merge probe)

    Newly inserted/updated rows inside a batched run are added to the index as
    the run progresses so later records can still merge against them.
    """

    def __init__(self, rows: list[Business]):
        self.by_src_id: dict[tuple[str, str], Business] = {}
        self.by_norm_name: dict[str, list[Business]] = {}
        for b in rows:
            self.add(b)

    def add(self, b: Business) -> None:
        if b.source and b.source_id:
            self.by_src_id[(b.source, b.source_id)] = b
        if b.normalized_name:
            self.by_norm_name.setdefault(b.normalized_name, []).append(b)

    def by_src(self, source: str, src_id: str) -> Optional[Business]:
        return self.by_src_id.get((source, src_id))

    def close_match(self, name: str, lat: float, lon: float) -> Optional[Business]:
        """Any source's row with this normalized name within ~100 m."""
        for b in self.by_norm_name.get(_norm(name) or "", ()):
            try:
                dist_m = haversine_km(b.latitude, b.longitude, lat, lon) * 1000.0
            except TypeError:
                continue
            if dist_m <= MERGE_DISTANCE_M:
                return b
        return None


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


def _provenance_patch(b: Business, row: dict, meta: dict) -> dict:
    """Compute the cross-source provenance update for a canonical row (pure).

    The canonical row keeps its original ``source`` (e.g. ``osm``) so
    ``uq_business_source_id`` stays valid and unique-competitor counts are not
    inflated. ``tags["sources"]`` and ``metadata_json["google_maps"]`` record
    that Google Maps also confirmed this business.

    Returns ``{"tags": …, "metadata_json": …, "changed": bool}`` without
    mutating ``b``, so a dry-run can report would changes accurately.
    """
    tags = dict(b.tags or {})
    sources = list(tags.get("sources") or [])
    base = tags.get("source") or getattr(b, "source", None)
    if base and base not in sources:
        sources.append(base)
    if SOURCE not in sources:
        sources.append(SOURCE)
    tags["sources"] = sorted(sources)
    meta = dict(meta)
    if row.get("place_url"):
        meta["place_url"] = row.get("place_url")
    m = dict(b.metadata_json or {})
    gm = dict(m.get("google_maps") or {})
    gm.update({k: v for k, v in meta.items() if v is not None})
    changed = m.get("google_maps") != gm or b.tags != tags
    m["google_maps"] = gm
    return {"tags": tags, "metadata_json": m, "changed": changed}


def _merge_provenance(b: Business, row: dict, meta: dict) -> bool:
    """Apply the cross-source provenance update to a canonical row."""
    p = _provenance_patch(b, row, meta)
    b.tags = p["tags"]
    b.metadata_json = p["metadata_json"]
    return p["changed"]


def _enrich(b: Business, row: dict, meta: dict) -> dict:
    """Plan contact/provenance enrichment for an existing row (pure, no writes).

    Returns ``{"changed": bool, "fields": {field: value}, "provenance": {…}}``
    so a dry-run can classify would-update vs would-merge vs would-noop without
    mutating the row.
    """
    fields = {}
    for field, val in (("phone", row.get("phone")), ("website", row.get("website")),
                       ("opening_hours", row.get("opening_hours")),
                       ("address", row.get("address"))):
        if val and not getattr(b, field):
            fields[field] = val
    prov = _provenance_patch(b, row, meta)
    return {"changed": bool(fields) or bool(prov["changed"]),
            "fields": fields, "provenance": prov}


def _plan(idx_or_db, row: dict, src_id: str, name: str, lat: float, lon: float,
          norm: str, category: str, meta: dict) -> dict:
    """Decide the action for one record (pure, read-only).

    ``idx_or_db`` may be an :class:`ExistingIndex` (fast, batched path) or a DB
    session from which the index is derived on the fly (test/single-record path).

    Returns one of: skip / updated / merged / noop / insert.
    """
    idx = idx_or_db if isinstance(idx_or_db, ExistingIndex) else ExistingIndex(
        list(idx_or_db.execute(select(Business)).scalars()))
    existing_src = idx.by_src(SOURCE, src_id)

    if existing_src is not None:
        # Idempotent re-run: same (source, source_id) row already present.
        applied = _enrich(existing_src, row, meta)
        action = "updated" if applied["changed"] else "noop"
        return {"action": action, "name": name, "category": category,
                "merged_into": existing_src.id, "target": existing_src,
                "patch": applied}

    dup = idx.close_match(name, lat, lon)
    if dup is not None:
        # Name + ~100 m match across sources (e.g. an OSM row already exists for
        # this store). Record Google Maps as an ADDITIONAL confirming source on
        # the canonical row instead of inserting a second row, so the answer to
        # "OSM only / GM only / both" stays truthful and competitor counts are
        # not inflated by the same physical store.
        applied = _enrich(dup, row, meta)
        action = "merged" if applied["changed"] else "noop"
        return {"action": action, "name": name, "category": category,
                "merged_into": dup.id, "target": dup, "patch": applied}

    return {"action": "insert", "name": name, "category": category, "patch": None}


def _apply(db, plan: dict, row: dict, lat: float, lon: float, norm: str,
           rating, meta: dict) -> dict:
    """Apply a plan made by ``_plan`` inside a write session."""
    action = plan["action"]
    if action == "skip":
        return plan
    target = plan.get("target")
    if target is not None:
        patch = plan["patch"]
        for field, val in patch["fields"].items():
            setattr(target, field, val)
        target.tags = patch["provenance"]["tags"]
        target.metadata_json = patch["provenance"]["metadata_json"]
        if action == "merged":
            target.confidence = "medium"
            target.verification_status = target.verification_status or "PARTIALLY_VERIFIED"
        target.last_seen_at = NOW
        target.retrieved_at = NOW
        return plan
    if action in ("updated", "merged"):
        # Race: target vanished between planning and apply; fall back to insert.
        action = "insert"
    if action == "insert":
        new = Business(
            name=row.get("name"),
            normalized_name=norm,
            category_code=plan["category"],
            subcategory=row.get("google_category"),
            latitude=float(lat),
            longitude=float(lon),
            address=row.get("address"),
            phone=row.get("phone"),
            website=row.get("website"),
            opening_hours=row.get("opening_hours"),
            brand=None,
            source=SOURCE,
            source_id=row.get("source_record_id") or row.get("google_id") or row.get("cid_seed") or row.get("place_url"),
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
            metadata_json=({"google_maps": meta} if meta else None),
            tags={"source": SOURCE, "sources": [SOURCE]},
        )
        db.add(new)
        return {"action": "inserted", "name": plan["name"], "category": plan["category"], "row": new}
    return plan


def ingest_one(row: dict, dry_run: bool, db=None, idx: ExistingIndex | None = None) -> dict:
    """Ingest a single scraped record, returning its action + stats payload.

    ``idx`` carries the in-memory index of existing rows. When given with
    ``db`` (batched mode) the plan/apply runs inside that open session and the
    index is updated with any row this call inserts/merges so later records see
    it. Otherwise a fresh session is opened per record (slow but
    self-contained; used by the CLI dry-run fallback and unit tests).
    """
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
    meta = {
        "rating": rating,
        "review_count": row.get("review_count"),
        "google_category": row.get("google_category"),
        "opening_hours_state": row.get("opening_hours_state"),
        "google_id": row.get("google_id"),
        "cid_seed": row.get("cid_seed"),
        "scrape_queried_at": row.get("queried_at"),
    }
    meta = {k: v for k, v in meta.items() if v is not None and v != []}

    def _run(sess, index):
        plan = _plan(index, row, src_id, name, lat, lon, norm, category, meta)
        action = plan["action"]
        if dry_run:
            mapped = {"insert": "would_insert", "updated": "would_update",
                      "merged": "would_merge", "noop": "would_noop", "skip": "skip"}
            return {"action": mapped[action], "name": plan.get("name", name),
                    "category": plan.get("category", category),
                    "merged_into": plan.get("merged_into"),
                    "changed": plan["patch"]["changed"] if plan.get("patch") else (action == "insert")}
        result = _apply(sess, plan, row, lat, lon, norm, rating, meta)
        # Register the row this call created/touched so later records in the
        # same run can merge against it via the in-memory index.
        if result.get("row") is not None:
            index.add(result["row"])
        return result

    if db is not None:
        if idx is None:
            # Derive the index from every row the session already knows about:
            # committed rows plus rows pending in this transaction (db.new), so
            # a repeated source id inside one transaction reconciles without a
            # per-record remote flush.
            rows = list(db.execute(select(Business)).scalars())
            pending = [o for o in db.new if isinstance(o, Business)]
            if pending:
                rows = [b for b in rows if b not in pending] + pending
            index = ExistingIndex(rows)
        else:
            index = idx
        return _run(db, index)
    with session_scope() as db:
        rows = list(db.execute(select(Business)).scalars())
        pending = [o for o in db.new if isinstance(o, Business)]
        if pending:
            rows = [b for b in rows if b not in pending] + pending
        index = ExistingIndex(rows)
        return _run(db, index)


def _load_rows(files):
    """Yield every JSONL record once. A record is skipped if it lacks a usable
    source id / name / coordinates (mirrors `ingest_one`'s skip rule) or is
    malformed JSON."""
    for f in files:
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
                src_id = row.get("source_record_id") or row.get("google_id") or row.get("cid_seed") or row.get("place_url")
                if not src_id or not (row.get("name") or "").strip() or \
                   row.get("latitude") is None or row.get("longitude") is None:
                    continue
                yield row


def _dedup_by_source_id(rows):
    """Collapse duplicate scrape records of the *same Google place* into a
    single best record per source id. A place scraped under N queries must map
    to exactly one canonical row, else competitor counts inflate."

    Best record preference: more reviews, then higher rating, then most recent.
    """
    best = {}
    for row in rows:
        src_id = row.get("source_record_id") or row.get("google_id") or row.get("cid_seed") or row.get("place_url")
        cur = best.get(src_id)
        if cur is None:
            best[src_id] = row
            continue
        def score(r):
            return (r.get("review_count") or 0, r.get("rating") or 0.0, r.get("queried_at") or "")
        if score(row) > score(cur):
            best[src_id] = row
    return list(best.values())


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

    stats = {"inserted": 0, "updated": 0, "merged": 0, "noop": 0, "skip": 0}
    # Best-record-per-place first: 19k raw records collapse to ~5k unique
    # source ids. This both cuts DB round-trips ~4x and guarantees a scraped
    # place is never double-counted (every Google place -> exactly one row).
    raw = list(_load_rows(files))
    unique = _dedup_by_source_id(raw)
    log.info("loaded %d raw records -> %d unique places (per source id)", len(raw), len(unique))
    # Single session for the whole run: remote DB, avoid one round-trip per
    # record. Dry-run uses a read-only session rolled back on exit, so nothing
    # is persisted. Build the existing-row index once so the two lookups per
    # record run in memory instead of ~N remote round-trips.
    with session_scope() as db:
        existing_rows = list(db.execute(select(Business)).scalars())
        index = ExistingIndex(existing_rows)
        for i, row in enumerate(unique, 1):
            res = ingest_one(row, dry_run=args.dry_run, db=db, idx=index)
            action = res["action"]
            if action in ("inserted", "would_insert"):
                stats["inserted"] += 1
            elif action in ("updated", "would_update"):
                stats["updated"] += 1
            elif action in ("merged", "would_merge"):
                stats["merged"] += 1
            elif action in ("noop", "would_noop"):
                stats["noop"] += 1
            else:
                stats["skip"] += 1
            # Flush in big batches to bound the number of remote round-trips
            # (a per-record flush over a remote DB is what made the apply take
            # minutes). The in-memory index already reconciles repeated source
            # ids, so we only need the DB to see rows periodically.
            if not args.dry_run and i % 1000 == 0:
                db.flush()
        if args.dry_run:
            db.rollback()  # read-only; discard the (unflushed) transaction
        else:
            db.commit()

    log.info("summary: %s", stats)
    return 0


if __name__ == "__main__":
    sys.exit(main())
