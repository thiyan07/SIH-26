"""Government data ingestion (data.gov.in discovery + Census baseline).

Designed to be repeatable: source -> validate -> normalize -> dedupe -> add
provenance -> store -> log errors -> timestamp.

Census 2011 data is always stored with census_year=2011 and flagged historical.

Usage:
  python -m scripts.ingest_government.ingest --dataset census
  python -m scripts.ingest_government.ingest --dataset datagov --url <csdl-url>
"""
from __future__ import annotations

import argparse
import logging
from datetime import datetime, timezone
from typing import Optional

import httpx

from app.db.models import DataSnapshot, DataSource, Location, PopulationStatistic
from app.db.session import session_scope
from scripts.ingest_government.normalize import (
    DATAGOV_DEFS,
    detect_format,
    normalize_datagov,
    store_datagov,
)

log = logging.getLogger("ingest_government")


def register_data_source(s, key: str, name: str, cat: str, dataset: str, note: str, is_demo=False):
    ds = s.query(DataSource).filter(DataSource.key == key).first()
    if ds is None:
        s.add(DataSource(key=key, display_name=name, category=cat, dataset_name=dataset,
                         freshness_note=note, is_demo=is_demo))


def ingest_census_demo_rows(rows: list[dict]):
    """Insert validated population rows (e.g. from a CSV of Census 2011 baseline).

    Each row: {state, district, block, village, population, households,
               males, females, census_year=2011}
    """
    snapshot = DataSnapshot(job_name="census_baseline", status="running",
                            started_at=datetime.now(timezone.utc))
    with session_scope() as s:
        register_data_source(s, "population_census", "Population (Census 2011)",
                             "demographics", "population_statistics",
                             "Census 2011 baseline - historical, not current population")
        n = 0
        for r in rows:
            # resolve Location by administrative identifiers
            loc = s.query(Location).filter(
                Location.state == r.get("state"),
                Location.district == r.get("district"),
                Location.block == r.get("block"),
                Location.village == r.get("village"),
            ).first()
            if loc is None:
                log.warning("no matching Location for %s/%s/%s/%s",
                            r.get("state"), r.get("district"), r.get("block"), r.get("village"))
                continue
            existing = s.query(PopulationStatistic).filter(
                PopulationStatistic.location_id == loc.id,
                PopulationStatistic.census_year == r.get("census_year", 2011),
            ).first()
            if existing:
                continue
            rec = PopulationStatistic(
                location_id=loc.id, level="village",
                census_year=r.get("census_year", 2011),
                population=r.get("population"), households=r.get("households"),
                males=r.get("males"), females=r.get("females"),
                source_name="Census India", source_type="government",
                dataset_name="Primary Census Abstract",
                reference_year=r.get("census_year", 2011),
                is_estimate=False, is_demo=False,
                confidence="high",
            )
            s.add(rec)
            n += 1
        snapshot.records_ingested = n
        snapshot.status = "completed"
        snapshot.finished_at = datetime.now(timezone.utc)
        s.add(snapshot)
    from app.log import log_event

    log_event("ingest", job="census_baseline", records=n, errors=0, status="completed")
    log.info("census ingested=%s", n)


def fetch_datagov_resource(url: str) -> Optional[bytes]:
    resp = httpx.get(url, timeout=120)
    resp.raise_for_status()
    return resp.content


def ingest_datagov_resource(url: Optional[str], file_path: Optional[str],
                            def_key: str, fmt: Optional[str] = None) -> int:
    defn = DATAGOV_DEFS[def_key]
    if file_path:
        with open(file_path, "rb") as fh:
            content = fh.read()
    else:
        content = fetch_datagov_resource(url)
    rows = normalize_datagov(content, defn, fmt=fmt or detect_format(content))
    if not rows:
        log.warning("no rows normalized for %s (format=%s)", def_key, fmt or detect_format(content))
        return 0
    snapshot = DataSnapshot(job_name=f"datagov_{def_key}", status="running",
                            started_at=datetime.now(timezone.utc))
    with session_scope() as s:
        n = store_datagov(s, defn, rows, url=url)
        snapshot.records_ingested = n
        snapshot.status = "completed"
        snapshot.finished_at = datetime.now(timezone.utc)
        s.add(snapshot)
    from app.log import log_event

    log_event("ingest", job=f"datagov_{def_key}", records=n,
              normalized=len(rows), status="completed")
    log.info("datagov %s: normalized=%d stored=%d", def_key, len(rows), n)
    return n


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", choices=["census", "datagov"], required=True)
    ap.add_argument("--url")
    ap.add_argument("--csv")
    ap.add_argument("--file")
    ap.add_argument("--def", dest="def_key", choices=sorted(DATAGOV_DEFS))
    ap.add_argument("--format", choices=["json", "csv", "xml"])
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO)
    if args.dataset == "census" and args.csv:
        import csv
        with open(args.csv, newline="") as f:
            rows = list(csv.DictReader(f))
        ingest_census_demo_rows(rows)
    elif args.dataset == "datagov" and (args.url or args.file) and args.def_key:
        ingest_datagov_resource(args.url, args.file, args.def_key, fmt=args.format)
    else:
        ap.error("--dataset datagov requires --def plus --url (or --file)")
