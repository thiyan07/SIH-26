"""India Meteorological Department (IMD) rainfall ingest.

Phase 6: IMD is the authoritative national source for rainfall/temperature,
but it has NO keyless public API. IMD gridded products and daily rainfall are
published through data.gov.in Open API resources that require a free
data.gov.in API key (the same ``DATA_GOV_API_KEY`` infrastructure already used
by the official market-price ingest), or via IMD's own restricted endpoints.

This runner implements the connection + provenance + storage half so that the
moment a resource id is confirmed against a live key it can run unchanged.
Normalization (field-tolerant, month/period aware) is shared and already
fixture-tested via ``DATAGOV_DEFS["imd_rainfall"]``.

Rules
-----
- missing/invalid key OR unconfirmed resource => FAIL FAST, exit 2, nothing
  written. Rainfall values are NEVER fabricated or approximated from other
  weather sources and labelled "IMD".
- ``--resource`` or env ``IMD_RAINFALL_RESOURCE`` selects the data.gov.in
  resource; there is intentionally no hardcoded default id (an unverified id
  would silently return empty records).

Usage:
  DATA_GOV_API_KEY=... IMD_RAINFALL_RESOURCE=<confirmed-id> \\
      python -m scripts.ingest_government.ingest_imd_rainfall
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

log = logging.getLogger("ingest_imd_rainfall")

API_BASE = "https://api.data.gov.in/resource/{resource}"
UA = "GramBizAI/1.0 (IMD rainfall via data.gov.in)"
SOURCE_KEY = "imd_rainfall"
SOURCE_NAME = "IMD rainfall (gridded/district)"
DATASET_NAME = "District rainfall (IMD)"


def _fetch(api_key: str, resource: str, state: str, district: str | None) -> dict:
    filters = {"filters[state]": state}
    if district:
        filters["filters[district]"] = district
    query = urllib.parse.urlencode({
        "api-key": api_key,
        "format": "json",
        "limit": 1000,
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
                    help="data.gov.in resource id that serves IMD rainfall "
                         "(or env IMD_RAINFALL_RESOURCE); must be confirmed against your key")
    ap.add_argument("--state", default="Tamil Nadu")
    ap.add_argument("--district", default="Erode")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    api_key = (settings.data_gov_api_key or "").strip()
    resource = args.resource or getattr(settings, "imd_rainfall_resource", "") or ""
    snapshot = DataSnapshot(job_name="imd_rainfall_erode", status="running",
                            records_ingested=0, started_at=datetime.now(timezone.utc))
    session = session_scope()
    conn = session.__enter__()
    try:
        register_data_source(
            conn, SOURCE_KEY, SOURCE_NAME, "weather", "weather_statistics",
            "IMD district rainfall via data.gov.in; requires a key and a confirmed resource id.",
            is_demo=False)
        conn.flush()
        if not api_key or not resource:
            ds = conn.query(DataSource).filter(DataSource.key == SOURCE_KEY).first()
            ds.freshness_note = (
                "Unavailable: IMD needs DATA_GOV_API_KEY plus a confirmed IMD "
                "rainfall resource id (IMD_RAINFALL_RESOURCE). No values labelled "
                "'IMD' are ever approximated.")
            snapshot.status = "failed"
            snapshot.finished_at = datetime.now(timezone.utc)
            conn.add(snapshot)
            log.error("IMD requires DATA_GOV_API_KEY and IMD_RAINFALL_RESOURCE; "
                      "nothing written (rainfall is never fabricated).")
            return 2

        defn = DATAGOV_DEFS["imd_rainfall"]
        batch = _fetch(api_key, resource, args.state, args.district)
        raw = batch.get("records") or []
        payload = json.dumps({"records": raw}).encode("utf-8")
        rows = normalize_datagov(payload, defn, fmt="json")
        log.info("fetched=%d normalized=%d", len(raw), len(rows))
        if args.dry_run:
            print(f"[dry-run] would store {len(rows)} IMD rainfall rows")
            snapshot.status = "dry_run"
            snapshot.finished_at = datetime.now(timezone.utc)
            conn.add(snapshot)
            return 0
        stored = store_datagov(conn, defn, rows,
                               url=API_BASE.format(resource=resource))
        snapshot.records_ingested = stored
        snapshot.status = "completed"
        snapshot.finished_at = datetime.now(timezone.utc)
        conn.add(snapshot)
        log_event("ingest", job="imd_rainfall_erode",
                  raw=len(raw), stored=stored, status="completed")
        print(f"stored {stored} IMD rainfall rows")
        return 0
    except Exception:
        snapshot.status = "failed"
        snapshot.finished_at = datetime.now(timezone.utc)
        conn.add(snapshot)
        raise
    finally:
        session.__exit__(None, None, None)


if __name__ == "__main__":
    sys.exit(main())
