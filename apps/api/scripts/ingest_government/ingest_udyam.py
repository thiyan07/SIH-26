"""Official data.gov.in UDYAM MSME registration unit ingest (Ministry of MSME).

Source of record: the Government of India open-data API (api.data.gov.in),
which mirrors the "List of MSME Registered Units under UDYAM" resource
(Ministry of Micro, Small & Medium Enterprises). Units ship with **pincode**
granularity - there is no exact lat/lng and no turnover/investment/MSME-class
in the unit-level list. Per the geo-resolution policy:

  * a unit is located at its ``pincode`` centroid when a pincode directory is
    available (see ``PincodeResolver``), else the pincode is stored with null
    coordinates;
  * ``geographic_level`` is always ``pincode`` and ``confidence`` is reduced,
    because pincode centroids approximate, not locate, a shop;
  * pincode-level rows feed district/pincode-scoped ``nearby_msmes`` /
    ``relevant_msmes`` aggregation and are NEVER counted as point-radius
    competitors (OSM covers that role in GramBiz).

No values are fabricated: null turnover/investment stay null, and the whole
job fails fast (exit 2) if ``DATA_GOV_API_KEY`` or ``UDYAM_RESOURCE`` is
absent.

Usage:
  DATA_GOV_API_KEY=... UDYAM_RESOURCE=<id> \\
      python -m scripts.ingest_government.ingest_udyam --state "Tamil Nadu"
"""
from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone

from app.config import settings
from app.db.models import DataSnapshot, DataSource, UdyamUnit
from app.db.session import session_scope
from app.log import log_event
from scripts.ingest_government.ingest import register_data_source

log = logging.getLogger("ingest_udyam")

API_BASE = "https://api.data.gov.in/resource/{resource}"
UA = "GramBizAI/1.0 (UDYAM MSME units via data.gov.in)"
SOURCE_KEY = "udyam"
SOURCE_NAME = "UDYAM MSME registration (Ministry of MSME, via data.gov.in)"
DATASET_NAME = "List of MSME Registered Units under UDYAM"

# Column aliases observed on the OGD resource (hardened against source churn:
# the public resource anonymises unit records, so the canonical export ships
# uppercase keys: EnterpriseName, CommunicationAddress, Pincode, State,
# District, RegistrationDate, Activities (NIC-2008 list JSON), LG_*_Code.
# ``udyam_number`` was present in older exports but is omitted in newer ones;
# a deterministic source_key is derived there).
FIELD_ALIASES = {
    "udyam_number": ["udyam_registration_number", "udyamno", "udyam_number", "udyam_reg_no", "reg_no", "UdyamRegistrationNumber"],
    "enterprise_name": ["enterprise_name", "enterprise", "name", "unit_name", "EnterpriseName", "ENTERPRISE_NAME"],
    "category": ["category", "enterprise_type", "type_of_enterprise", "msme_class", "Category", "category_name"],
    "sector": ["sector", "sector_name", "Sector"],
    "nic_code": ["nic_code", "nic", "activity_code", "nic_2008", "nic5", "NIC5DigitId", "NIC5DigitCode"],
    "state": ["state", "state_name", "State", "STATE"],
    "district": ["district", "district_name", "District", "DISTRICT"],
    "pincode": ["pincode", "pin_code", "pin", "Pincode", "PINCode", "PINCode_pin", "PIN_CODE", "Pincode_pin"],
    "address": ["address", "unit_address", "official_address", "CommunicationAddress", "PlantLocation", "communication_address"],
    "registration_date": ["registration_date", "reg_date", "date_of_registration", "udayam_registration_date", "dated", "RegistrationDate", "registration_date_dt"],
}

# NIC-2008 activity codes are embedded in the ``Activities`` JSON list of the
# anonymised export: [{"NIC5DigitId": "96010", "Description": "..."}, ...].
ACTIVITIES_ALIASES = ["Activities", "activities", "Activity", "NIC"]
NIC_CODE_ALIASES = ["NIC5DigitId", "nic5_digit_id", "nic5digitid", "NIC5DigitCode", "code"]
NIC_DESCR_ALIASES = ["Description", "description", "activity_desc", "nic_description"]
PINIFY = lambda v: None if v in (None, "") else str(v).split(".")[0].strip().zfill(6) if str(v).split(".")[0].strip().isdigit() else str(v).strip()


def _extract_nic(rec: dict) -> tuple[str | None, str | None]:
    """Return (nic_code, nic_description) from the Activities/NIC JSON list."""
    act = None
    for k in ACTIVITIES_ALIASES:
        v = rec.get(k)
        if v:
            act = v
            break
    if act is None:
        return None, None
    if isinstance(act, str):
        act = act.strip()
        try:
            parsed = json.loads(act) if act.startswith("[") else json.loads(act)
        except ValueError:
            return act[:20], None
    if not isinstance(parsed, list):
        return None, None
    for item in parsed:
        if not isinstance(item, dict):
            continue
        code = None
        for k in NIC_CODE_ALIASES:
            if item.get(k):
                code = str(item[k]).strip()
                break
        desc = None
        for k in NIC_DESCR_ALIASES:
            if item.get(k):
                desc = str(item[k]).strip()
                break
        if code:
            return code, desc
    return None, None


