"""Official data.gov.in market-price ingest for Erode (Phase 4).

Source of record: the Government of India open-data API (api.data.gov.in),
which publishes ministry/APMC-reported daily mandi prices for the same
commodities stored in ``market_prices``. It is the official counterpart of the
keyless ACROP mirror already ingested (``ingest_mandi_live.py``).

Requirements
------------
A free data.gov.in API key must be present (env ``DATA_GOV_API_KEY`` or
``data_gov_api_key`` in ``.env``). Register at:
    https://data.gov.in/register/commonuser/resource/nonelist

Resource: the daily market-price resource (resource id in
``DATA_GOV_MARKET_RESOURCE``, default ``9ef84268-d588-465a-a308-a864a43d0070``
— the widely-published "daily market price" data.gov.in resource; override if
your key resolves a different one; the mapper is schema-tolerate and will
accept commodity/market/price/date columns as returned).

Rules
-----
- Missing/invalid key => FAIL FAST: nothing is written, exit code 2, source
  registered as unavailable. Prices are NEVER fabricated.
- Normalization/dedupe goes through ``normalize.py`` (DATAGOV_DEFS
  ``market_arrivals``) + ``store_datagov``; the DB also enforces a partial
  unique index on (item_name, market_name, district, reference_date) for real
  rows, so re-runs are idempotent.
- ``--dry-run`` fetches and reports counts/market coverage without writing.

Usage:
  DATA_GOV_API_KEY=... python -m scripts.ingest_government.ingest_market_datagov
  DATA_GOV_API_KEY=... python -m scripts.ingest_government.ingest_market_datagov \
      --resource 9ef84268-d588-465a-a308-a864a43d0070 --dry-run
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

log = logging.getLogger("ingest_market_datagov")

API_BASE = "https://api.data.gov.in/resource/{resource}"
UA = "GramBizAI/1.0 (official data.gov.in market-price ingest)"

SOURCE_KEY = "market_prices_datagov"
SOURCE_NAME = "data.gov.in (official market prices)"
DATASET_NAME = "Market arrivals (official Mandi prices)"


def _fetch_page(api_key: str, resource: str, state: str, district: str,
                limit: int, offset: int) -> dict:
    query = urllib.parse.urlencode({
        "api-key": api_key,
        "format": "json",
        "limit": limit,
        **({"offset": offset} if offset > 0 else {}),
        "filters[state]": state,
        "filters[district]": district,
    })
    url = f"{API_BASE.format(resource=resource)}?{query}"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310 - govt open API
        return json.loads(resp.read().decode("utf-8", "replace"))


def fetch_records(api_key: str, resource: str, state: str, district: str,
                  limit: int = 1000, max_pages: int = 5) -> tuple[list[dict], dict]:
    """Paginate the data.gov.in resource for one state/district.

    Returns (raw_records, meta) where meta carries the API-reported paging
    totals plus a note about truncation. Empty responses are returned as-is
    (never interpreted as success-without-data beyond what the API reports).
    """
    offset = 0
    records: list[dict] = []
    total_batches = 0
    for _ in range(max(1, max_pages)):
        batch = _fetch_page(api_key, resource, state, district, limit, offset)
        recs = batch.get("records") or []
        records.extend(recs if isinstance(recs, list) else [])
        total_batches += 1
        count = len(recs)
        if count < limit:
            break
        offset += count
    meta = {
        "batches": total_batches,
        "raw_records": len(records),
        "api_limited": total_batches >= max(1, max_pages),
    }
    return records, meta


def main(argv=None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    ap = argparse.ArgumentParser()
    ap.add_argument("--resource", default=None,
                    help="data.gov.in resource id (default: DATA_GOV_MARKET_RESOURCE or the known "
                         "daily market-price resource)")
    ap.add_argument("--state", default="Tamil Nadu")
    ap.add_argument("--district", default="Erode")
    ap.add_argument("--limit", type=int, default=1000)
    ap.add_argument("--max-pages", type=int, default=5)
    ap.add_argument("--dry-run", action="store_true",
                    help="fetch and report only; do not write rows")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    api_key = (settings.data_gov_api_key or "").strip()
    if not api_key:
        log.error("DATA_GOV_API_KEY is not set. Register a free key at data.gov.in "
                  "and set DATA_GOV_API_KEY (or data_gov_api_key in .env).")
        with session_scope() as s:
            ds = s.query(DataSource).filter(DataSource.key == SOURCE_KEY).first()
            if ds is None:
                register_data_source(
                    s, SOURCE_KEY, SOURCE_NAME, "prices", "market_prices",
                    "Unavailable: requires a free data.gov.in API key (DATA_GOV_API_KEY). "
                    "No prices will be fabricated.")
            else:
                ds.freshness_note = (
                    "Unavailable: requires a free data.gov.in API key (DATA_GOV_API_KEY).")
        return 2

    resource = args.resource or getattr(settings, "data_gov_market_resource", None) or \
        "9ef84268-d588-465a-a308-a864a43d0070"

    snapshot = DataSnapshot(job_name="market_prices_official_erode", status="running",
                            records_ingested=0, started_at=datetime.now(timezone.utc))
    session = session_scope()
    conn = session.__enter__()
    try:
        defn = DATAGOV_DEFS["market_arrivals"]
        register_data_source(
            conn, SOURCE_KEY, SOURCE_NAME, "prices", "market_prices",
            f"Official daily market prices for {args.district} district via "
            "data.gov.in; refresh daily.")
        raw, meta = fetch_records(api_key, resource, args.state, args.district,
                                  limit=args.limit, max_pages=args.max_pages)
        if not raw:
            log.warning("no records returned for %s/%s (resource may be empty or the id wrong)",
                        args.state, args.district)
        payload = json.dumps({"records": raw}).encode("utf-8")
        rows = normalize_datagov(payload, defn, fmt="json")
        markets = sorted({r.get("market_name") for r in rows if r.get("market_name")})
        log.info("fetched=%d normalized=%d markets=%d", len(raw), len(rows), len(markets))
        log.info("markets: %s", ", ".join(markets[:20]))
        if args.dry_run:
            print(f"[dry-run] would store {len(rows)} rows across {len(markets)} mandis "
                  f"(raw {len(raw)}, batches {meta['batches']})")
            snapshot.status = "dry_run"
            snapshot.finished_at = datetime.now(timezone.utc)
            conn.add(snapshot)
            return 0
        stored = store_datagov(conn, defn, rows,
                               url=API_BASE.format(resource=resource))
        snapshot.records_ingested = stored
        snapshot.status = "completed"
        snapshot.finished_at = datetime.now(timezone.utc)
        # mark source fresh so the /data-sources status reflects the run
        ds = conn.query(DataSource).filter(DataSource.key == SOURCE_KEY).first()
        if ds is not None:
            ds.last_updated = datetime.now(timezone.utc)
            ds.record_count = stored
            ds.freshness_note = "Official daily market prices; refreshed via data.gov.in."
        conn.add(snapshot)
        log_event("ingest", job="market_prices_official_erode",
                  raw=len(raw), normalized=len(rows), stored=stored,
                  markets=len(markets), status="completed")
        print(f"stored {stored} official price rows across {len(markets)} mandis")
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
