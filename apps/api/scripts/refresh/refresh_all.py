"""Refresh CLI for live-data providers (Phase 18).

Runs the individual, already-built ingest entry points under one cooldown-aware
umbrella, so scheduled refreshes (daily prices, hourly weather) respect each
provider's cadence without hammering the source APIs or rewriting identical
rows. Sources that are historical-by-design (Census 2011) are never re-pulled;
sources that need a key fail fast and are reported, they are never guessed.

Rules
-----
- Every job has a cooldown window (from the last *successful* DataSnapshot).
  Within the window the job is skipped unless ``--force``.
- A provider failure (network, missing key, API error) is reported and exits
  non-zero; other jobs still run.
- ``--only key...`` selects a subset; otherwise all jobs run.

Usage:
  python -m scripts.refresh.refresh_all --only prices_mirror
  python -m scripts.refresh.refresh_all --force                 # bypass cooldowns
  python -m scripts.refresh.refresh_all                         # everything
"""
from __future__ import annotations

import argparse
import datetime as dt
import logging
import sys
from dataclasses import dataclass
from typing import Callable, Optional

from app.db.models import DataSnapshot
from app.db.session import session_scope
from scripts import ingest_osm  # noqa: F401  (import side effect: Overpass runner)
from scripts.ingest_government import (
    ingest_bharatlas_boundaries,
    ingest_bharatlas_geocode,
    ingest_bharatlas_health,
    ingest_mandi_live,
    ingest_market_datagov,
    ingest_openmeteo_weather,
    ingest_soil_health,
    ingest_weather_current,
)

log = logging.getLogger("refresh_all")


def _osm_run(argv: list[str] | None = None):
    from scripts.ingest_osm.ingest import REGION_BBOXES, ingest

    args = argparse.Namespace(bbox=None, region="erode", dry_run=False)
    ingest(args.bbox or REGION_BBOXES.get(args.region), args.region, args.dry_run)
    return 0


@dataclass
class Job:
    key: str
    label: str
    run: Optional[Callable[[], int]] = None
    cooldown: dt.timedelta = dt.timedelta(hours=6)
    snapshot_job_hint: str = ""
    note: str = ""


JOBS: list[Job] = [
    Job(
        key="osm", label="OpenStreetMap businesses & infrastructure",
        run=_osm_run, cooldown=dt.timedelta(days=7), snapshot_job_hint="osm",
    ),
    Job(
        key="prices_mirror", label="Mandi prices (ACROP Agmarknet mirror)",
        run=lambda: ingest_mandi_live.main([]), cooldown=dt.timedelta(hours=12),
        snapshot_job_hint="market_prices_live_erode",
    ),
    Job(
        key="prices_official", label="Official market prices (data.gov.in)",
        run=lambda: ingest_market_datagov.main([]), cooldown=dt.timedelta(hours=12),
        snapshot_job_hint="market_prices_official_erode",
        note="Requires DATA_GOV_API_KEY. Fails fast without a key; never fabricates prices.",
    ),
    Job(
        key="weather_era5", label="Historical weather (Open-Meteo ERA5)",
        run=lambda: ingest_openmeteo_weather.main([]), cooldown=dt.timedelta(days=1),
        snapshot_job_hint="weather_openmeteo_erode",
    ),
    Job(
        key="weather_current", label="Live weather (Open-Meteo current + NASA POWER)",
        run=lambda: ingest_weather_current.main([]), cooldown=dt.timedelta(hours=6),
        snapshot_job_hint="weather_live_erode",
    ),
    Job(
        key="bharat_atlas", label="Location geocode backfill (Bharat Atlas LGD)",
        run=lambda: ingest_bharatlas_geocode.main([]), cooldown=dt.timedelta(days=30),
        snapshot_job_hint="geocode_bharatlas_backfill",
    ),
    Job(
        key="bharatlas_health", label="Health facilities (GODL-India via Bharat Atlas)",
        run=lambda: ingest_bharatlas_health.main([]), cooldown=dt.timedelta(days=7),
        snapshot_job_hint="bharatlas_health_erode",
    ),
    Job(
        key="bharatlas_boundaries", label="Admin boundaries (LGD via Bharat Atlas)",
        run=lambda: ingest_bharatlas_boundaries.main([]), cooldown=dt.timedelta(days=90),
        snapshot_job_hint="bharatlas_boundaries_erode",
    ),
    Job(
        key="census", label="Census 2011 (historical baseline)",
        run=None, cooldown=dt.timedelta(days=3650),
        note="Historical by design - never refreshed from a live source.",
    ),
    Job(
        key="soil_health", label="Soil Health Card (data.gov.in, MOAFW)",
        run=lambda: ingest_soil_health.main([]), cooldown=dt.timedelta(days=30),
        note="Key-gated; skipped cleanly when DATA_GOV_API_KEY or SOIL_HEALTH_RESOURCE is absent.",
    ),
]

JOB_BY_KEY = {j.key: j for j in JOBS}


def _last_success(job: Job) -> Optional[dt.datetime]:
    with session_scope() as s:
        q = s.query(DataSnapshot).filter(DataSnapshot.status == "completed")
        if job.snapshot_job_hint:
            q = q.filter(DataSnapshot.job_name.ilike(f"%{job.snapshot_job_hint}%"))
        row = q.order_by(DataSnapshot.started_at.desc().nulls_last()).limit(1).first()
        return row.started_at if row else None


def main(argv=None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", default=None,
                    help=f"jobs to run (default: all). Known: {sorted(JOB_BY_KEY)}")
    ap.add_argument("--force", action="store_true", help="bypass cooldowns")
    ap.add_argument("--dry-run", action="store_true",
                    help="report what would run without invoking the sources")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    unknown = set(args.only or []) - set(JOB_BY_KEY)
    if unknown:
        ap.error(f"unknown job(s): {sorted(unknown)}")
    selected = [JOB_BY_KEY[k] for k in (args.only or JOB_BY_KEY)]

    now = dt.datetime.now(dt.timezone.utc)
    failures: list[str] = []
    for job in selected:
        if job.run is None:
            print(f"[skip  ] {job.key:<15} {job.label} ({job.note})")
            continue
        last = _last_success(job) if not args.force else None
        remaining = (last + job.cooldown - now) if last else dt.timedelta(0)
        if last and remaining.total_seconds() > 0:
            print(f"[skip  ] {job.key:<15} {job.label} (within cooldown, last {last.isoformat()}; "
                  f"use --force to override)")
            continue
        if args.dry_run:
            print(f"[would ] {job.key:<15} {job.label}")
            continue
        print(f"[run   ] {job.key:<15} {job.label}")
        try:
            rc = job.run()
            if rc not in (0, None):
                raise SystemExit(f"{job.key} returned {rc}")
            print(f"[ok    ] {job.key}")
        except SystemExit as exc:
            failures.append(f"{job.key}: {exc}")
            print(f"[fail  ] {job.key}: {exc}")
        except Exception as exc:  # noqa: BLE001 - report and keep going
            failures.append(f"{job.key}: {exc}")
            print(f"[fail  ] {job.key}: {exc}")
    if failures:
        log.error("refresh finished with failures:\n%s", "\n".join(failures))
        return 1
    print("refresh complete: all jobs ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
