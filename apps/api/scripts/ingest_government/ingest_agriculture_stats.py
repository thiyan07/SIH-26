"""Ingest real, current agriculture statistics for Erode district.

Single source, keyless and official - the Government of Tamil Nadu Digital
Crop Survey (DCS) at tnagrisnet.tn.gov.in. The DCS publishes taluk-wise
"sown area" tables for Erode by season; the seasons currently published are
Summer 2025, Rabi 2024 and Kharif 2025 (the report pages are server-rendered
HTML tables, Taluk x crop, values in hectares).

Why only DCS? The Tamil Nadu Season & Crop Report 2024-25 district tables
(production in tonnes, yield in kg/ha) are reachable as official PDFs on
tn.gov.in/crop but their multi-row headers are rendered as rotated/reversed
letter artifacts that cannot be mapped to data columns automatically. A
prototype autoparser was written and discarded (2026-08 audit) because the
labels it produced were not trustworthy enough to store. Keeping only area
data whose labels we can verify column-for-column.

Provenance is real and attributed: is_demo=False, government source URL,
confidence medium (agri survey returns, not ground truth), nothing fabricated.

Usage:
  python -m scripts.ingest_government.ingest_agriculture_stats
"""
from __future__ import annotations

import logging
import re
import sys
import time
import urllib.request
from datetime import datetime, timezone

from app.db.models import AgricultureStatistic, DataSnapshot, Location
from app.db.session import session_scope
from app.log import log_event
from scripts.ingest_government.ingest import register_data_source

log = logging.getLogger("ingest_agriculture_stats")

UA = "GramBizAI/1.0 (Erode agriculture statistics ingest; keyless public govt site)"
DCS_BASE = "https://www.tnagrisnet.tn.gov.in/ARS/dcs/reportTalukWise"
DCS_SEASONS = {1: "Summer 2025", 2: "Rabi 2024", 3: "Kharif 2025"}


def _first_number(cell: str | None) -> float | None:
    if not cell:
        return None
    first = re.split(r"[\n/]", cell.strip())[0].replace(",", "").strip()
    try:
        return float(first) if first and first != "-" else None
    except ValueError:
        return None


def fetch_dcs(sid: int) -> list[list[str]]:
    url = f"{DCS_BASE}/{sid}/Erode/Agriculture"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310
        html = resp.read().decode("utf-8", errors="ignore")
    m = re.search(r"<table.*?</table>", html, re.S)
    if not m:
        raise RuntimeError(f"DCS page for season {sid}: no <table>")
    rows: list[list[str]] = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", m.group(0), re.S):
        cells = [re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", c)).strip()
                 for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S)]
        rows.append(cells)
    return rows


def upsert_area(session, snapshot, *, level, location_id, crop, season,
                area, source, url, dataset, ref_year, taluk):
    existing = session.query(AgricultureStatistic).filter(
        AgricultureStatistic.level == level,
        AgricultureStatistic.crop == crop,
        AgricultureStatistic.season == season,
        AgricultureStatistic.source_name == source,
    ).first()
    if existing:
        existing.area = area
        existing.location_id = location_id
        existing.metadata_json = {"taluk": taluk, "indicator": "sown_area"}
        return 0
    session.add(AgricultureStatistic(
        location_id=location_id, level=level, crop=crop, season=season,
        area=area, production=None, yield_value=None,
        metadata_json={"taluk": taluk, "indicator": "sown_area"},
        source_name=source, source_url=url, dataset_name=dataset,
        source_type="government", reference_year=ref_year,
        retrieved_at=datetime.now(timezone.utc),
        geographic_level="district" if level == "district" else "taluk",
        confidence="medium", completeness=0.7,
        methodology="Government Digital Crop Survey figure (sown area in "
                    "hectares), taken verbatim from the published table.",
        is_estimate=False, is_demo=False,
    ))
    snapshot.records_ingested += 1
    return 1


def ingest_dcs(session, snapshot) -> int:
    added = 0
    for sid, season in DCS_SEASONS.items():
        try:
            rows = fetch_dcs(sid)
        except Exception as exc:  # noqa: BLE001
            log.warning("DCS season %s failed: %s", season, exc)
            continue
        if not rows:
            log.warning("DCS season %s: empty", season)
            continue
        crops = [c for c in rows[0][1:] if c]
        district_url = f"{DCS_BASE}/{sid}/Erode/Agriculture"
        dataset = (f"TN Digital Crop Survey taluk-wise sown area, Erode "
                   f"({season}).")
        for row in rows[1:]:
            if not row:
                continue
            taluk = row[0] or ""
            is_total = taluk.strip().lower() in ("total", "district total")
            taluk_key = taluk.strip().title()
            loc_id = None
            if not is_total:
                loc = session.query(Location).filter(
                    Location.district == "Erode",
                    Location.village == taluk_key,
                ).first()
                loc_id = loc.id if loc else None
            for j, crop in enumerate(crops):
                if j + 1 >= len(row):
                    break
                area = _first_number(row[j + 1])
                if area is None or area <= 0:
                    continue
                added += upsert_area(
                    session, snapshot,
                    level="district" if is_total else "taluk",
                    location_id=loc_id,
                    crop=re.sub(r"\s+", " ", crop).strip().title(),
                    season=season, area=area,
                    source="TN Digital Crop Survey (DCS)",
                    url=district_url, dataset=dataset,
                    ref_year=int(season.split()[1]),
                    taluk=taluk_key if not is_total else None,
                )
        log.info("DCS %s: %d crop-area cells", season, added)
        time.sleep(0.5)
    return added


def main(argv=None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    snapshot = DataSnapshot(job_name="agriculture_stats_erode", status="running",
                            records_ingested=0, started_at=datetime.now(timezone.utc))
    with session_scope() as s:
        register_data_source(
            s, "agriculture_stats_live",
            "Agriculture statistics (TN Digital Crop Survey)",
            "agriculture", "agriculture_statistics",
            "Keyless official: current-season (Summer 2025 / Rabi 2024 / "
            "Kharif 2025) taluk-wise sown area for Erode district.")
        ingest_dcs(s, snapshot)
        snapshot.status = "completed"
        snapshot.finished_at = datetime.now(timezone.utc)
        s.add(snapshot)
    log_event("ingest", job="agriculture_stats_erode",
              records=snapshot.records_ingested, status="completed")
    log.info("agriculture rows written: %d", snapshot.records_ingested)
    return 0


if __name__ == "__main__":
    sys.exit(main())
