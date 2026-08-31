"""Ingest a downloaded UDYAM MSME unit CSV export into ``udyam_units``.

The user-downloaded CSV ("List of MSME Registered Units under UDYAM" resource
``8b68ae56-84cf-4728-a0a6-1be11028dea7``) is an Erode, Tamil Nadu slice of the
official resource. This export ships **without** ``udyam_number`` (the unique
registration number is not exposed by the resource). Per the chosen design the
unit identity is then the composite (state, district, enterprise_name, pincode,
registration_date), enforced by the ``uq_udyam_real_dedupe`` expression index
so official re-runs cannot duplicate rows.

Column mapping (source CSV -> model):
  * EnterpriseName       -> enterprise_name
  * CommunicationAddress -> address
  * Activities           -> nic_code  (parsed from the embedded JSON NIC5DigitId)
  * State                -> state
  * District             -> district
  * Pincode              -> pincode   (float with trailing ".0" stripped)
  * RegistrationDate     -> registration_date (DD/MM/YYYY)
  * udyam_number, category, sector -> null (not present in this export)

No values are fabricated: the resource carries no turnover/investment/class and
no coordinates, so those stay null.

Usage:
  python -m scripts.ingest_government.ingest_udyam_csv [--dry-run]
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
import sys
from datetime import datetime, timezone

from app.db.models import DataSnapshot, UdyamUnit
from app.db.session import session_scope
from app.log import log_event
from scripts.ingest_government.ingest import register_data_source

log = logging.getLogger("ingest_udyam_csv")

SOURCE_KEY = "udyam"
SOURCE_NAME = "UDYAM MSME registration (Ministry of MSME, via data.gov.in)"
DATASET_NAME = "List of MSME Registered Units under UDYAM"
SOURCE_URL = "https://data.gov.in/resource/8b68ae56-84cf-4728-a0a6-1be11028dea7.csv"

RAW_PATH = "data/raw/udyam_erode/udyam_erode_units.csv"


def _clean(v) -> str | None:
    if v in (None, ""):
        return None
    s = str(v).strip()
    return s or None


def _normalize_pincode(v) -> str | None:
    s = _clean(v)
    if not s:
        return None
    s = s.rstrip("0").rstrip(".") if "." in s else s
    return s


def _coerce_date(v):
    if not v:
        return None
    s = str(v).strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(s[:10], fmt).date()
        except ValueError:
            continue
    return None


def _nic_from_activities(v) -> str | None:
    s = _clean(v)
    if not s:
        return None
    try:
        payload = json.loads(s)
    except (ValueError, TypeError):
        payload = None
    if isinstance(payload, list):
        for item in payload:
            if isinstance(item, dict) and item.get("NIC5DigitId"):
                return str(item["NIC5DigitId"]).strip()
    elif isinstance(payload, dict) and payload.get("NIC5DigitId"):
        return str(payload["NIC5DigitId"]).strip()
    return None


def _rows_from_csv(path: str) -> list[dict]:
    rows = []
    with open(path, newline="", encoding="utf-8-sig") as fh:
        for rec in csv.DictReader(fh):
            row = {
                "udyam_number": None,
                "enterprise_name": _clean(rec.get("EnterpriseName")),
                "category": None,
                "sector": None,
                "nic_code": _nic_from_activities(rec.get("Activities")),
                "state": _clean(rec.get("State")),
                "district": _clean(rec.get("District")),
                "pincode": _normalize_pincode(rec.get("Pincode")),
                "address": _clean(rec.get("CommunicationAddress")),
                "registration_date": _coerce_date(rec.get("RegistrationDate")),
                "latitude": None,
                "longitude": None,
            }
            row["source_key"] = _source_key(row)
            rows.append(row)
    return rows


def _identity(r: dict) -> tuple:
    return (
        r["state"], r["district"], r["enterprise_name"],
        r["pincode"], r["registration_date"],
    )


def _source_key(r: dict) -> str | None:
    if r.get("udyam_number"):
        return str(r["udyam_number"])
    ident = _identity(r)
    raw = "|".join("" if v is None else str(v) for v in ident)
    return "ud-" + hashlib.md5(raw.encode("utf-8")).hexdigest()


def _store(session, rows: list[dict]) -> int:
    existing_keys = {
        sk for (sk,) in session.query(UdyamUnit.source_key)
        .filter(UdyamUnit.is_demo.is_not(True), UdyamUnit.source_key.isnot(None))
        .all()
    }
    seen: set[str] = set()
    stored = 0
    for r in rows:
        key = r["source_key"]
        if key in seen or key in existing_keys:
            continue
        seen.add(key)
        session.add(UdyamUnit(
                udyam_number=r["udyam_number"],
                source_key=r["source_key"],
                enterprise_name=r["enterprise_name"],
                nic_code=r["nic_code"],
                state=r["state"],
                district=r["district"],
                pincode=r["pincode"],
                address=r["address"],
                registration_date=r["registration_date"],
                source_name=SOURCE_NAME,
                source_url=SOURCE_URL,
                dataset_name=DATASET_NAME,
                source_type="government",
                reference_date=r["registration_date"],
                retrieved_at=datetime.now(timezone.utc),
                geographic_level="pincode",
                confidence="medium",
                methodology=("Official UDYAM unit list (data.gov.in CSV export); "
                             "source omits udyam_number, so the composite identity "
                             "(state, district, enterprise_name, pincode, "
                             "registration_date) is used for idempotency."),
                is_estimate=False,
                is_demo=False,
                metadata_json={"geo_resolution": "pincode",
                               "udyam_number_present": False},
            ))
        stored += 1
    if stored:
        session.flush()
    return stored


def main(argv=None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", default=RAW_PATH, help="path to the UDYAM CSV export")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    rows = _rows_from_csv(args.path)
    log.info("parsed %d UDYAM units from %s", len(rows), args.path)

    session = session_scope()
    conn = session.__enter__()
    snapshot = DataSnapshot(job_name="udyam_erode_csv", status="running",
                            records_ingested=0, started_at=datetime.now(timezone.utc))
    try:
        register_data_source(
            conn, SOURCE_KEY, SOURCE_NAME, "msme", "udyam_units",
            "UDYAM MSME unit list (Erode CSV export) via data.gov.in; "
            "pincode-level, composite-key idempotency.", is_demo=False)
        conn.flush()
        if args.dry_run:
            print(f"[dry-run] would store {len(rows)} UDYAM units")
            snapshot.status = "dry_run"
            snapshot.finished_at = datetime.now(timezone.utc)
            conn.add(snapshot)
            return 0
        n = _store(conn, rows)
        snapshot.records_ingested = n
        snapshot.status = "completed" if n else "no_rows"
        snapshot.finished_at = datetime.now(timezone.utc)
        conn.add(snapshot)
        log_event("ingest", job="udyam_erode_csv", records=len(rows), stored=n,
                  status=snapshot.status)
        print(f"[ok] udyam_csv: parsed={len(rows)} stored={n}")
        return 0
    finally:
        session.__exit__(None, None, None)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
