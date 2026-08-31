"""Erode admin-boundary registry from the Bharat Atlas keyless API.

Bharat Atlas (https://bharatlas.com) exposes curated, keyless layers over
openly-licensed official data.  Its ``lgd_districts`` / ``lgd_blocks`` layers
carry the Local Government Directory (LGD, CC0-1.0) administrative names and
Census-2011 codes for Erode district and its 13 block panchayat unions.

This pass stores those real names/codes as ``administrative_boundaries`` rows so
the block and district registries can be joined against location and statistical
tables by code, not only by name.  The API exposes no attribute centroids for
these polygon layers, so no coordinates are written (never approximated).

Usage:
  python -m scripts.ingest_government.ingest_bharatlas_boundaries [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone

from app.db.models import AdministrativeBoundary, DataSnapshot
from app.db.session import session_scope
from app.log import log_event
from scripts.ingest_government.ingest import register_data_source

log = logging.getLogger("ingest_bharatlas_boundaries")

# bharatlas API base (keyless, read-only, 120 req/min).  Layers: LGD districts
# + LGD blocks -> Local Government Directory (CC0-1.0).
API = "https://bharatlas.com/api/v1"
UA = {"User-Agent": "GramBizAI/1.0 (erode census research; contact: dev)"}

SOURCE_KEY = "bharatlas_boundaries"
SOURCE_NAME = "LGD administrative boundaries via Bharat Atlas"  # canonical; mirrors data_sources.py
DATASET_NAME = "Local Government Directory districts/blocks (via Bharat Atlas lgd layers)"
SOURCE_URL = "https://bharatlas.com"


def _fetch_rows(layer: str, where: str) -> list[dict]:
    url = f"{API}/layers/{layer}/query"
    rows: list[dict] = []
    offset, page = 0, 0
    while True:
        q = dict(where=where, limit="500")
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


def _district_rows():
    return _fetch_rows("lgd_districts", "dtname=Erode")


def _block_rows():
    return _fetch_rows("lgd_blocks", "district=Erode")


def _title(name: str | None) -> str | None:
    return name.title() if name else None


def main(argv=None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    snapshot = DataSnapshot(job_name="bharatlas_boundaries_erode", status="running",
                            records_ingested=0, started_at=datetime.now(timezone.utc))
    with session_scope() as s:
        register_data_source(
            s, SOURCE_KEY, SOURCE_NAME, "infrastructure", "administrative_boundaries",
            "LGD district/block codes via the Bharat Atlas keyless API; names and "
            "codes come straight from Local Government Directory. No coordinates "
            "are written (the API exposes no centroids for these layers).",
            is_demo=False)
        s.flush()

        districts = _district_rows()
        blocks = _block_rows()
        now = datetime.now(timezone.utc)

        existing = {
            (b.level, b.name) for b in s.query(AdministrativeBoundary).all()
        }
        added, skipped = 0, 0

        for r in districts:
            name = _title(r.get("dtname"))
            code = str(r.get("dtcode11") or "").strip()
            parent = str(r.get("stcode11") or "").strip()
            if not name or not code or (("district", name) in existing):
                skipped += 1
                continue
            if not args.dry_run:
                s.add(AdministrativeBoundary(
                    level="district", name=name, code=code, parent_code=parent,
                    metadata_json={
                        "stname": r.get("stname"), "stcode11": r.get("stcode11"),
                        "dtcode11": r.get("dtcode11"), "dist_lgd": r.get("dist_lgd"),
                        "state_lgd": r.get("state_lgd"), "year_stat": r.get("year_stat"),
                    },
                    source_name=SOURCE_NAME, source_url=SOURCE_URL,
                    dataset_name=DATASET_NAME, source_type="government",
                    retrieved_at=now, geographic_level="district",
                    confidence="high", is_estimate=False, is_demo=False,
                    methodology="Name/code from Bharat Atlas lgd_districts layer "
                                "(Local Government Directory, CC0-1.0); no centroid "
                                "exposed by the API.",
                ))
            existing.add(("district", name))
            added += 1

        for r in blocks:
            name = _title(r.get("block_name"))
            code = str(r.get("code2011") or "").strip()
            parent = str(r.get("dtcode11") or "").strip()  # district code
            if not name or not code or (("block", name) in existing):
                skipped += 1
                continue
            if not args.dry_run:
                s.add(AdministrativeBoundary(
                    level="block", name=name, code=code, parent_code=parent,
                    metadata_json={
                        "stcode11": r.get("stcode11"), "dtcode11": r.get("dtcode11"),
                        "blkcode11": r.get("blkcode11"), "block_lgd": r.get("block_lgd"),
                        "dist_lgd": r.get("dist_lgd"), "b_pan_code": r.get("b_pan_code"),
                        "state_lgd": r.get("state_lgd"),
                    },
                    source_name=SOURCE_NAME, source_url=SOURCE_URL,
                    dataset_name=DATASET_NAME, source_type="government",
                    retrieved_at=now, geographic_level="block",
                    confidence="high", is_estimate=False, is_demo=False,
                    methodology="Name/code from Bharat Atlas lgd_blocks layer (Local "
                                "Government Directory, CC0-1.0); no centroid exposed by "
                                "the API.",
                ))
            existing.add(("block", name))
            added += 1

        if args.dry_run:
            print(f"[dry-run] would store {added} LGD boundaries "
                  f"({len(districts)} district, {len(blocks)} blocks); {skipped} skipped")
            snapshot.status = "dry_run"
            snapshot.records_ingested = added
            snapshot.finished_at = datetime.now(timezone.utc)
            s.add(snapshot)
            return 0

        snapshot.records_ingested = added
        snapshot.status = "completed" if added else "no_rows"
        snapshot.finished_at = datetime.now(timezone.utc)
        s.add(snapshot)
        log_event("ingest", job="erode_bharatlas_boundaries",
                  boundaries_added=added, boundaries_skipped=skipped,
                  districts_fetched=len(districts), blocks_fetched=len(blocks),
                  status="completed")
        log.info("LGD boundaries (Erode): %d added, %d skipped "
                 "(%d districts, %d blocks)", added, skipped,
                 len(districts), len(blocks))
    return 0


if __name__ == "__main__":
    sys.exit(main())
