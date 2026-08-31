"""Ingest an Erode small-scale-industries profile into ``industrial_units``.

Source: the user-downloaded ``small_scale_industries_erd_18_19.csv`` - a
district industrial profile for Erode, Tamil Nadu, listing the number of small
scale industrial units per NIC division for FY 2018-19 (total 6,430 units).

This is district-scoped aggregate data (matching the ``IndustrialUnit`` model's
granularity - it carries no per-unit coordinates). We store a single aggregate
row (state, district, unit_type=small_scale_industry, reference_year=2019)
whose ``count`` is the official total, and preserve the full per-NIC division
breakdown in ``metadata_json`` so no detail from the source is lost.

Real rows are unique per (state, district, unit_type, reference_year) so
official re-runs are idempotent.

Usage:
  python -m scripts.ingest_government.ingest_industrial_erode [--dry-run]
"""
from __future__ import annotations

import argparse
import csv
import logging
import sys
from datetime import datetime, timezone

from app.db.models import DataSnapshot, IndustrialUnit
from app.db.session import session_scope
from app.log import log_event
from scripts.ingest_government.ingest import register_data_source

log = logging.getLogger("ingest_industrial_erode")

SOURCE_KEY = "industrial_erode"
SOURCE_NAME = "Erode district small-scale industry profile (2018-19)"
SOURCE_URL = "data/raw/industrial_erode/small_scale_industries_erode_2018_19.csv"
DATASET_NAME = "Small Scale Industries in Erode District (2018-19)"
STATE = "Tamil Nadu"
DISTRICT = "Erode"
REFERENCE_YEAR = 2019  # FY 2018-19
UNIT_TYPE = "small_scale_industry"

RAW_PATH = SOURCE_URL


def _int_or_none(v):
    if v in (None, ""):
        return None
    s = str(v).strip()
    if s.upper() in ("NA", "N/A", "-"):
        return None
    try:
        return int(float(s))
    except ValueError:
        return None


def _parse(path: str) -> tuple[dict, list[dict]]:
    """Return (aggregate_row, breakdown) where aggregate_row holds the total."""
    breakdown = []
    total = None
    with open(path, newline="", encoding="utf-8-sig") as fh:
        for rec in csv.DictReader(fh):
            label = (rec.get("Detail of Classification") or "").strip()
            clazz = (rec.get("Classification") or "").strip()
            count = _int_or_none(rec.get("Number of Units"))
            if label.upper() == "TOTAL":
                total = count or 0
                continue
            breakdown.append({
                "nic_division": clazz,
                "classification": label,
                "count": count,
            })
    if total is None:
        total = sum(b["count"] for b in breakdown if b["count"] is not None)
    agg = {
        "state": STATE,
        "district": DISTRICT,
        "count": total,
        "breakdown_metadata": breakdown,
    }
    return agg, breakdown


def _store(session, agg: dict) -> int:
    existing = session.query(IndustrialUnit).filter(
        IndustrialUnit.state == agg["state"],
        IndustrialUnit.district == agg["district"],
        IndustrialUnit.unit_type == UNIT_TYPE,
        IndustrialUnit.reference_year == REFERENCE_YEAR,
    ).first()
    if existing:
        if existing.is_demo:
            return 0
        return 0  # identical aggregate already present; idempotent skip
    session.add(IndustrialUnit(
        state=agg["state"],
        district=agg["district"],
        unit_type=UNIT_TYPE,
        count=agg["count"],
        reference_year=REFERENCE_YEAR,
        source_name=SOURCE_NAME,
        source_url=SOURCE_URL,
        dataset_name=DATASET_NAME,
        source_type="government",
        retrieved_at=datetime.now(timezone.utc),
        geographic_level="district",
        confidence="medium",
        completeness=1.0,
        methodology=("User-downloaded Erode district small-scale industry "
                     "profile (FY 2018-19): total small scale industrial units "
                     "by NIC division; district-scoped aggregate, no "
                     "coordinate-level detail in source."),
        is_estimate=False,
        is_demo=False,
        metadata_json={"nic_breakdown": agg["breakdown_metadata"]},
    ))
    session.flush()
    return 1


def main(argv=None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", default=RAW_PATH, help="path to the SSI CSV")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    agg, breakdown = _parse(args.path)
    log.info("parsed %d NIC divisions; total units = %d", len(breakdown), agg["count"])

    session = session_scope()
    conn = session.__enter__()
    snapshot = DataSnapshot(job_name="industrial_erode", status="running",
                            records_ingested=0, started_at=datetime.now(timezone.utc))
    try:
        register_data_source(
            conn, SOURCE_KEY, SOURCE_NAME, "industrial", "industrial_units",
            "Erode district small-scale industry aggregate (FY 2018-19); "
            "district-scoped, no coordinates.", is_demo=False)
        conn.flush()
        if args.dry_run:
            print(f"[dry-run] would store 1 aggregate (total={agg['count']}, "
                  f"{len(breakdown)} NIC divisions)")
            snapshot.status = "dry_run"
            snapshot.finished_at = datetime.now(timezone.utc)
            conn.add(snapshot)
            return 0
        n = _store(conn, agg)
        snapshot.records_ingested = n
        snapshot.status = "completed" if n else "no_rows"
        snapshot.finished_at = datetime.now(timezone.utc)
        conn.add(snapshot)
        log_event("ingest", job="industrial_erode", records=n, stored=n,
                  status=snapshot.status)
        print(f"[ok] industrial_erode: total={agg['count']} stored={n}")
        return 0
    finally:
        session.__exit__(None, None, None)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