def _pick(rec: dict, names: list[str]):
    """Return the first non-empty alias value for a field (or None)."""
    for n in names:
        v = rec.get(n)
        if v not in (None, ""):
            return v
    return None


class PincodeResolver:
    """Built-in pincode->centroid table, seeded from an optional CSV.

    CSV columns: ``pincode,latitude,longitude[,district,state]``. When the
    file is absent the resolver returns ``None`` and units store null
    coordinates (still aggregated at district scope by their text fields).
    Only pincodes we have a centroid for are located.
    """

    _lazy: dict[str, tuple[float, float]] | None = None

    @classmethod
    def load(cls, path: str | None):
        cls._lazy = {}
        if not path or not os.path.exists(path):
            return
        with open(path, newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                pin = str(row.get("pincode", "")).strip().zfill(6)
                try:
                    lat = float(row["latitude"])
                    lng = float(row["longitude"])
                except (KeyError, ValueError, TypeError):
                    continue
                if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
                    continue
                cls._lazy[pin] = (lat, lng)

    @classmethod
    def resolve(cls, pincode: str | None) -> tuple[float, float] | None:
        if not pincode:
            return None
        if cls._lazy is None:
            cls.load(settings.udyam_pincode_directory or "")
        return cls._lazy.get(str(pincode).strip().zfill(6))


def _fetch(api_key: str, resource: str, state: str, limit: int = 1000,
           offset: int = 0, district: str | None = None,
           pincodes: list[str] | None = None) -> dict:
    query = urllib.parse.urlencode({
        "api-key": api_key,
        "format": "json",
        "limit": limit,
        **({"offset": offset} if offset > 0 else {}),
        # The public resource capitalises its field names exactly.
        **({"filters[State]": state} if state else {}),
        **({"filters[District]": district} if district else {}),
        **({"filters[Pincode]": PINIFY(pincodes[0])} if pincodes else {}),
    })
    req = urllib.request.Request(
        f"{API_BASE.format(resource=resource)}?{query}",
        headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=90) as resp:  # noqa: S310 - govt open API
        return json.loads(resp.read().decode("utf-8", "replace"))


def _normalized_rows(raw: list[dict]) -> list[dict]:
    rows = []
    for rec in raw:
        if not isinstance(rec, dict):
            continue
        udyam_no = str(_pick(rec, FIELD_ALIASES["udyam_number"]) or "").strip()
        pincode = PINIFY(_pick(rec, FIELD_ALIASES["pincode"]))
        state = _clean(_pick(rec, FIELD_ALIASES["state"]))
        district = _clean(_pick(rec, FIELD_ALIASES["district"]))
        ename = _clean(_pick(rec, FIELD_ALIASES["enterprise_name"]))
        # Skip rows that carry no identifying content at all (junk).
        if not udyam_no and not ename:
            continue
        nic_code, nic_desc = _extract_nic(rec)
        # Natural key may be absent on anonymised exports: build a deterministic
        # source_key from (state, district, pincode, name, date) per the model.
        if not udyam_no:
            reg_dt = _coerce_date(_pick(rec, FIELD_ALIASES["registration_date"]))
            reg_key = reg_dt.isoformat() if reg_dt else ""
            udyam_no = None
            source_key = "|".join(filter(None, [
                str(state or "").upper(), str(district or "").upper(),
                str(pincode or ""), str(ename or "").upper(), reg_key]))
            source_key = source_key or "unknown"
        else:
            source_key = udyam_no
        reg_date = _coerce_date(_pick(rec, FIELD_ALIASES["registration_date"]) or rec.get("registration_date"))
        coords = PincodeResolver.resolve(pincode)
        rows.append({
            "udyam_number": udyam_no,
            "source_key": source_key,
            "enterprise_name": ename,
            "category": _clean(_pick(rec, FIELD_ALIASES["category"])),
            "sector": _clean(_pick(rec, FIELD_ALIASES["sector"])),
            "nic_code": _clean(nic_code) or _clean(_pick(rec, FIELD_ALIASES["nic_code"])),
            "nic_description": nic_desc,
            "state": state,
            "district": district,
            "pincode": pincode,
            "address": _clean(_pick(rec, FIELD_ALIASES["address"])),
            "registration_date": reg_date,
            "latitude": coords[0] if coords else None,
            "longitude": coords[1] if coords else None,
            "located": coords is not None,
        })
    return rows


def _clean(v) -> str | None:
    if v in (None, ""):
        return None
    s = str(v).strip()
    return s or None


def _coerce_date(v):
    if not v:
        return None
    s = str(v).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(s[:10], fmt).date()
        except ValueError:
            continue
    return None


def _store(session, rows: list[dict], url: str) -> int:
    stored = 0
    for r in rows:
        existing = session.query(UdyamUnit).filter(
            UdyamUnit.source_key == r["source_key"]).first()
        if existing:
            if existing.is_demo:
                continue
            existing.enterprise_name = r["enterprise_name"] or existing.enterprise_name
            existing.category = r["category"] or existing.category
            existing.sector = r["sector"] or existing.sector
            existing.nic_code = r["nic_code"] or existing.nic_code
            existing.state = r["state"] or existing.state
            existing.district = r["district"] or existing.district
            existing.pincode = r["pincode"] or existing.pincode
            existing.address = r["address"] or existing.address
            existing.registration_date = r["registration_date"] or existing.registration_date
            existing.latitude = r["latitude"]
            existing.longitude = r["longitude"]
            existing.retrieved_at = datetime.now(timezone.utc)
        else:
            session.add(UdyamUnit(
                udyam_number=r["udyam_number"],
                source_key=r["source_key"],
                enterprise_name=r["enterprise_name"],
                category=r["category"],
                sector=r["sector"],
                nic_code=r["nic_code"],
                state=r["state"],
                district=r["district"],
                pincode=r["pincode"],
                address=r["address"],
                registration_date=r["registration_date"],
                latitude=r["latitude"],
                longitude=r["longitude"],
                source_name=SOURCE_NAME,
                source_url=url or API_BASE,
                dataset_name=DATASET_NAME,
                source_type="government",
                reference_date=r["registration_date"],
                retrieved_at=datetime.now(timezone.utc),
                geographic_level="pincode",
                confidence="medium",
                methodology=("Official UDYAM unit list via data.gov.in; located at "
                             "pincode centroid when a directory is available."),
                is_estimate=False,
                is_demo=False,
                metadata_json={"pincode_located": bool(r["latitude"]),
                               "geo_resolution": "pincode",
                               "deterministic_key": r["source_key"] != r["udyam_number"],
                               "nic_description": r.get("nic_description")},
            ))
        stored += 1
    if stored:
        session.flush()
    return stored


def main(argv=None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    ap = argparse.ArgumentParser()
    ap.add_argument("--resource", default=None,
                    help="data.gov.in resource id for the UDYAM unit list "
                         "(or env UDYAM_RESOURCE); must be confirmed against your key")
    ap.add_argument("--state", default="Tamil Nadu")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    api_key = (settings.data_gov_api_key or "").strip()
    resource = args.resource or getattr(settings, "udyam_resource", "") or ""
    session = session_scope()
    conn = session.__enter__()
    snapshot = DataSnapshot(job_name="udyam_erode", status="running",
                            records_ingested=0, started_at=datetime.now(timezone.utc))
    try:
        register_data_source(
            conn, SOURCE_KEY, SOURCE_NAME, "msme", "udyam_units",
            "UDYAM MSME unit list via data.gov.in; pincode-level geo, "
            "requires a key and a confirmed resource id.", is_demo=False)
        conn.flush()
        if not api_key or not resource:
            ds = conn.query(DataSource).filter(DataSource.key == SOURCE_KEY).first()
            ds.freshness_note = (
                "Unavailable: needs DATA_GOV_API_KEY plus a confirmed UDYAM unit-list "
                "resource id (UDYAM_RESOURCE). No MSME facts are ever approximated.")
            snapshot.status = "failed"
            snapshot.finished_at = datetime.now(timezone.utc)
            conn.add(snapshot)
            log.error("UDYAM requires DATA_GOV_API_KEY and UDYAM_RESOURCE; "
                      "nothing written (MSME data is never fabricated).")
            return 2

        PincodeResolver.load(settings.udyam_pincode_directory or "")
        offset = 0
        all_rows = []
        while True:
            batch = _fetch(api_key, resource, args.state, offset=offset)
            raw = batch.get("records") or []
            if not raw:
                break
            all_rows.extend(_normalized_rows(raw))
            total = batch.get("total", len(raw))
            offset += len(raw)
            if offset >= int(total or 0) or len(raw) < 1000:
                break
        located = sum(1 for r in all_rows if r["located"])
        log.info("fetched=%d normalized=%d located=%d", len(all_rows), len(all_rows), located)
        if args.dry_run:
            print(f"[dry-run] would store {len(all_rows)} UDYAM units (state={args.state}, "
                  f"{located} pincode-located)")
            snapshot.status = "dry_run"
            snapshot.finished_at = datetime.now(timezone.utc)
            conn.add(snapshot)
            return 0
        n = _store(conn, all_rows, batch.get("message", "") if all_rows else "")
        snapshot.records_ingested = n
        snapshot.status = "completed" if n else "no_rows"
        snapshot.finished_at = datetime.now(timezone.utc)
        conn.add(snapshot)
        log_event("ingest", job="udyam_erode", records=len(all_rows), stored=n,
                  located=located, status=snapshot.status, resource=resource)
        print(f"[ok] udyam: fetched={len(all_rows)} stored={n} located={located}")
        return 0
    finally:
        session.__exit__(None, None, None)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
