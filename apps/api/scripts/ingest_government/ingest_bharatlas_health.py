"""Erode health-establishment ingest from the Bharat Atlas keyless API.

Bharat Atlas (https://bharatlas.com) exposes curated, keyless layers over
openly-licensed official data.  Its ``nic_health`` layer carries NIC / Ministry
of Health & Family Welfare health establishments (sub-centres, PHCs, CHCs,
hospitals) as points with real coordinates under the Government Open Data
License (GODL-India); for our Erode focus it resolves to ~250 establishments.

This pass fetches the Erode slice and stores each establishment as an
``InfrastructurePoint`` (kind ``hospital``) with full provenance.  Nothing is
estimated or invented: coordinates come straight from the source, and the same
DB-level ``uq_infrastructure_real_dedupe`` guard that protects OSM rows keeps
official re-runs from duplicating facilities.

Usage:
  python -m scripts.ingest_government.ingest_bharatlas_health [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone

from app.db.models import DataSnapshot, InfrastructurePoint
from app.db.session import session_scope
from app.log import log_event
from scripts.ingest_government.ingest import register_data_source

log = logging.getLogger("ingest_bharatlas_health")

# bharatlas API base (keyless, read-only, 120 req/min).  Layer: NIC health
# establishments -> source NIC / MoHFW (GODL-India licence).
API = "https://bharatlas.com/api/v1"
HEALTH_LAYER = "nic_health"
UA = {"User-Agent": "GramBizAI/1.0 (erode census research; contact: dev)"}

SOURCE_KEY = "bharatlas_health"
SOURCE_NAME = "NIC health facilities (GODL-India) via Bharat Atlas"  # canonical; mirrors data_sources.py
DATASET_NAME = "NIC health establishments (GODL-India, via Bharat Atlas nic_health layer)"
SOURCE_URL = "https://bharatlas.com"


def _fetch_rows(district: str = "ERODE") -> list[dict]:
    """Fetch the full Erode slice of the health layer (paginated)."""
    url = f"{API}/layers/{HEALTH_LAYER}/query"
    rows: list[dict] = []
    offset, page = 0, 0
    while True:
        q = dict(where=f"district={district}", limit="500")
        if offset:
            q["offset"] = str(offset)
        params = urllib.parse.urlencode(q)
        with urllib.request.urlopen(  # noqa: S310 - bharatlas keyless public API
                urllib.request.Request(f"{url}?{params}", headers=UA), timeout=30) as resp:
            payload = json.load(resp)
        data = payload.get("data") or {}
        batch = data.get("rows", [])
        rows.extend(batch)
        total = int(data.get("total") or 0)
        offset += len(batch) or 500
        page += 1
        if offset >= total or page >= 40:
            break
    return rows


def main(argv=None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    ap = argparse.ArgumentParser()
    ap.add_argument("--district", default="ERODE")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    snapshot = DataSnapshot(job_name="bharatlas_health_erode", status="running",
                            records_ingested=0, started_at=datetime.now(timezone.utc))
    with session_scope() as s:
        register_data_source(
            s, SOURCE_KEY, SOURCE_NAME, "infrastructure", "infrastructure_points",
            "NIC health establishments (GODL-India) via the Bharat Atlas keyless "
            "API; coordinates come straight from the source, never estimated.",
            is_demo=False)
        s.flush()

        rows = _fetch_rows(args.district)
        existing = {
            p.source_id for p in s.query(InfrastructurePoint).filter(
                InfrastructurePoint.source_name == SOURCE_NAME,
                InfrastructurePoint.source_id.isnot(None),
            ).all()
        }
        now = datetime.now(timezone.utc)
        added, skipped = 0, 0
        for r in rows:
            lat, lon = r.get("_lat"), r.get("_lng")
            name = (r.get("name") or "").strip()
            sid = str(r.get("source_id") or "").strip()
            if lat is None or lon is None or not name or not sid:
                skipped += 1
                continue
            if sid in existing:
                skipped += 1
                continue
            if args.dry_run:
                continue
            s.add(InfrastructurePoint(
                kind="hospital", name=name, latitude=float(lat), longitude=float(lon),
                source_id=sid,
                metadata_json={
                    "facility_type": r.get("type"),
                    "place": r.get("place"),
                    "village_id": r.get("village_id"),
                    "layer": r.get("layer"),
                    "district": r.get("district"),
                    "state": r.get("state"),
                },
                source_name=SOURCE_NAME,
                source_url=SOURCE_URL,
                dataset_name=DATASET_NAME,
                source_type="government",
                retrieved_at=now,
                geographic_level="point",
                confidence="high",
                is_estimate=False,
                is_demo=False,
                methodology="Point = NIC health establishment from Bharat Atlas "
                            "nic_health layer (GODL-India); Erode district slice.",
            ))
            existing.add(sid)
            added += 1

        if args.dry_run:
            print(f"[dry-run] would store {len(rows) - skipped} NIC health facilities "
                  f"({args.district}); {skipped} existing/invalid")
            snapshot.status = "dry_run"
            snapshot.records_ingested = added
            snapshot.finished_at = datetime.now(timezone.utc)
            s.add(snapshot)
            return 0

        snapshot.records_ingested = added
        snapshot.status = "completed" if added else "no_rows"
        snapshot.finished_at = datetime.now(timezone.utc)
        s.add(snapshot)
        log_event("ingest", job="erode_bharatlas_health",
                  facilities_added=added, facilities_skipped=skipped,
                  total_fetched=len(rows), status="completed")
        log.info("NIC health (Erode): %d added, %d skipped, %d fetched",
                 added, skipped, len(rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())
