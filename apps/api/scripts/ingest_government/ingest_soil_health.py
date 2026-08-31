"""Official data.gov.in Soil Health Card ingest (MOAFW Soil Nutrient Analysis).

Source of record: the Government of India open-data API (api.data.gov.in),
which mirrors the Ministry of Agriculture & Farmers Welfare Soil Health Card
programme's "Soil Nutrient Analysis" dataset (state/district/block/village +
nutrient type/name/level + value). Stored into ``soil_health_statistics`` so
nutrient levels never mix with crop area/production/yield facts.

Requirements
------------
- ``DATA_GOV_API_KEY`` (free: https://data.gov.in/help/how-use-data-govin-apis)
- ``SOIL_HEALTH_RESOURCE``: the resource id of the Soil Nutrient Analysis
  dataset, confirmed against your key. This id is deliberately NOT hardcoded
  (resource ids churn and vary by account/key), so an operator must set it;
  the same fail-fast rule applies as for IMD rainfall.

Usage:
  DATA_GOV_API_KEY=... SOIL_HEALTH_RESOURCE=<id> \\
      python -m scripts.ingest_government.ingest_soil_health
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone

from app.config import settings
from app.db.models import DataSnapshot, DataSource
from app.db.session import session_scope
from app.log import log_event
from scripts.ingest_government.ingest import register_data_source
from scripts.ingest_government.normalize import (
    DATAGOV_DEFS,
    normalize_datagov,
    store_datagov,
)

log = logging.getLogger("ingest_soil_health")

API_BASE = "https://api.data.gov.in/resource/{resource}"
UA = "GramBizAI/1.0 (Soil Health Card via data.gov.in)"
SOURCE_KEY = "soil_health_datagov"
SOURCE_NAME = "Soil Health Card (MOAFW, via data.gov.in)"
DATASET_NAME = "Soil Health Card - Soil Nutrient Analysis"


def _fetch(api_key: str, resource: str, state: str, district: str | None,
           limit: int = 1000, offset: int = 0) -> dict:
    filters = {"filters[state]": state}
    if district:
        filters["filters[district]"] = district
    query = urllib.parse.urlencode({
        "api-key": api_key,
        "format": "json",
        "limit": limit,
        **({"offset": offset} if offset > 0 else {}),
        **filters,
    })
    req = urllib.request.Request(
        f"{API_BASE.format(resource=resource)}?{query}",
        headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310 - govt open API
        return json.loads(resp.read().decode("utf-8", "replace"))


def main(argv=None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    ap = argparse.ArgumentParser()
    ap.add_argument("--resource", default=None,
                    help="data.gov.in resource id serving Soil Nutrient Analysis "
                         "(or env SOIL_HEALTH_RESOURCE); must be confirmed against your key")
    ap.add_argument("--state", default="Tamil Nadu")
    ap.add_argument("--district", default="Erode")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    api_key = (settings.data_gov_api_key or "").strip()
    resource = args.resource or getattr(settings, "soil_health_resource", "") or ""
    snapshot = DataSnapshot(job_name="soil_health_erode", status="running",
                            records_ingested=0, started_at=datetime.now(timezone.utc))
    session = session_scope()
    conn = session.__enter__()
    try:
        register_data_source(
            conn, SOURCE_KEY, SOURCE_NAME, "agriculture", "soil_health_statistics",
            "Soil Health Card nutrient analysis via data.gov.in; requires a key "
            "and a confirmed resource id.", is_demo=False)
        conn.flush()
        if not api_key or not resource:
            ds = conn.query(DataSource).filter(DataSource.key == SOURCE_KEY).first()
            ds.freshness_note = (
                "Unavailable: needs DATA_GOV_API_KEY plus a confirmed Soil Nutrient "
                "Analysis resource id (SOIL_HEALTH_RESOURCE). No 'SHC' values are ever approximated.")
            snapshot.status = "failed"
            snapshot.finished_at = datetime.now(timezone.utc)
            conn.add(snapshot)
            log.error("Soil Health requires DATA_GOV_API_KEY and SOIL_HEALTH_RESOURCE; "
                      "nothing written (soil data is never fabricated).")
            return 2

        defn = DATAGOV_DEFS["soil_health"]
        batch = _fetch(api_key, resource, args.state, args.district)
        raw = batch.get("records") or []
        payload = json.dumps({"records": raw}).encode("utf-8")
        rows = normalize_datagov(payload, defn, fmt="json")
        log.info("fetched=%d normalized=%d", len(raw), len(rows))
        if args.dry_run:
            print(f"[dry-run] would store {len(rows)} Soil Health rows (state={args.state}, district={args.district})")
            snapshot.status = "dry_run"
            snapshot.finished_at = datetime.now(timezone.utc)
            conn.add(snapshot)
            return 0
        n = store_datagov(conn, defn, rows, url=batch.get("message", ""))
        snapshot.records_ingested = n
        snapshot.status = "completed" if n else "no_rows"
        snapshot.finished_at = datetime.now(timezone.utc)
        conn.add(snapshot)
        log_event("ingest", job="soil_health_erode", records=len(raw), stored=n,
                  status=snapshot.status, resource=resource)
        print(f"[ok] soil_health: fetched={len(raw)} stored={n}")
        return 0
    finally:
        session.__exit__(None, None, None)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
