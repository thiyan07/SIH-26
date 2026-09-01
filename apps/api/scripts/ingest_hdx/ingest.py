"""HDX India POI ingestion.

Downloads the Humanitarian OpenStreetMap Team (HOT) "Point of Interest"
export for India (a bulk OSM extract), filters to a target district, maps
records onto the GramBiz Business / InfrastructurePoint models, and records a
DataSnapshot.

Unlike ingest_osm (live Overpass per-request), this reads one pre-extracted,
worldwide/India-wide GeoJSON snapshot so a single run seeds a whole district.
The download is optional — you can pass an already-downloaded file.

Dataset: https://data.humdata.org/dataset/hotosm_ind_points_of_interest
License: ODbL (Open Database License). Derived data must retain attribution —
        "© OpenStreetMap contributors". See README in the export zip.

Usage:
  python -m scripts.ingest_hdx.ingest --district "Erode"
  python -m scripts.ingest_hdx.ingest --file /tmp/poi.geojson --district "Erode"
  python -m scripts.ingest_hdx.ingest --state "Tamil Nadu" --district "Erode" --dry-run
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import tempfile
import zipfile
from datetime import datetime, timezone
from typing import Optional

import httpx

from app.config import settings
from app.db.models import Business, DataSnapshot, InfrastructurePoint
from app.db.session import session_scope
from app.engines.profit import CATEGORY_OSM_TAGS

log = logging.getLogger("ingest_hdx")

HDX_ATTR = "OpenStreetMap contributors"
HDX_LICENSE = "ODbL"
HDX_DATASET_URL = "https://data.humdata.org/dataset/hotosm_ind_points_of_interest"
# S3-hosted GeoJSON zip (See "points_of_interest_osm_geojson.zip" resource).
HDX_RAW_URL = (
    "https://production-raw-data-api.s3.amazonaws.com/ISO3/IND/"
    "points_of_interest/hotosm_ind_points_of_interest_osm_geojson.zip"
)

# Adm-boundary property names in the HOT export's feature properties.
_DISTRICT_KEY = "adm2_name"   # e.g. "Erode"
_STATE_KEY = "adm1_name"      # e.g. "Tamil Nadu" (occasionally "Tamil Nādu")


# Map HDX amenity/shop/tourism values onto GramBiz competition categories
# (matches app.engines.profit.CATEGORY_OSM_TAGS).
def _category_for_tags(tags: dict) -> Optional[str]:
    for code, tag_sets in CATEGORY_OSM_TAGS.items():
        for ts in tag_sets:
            if all(tags.get(k) == v for k, v in ts.items() if v is not None):
                if any(k in tags for k in ts):
                    return code
    return None


# Infra mapping for non-business amenity features (schools/hospitals/… that
# the analysis uses for accessibility/competition context). Reuses the same
# keys as the OSM ingester.
_INFRA_TAG_KIND = {
    "amenity=bank": "bank",
    "amenity=atm": "bank",
    "amenity=school": "school",
    "amenity=college": "school",
    "amenity=hospital": "hospital",
    "amenity=clinic": "hospital",
    "amenity=doctors": "hospital",
    "amenity=dentist": "hospital",
    "amenity=pharmacy": "hospital",
    "amenity=bus_station": "transport",
    "amenity=fuel": "transport",
    "amenity=parking": "transport",
    "amenity=marketplace": "market",
    "amenity=post_office": "transport",
    "amenity=community_centre": "civic",
    "amenity=townhall": "civic",
    "amenity=library": "civic",
    "amenity=police": "civic",
    "amenity=fire_station": "civic",
    "amenity=place_of_worship": "civic",
    "amenity=toilets": "civic",
    "man_made=water_tower": "water",
    "man_made=water_well": "water",
    "man_made=storage_tank": "water",
    "man_made=wastewater_plant": "water",
    "man_made=tower": "utility",
    "man_made=works": "manufacturing",
    "man_made=pier": "transport",
    "tourism=hotel": "hospitality",
    "tourism=hostel": "hospitality",
    "tourism=guest_house": "hospitality",
    "tourism=apartment": "hospitality",
}


def _infra_kind(tags: dict) -> Optional[str]:
    for comb, kind in _INFRA_TAG_KIND.items():
        k, v = comb.split("=", 1)
        if tags.get(k) == v:
            return kind
    return None


def _completeness_and_confidence(props: dict) -> tuple[float, str]:
    present = 0.0
    if props.get("name"):
        present += 0.35
    if props.get("addr_full") or props.get("addr_street"):
        present += 0.20
    if props.get("opening_hours"):
        present += 0.15
    completeness = round(min(present, 1.0), 2)
    confidence = "high" if completeness >= 0.70 else ("medium" if completeness >= 0.40 else "low")
    return completeness, confidence


def _provenance() -> dict:
    return {
        "source_name": HDX_ATTR,
        "source_url": HDX_DATASET_URL,
        "dataset_name": "HOT India POI export (OSM)",
        "source_type": "osm",
        "retrieved_at": datetime.now(timezone.utc),
        "geographic_level": "point",
        "is_estimate": True,
        "is_demo": False,
        "methodology": ("Bulk OpenStreetMap extract (HOT 'oex') filtered to the "
                        "target district by admin boundary properties; amenities "
                        "mapped to infrastructure kinds, shops to competition "
                        "categories. OSM coverage varies by locality."),
    }


def download_hdx(tmpdir: str) -> str:
    """Download + extract the India POI GeoJSON, return the file path."""
    log.info("Downloading HDX India POI export…")
    zip_path = os.path.join(tmpdir, "hdx_india_poi.zip")
    with httpx.stream("GET", HDX_RAW_URL, timeout=600, follow_redirects=True) as r:
        r.raise_for_status()
        with open(zip_path, "wb") as f:
            for chunk in r.iter_bytes(chunk_size=1 << 20):
                f.write(chunk)
    log.info("Extracting… (zip %.1f MB)", os.path.getsize(zip_path) / 1e6)
    with zipfile.ZipFile(zip_path) as zf:
        # Locate the main .geojson member.
        member = next(n for n in zf.namelist() if n.endswith(".geojson"))
        target = os.path.join(tmpdir, os.path.basename(member))
        with zf.open(member) as src, open(target, "wb") as dst:
            while True:
                chunk = src.read(1 << 20)
                if not chunk:
                    break
                dst.write(chunk)
    return target


def load_features(path: str, district: str, state: Optional[str]) -> list[dict]:
    """Load a GeoJSON file, filter to the target district, return features."""
    log.info("Reading %s", path)
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    features = data.get("features", [])
    log.info("Total features in file: %s", len(features))
    kept = []
    skipped = 0
    for feat in features:
        props = feat.get("properties") or {}
        d = props.get(_DISTRICT_KEY)
        if d is None:
            d = props.get("adm2") or props.get("district")
        if d is None:
            # No district tag — keep only if we can't filter (safety).
            skipped += 1
            continue
        if str(d).strip().lower() != str(district).strip().lower():
            skipped += 1
            continue
        if state:
            st = props.get(_STATE_KEY) or props.get("adm1")
            if st and str(st).strip().lower() != str(state).strip().lower():
                skipped += 1
                continue
        kept.append(feat)
    log.info("Matched %s features for district '%s' (%s skipped)", len(kept), district, skipped)
    return kept


def _coord(feat: dict) -> tuple[Optional[float], Optional[float]]:
    geom = feat.get("geometry") or {}
    if geom.get("type") != "Point":
        return None, None
    coords = geom.get("coordinates") or []
    if len(coords) < 2:
        return None, None
    return float(coords[1]), float(coords[0])


def ingest(path: str, district: str, state: Optional[str], dry_run: bool = False) -> int:
    features = load_features(path, district, state)
    job_name = f"hdx_{district.replace(' ', '_').lower()}"
    if dry_run:
        # Report the number of distinct, coordinate-valid, named records that
        # would be loaded, without touching the database.
        n = 0
        ids_seen: set[str] = set()
        for feat in features:
            props = feat.get("properties") or {}
            lat, lon = _coord(feat)
            if lat is None or lon is None:
                continue
            if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                continue
            sid = str(props.get("id") or "unknown")
            if sid in ids_seen:
                continue
            ids_seen.add(sid)
            if props.get("name") or props.get("name_en") or props.get("name_latin"):
                n += 1
        log.info("dry-run: %s candidate records for '%s'", n, district)
        from app.log import log_event
        log_event("ingest", job=job_name, records=n, errors=0, dry_run=True,
                  status="completed")
        return n

    snapshot = DataSnapshot(job_name=job_name, status="running",
                            started_at=datetime.now(timezone.utc),
                            records_ingested=0)
    ingested = 0
    errors = 0
    ids_seen = set()
    with session_scope() as s:
        for feat in features:
            try:
                props = feat.get("properties") or {}
                lat, lon = _coord(feat)
                if lat is None or lon is None:
                    errors += 1
                    continue
                if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                    errors += 1
                    continue
                source_id = str(props.get("id") or "unknown")
                if source_id in ids_seen:
                    continue
                ids_seen.add(source_id)
                name = props.get("name") or props.get("name_en") or props.get("name_latin")
                if not name:
                    errors += 1
                    continue
                tags = {k: v for k, v in props.items() if v is not None}
                cat = _category_for_tags(tags) or "other"
                kind = _infra_kind(tags)
                if cat != "other" or kind:
                    completeness, confidence = _completeness_and_confidence(props)
                    prov = _provenance()
                    prov["confidence"] = confidence
                    prov["completeness"] = completeness
                    if kind:
                        existing = s.query(InfrastructurePoint).filter(
                            InfrastructurePoint.source_type == "osm",
                            InfrastructurePoint.source_id == f"hdx-{source_id}",
                        ).first()
                        if existing:
                            continue
                        s.add(InfrastructurePoint(
                            kind=kind, name=name, latitude=lat, longitude=lon,
                            source_id=f"hdx-{source_id}", **prov,
                        ))
                        ingested += 1
                    else:
                        existing = s.query(Business).filter(
                            Business.source == "hdx", Business.source_id == source_id,
                        ).first()
                        if existing:
                            continue
                        address = props.get("addr_full") or props.get("addr_street")
                        s.add(Business(
                            name=name, category_code=cat, latitude=lat, longitude=lon,
                            source="hdx", source_id=source_id,
                            address=address or None, tags=tags, **prov,
                        ))
                        ingested += 1
            except Exception as e:  # noqa: BLE001
                errors += 1
                log.warning("error ingesting HDX feature: %s", e)
        snapshot.records_ingested = ingested
        snapshot.errors = errors
        snapshot.status = "completed"
        snapshot.finished_at = datetime.now(timezone.utc)
        s.add(snapshot)
    from app.log import log_event

    log_event("ingest", job=snapshot.job_name, records=ingested, errors=errors,
              dry_run=dry_run, status="completed")
    log.info("ingested=%s errors=%s", ingested, errors)
    return ingested


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default=None,
                    help="Path to a .geojson (or .geojson.zip) HOT India POI file. "
                         "If omitted, downloads the latest from HDX.")
    ap.add_argument("--district", default="Erode", help="adm2 name to filter to (default: Erode)")
    ap.add_argument("--state", default=None, help="adm1 name filter (optional). Leave unset to filter "
                                                  "only by district.")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO)
    with tempfile.TemporaryDirectory(prefix="hdx_ingest_") as tmp:
        src = args.file
        if src and src.endswith(".zip"):
            with zipfile.ZipFile(src) as zf:
                member = next(n for n in zf.namelist() if n.endswith(".geojson"))
                src = os.path.join(tmp, os.path.basename(member))
                with zf.open(member) as s_in, open(src, "wb") as d_out:
                    d_out.write(s_in.read())
        elif not src:
            src = download_hdx(tmp)
        ingest(src, args.district, args.state, args.dry_run)
