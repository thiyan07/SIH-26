"""OSM ingestion via Overpass API.

Downloads POIs/businesses for a region, normalizes, dedupes, adds provenance,
stores, and records a DataSnapshot. Designed for scheduled ingestion, NOT for
per-dashboard live requests.

Usage:
  python -m scripts.ingest_osm.ingest --bbox "11.45,77.5,11.55,77.6" --region "erode-sathyamangalam"
  python -m scripts.ingest_osm.ingest --region "erode" --district "Erode"   # region alias

© OpenStreetMap contributors - ODbL. Derived data must retain attribution.
"""
from __future__ import annotations

import argparse
import logging
import os
from datetime import datetime, timezone
from typing import Optional

import httpx

from app.config import settings
from app.db.models import Business, DataSnapshot, InfrastructurePoint
from app.db.session import session_scope
from app.engines.profit import CATEGORY_OSM_TAGS

log = logging.getLogger("ingest_osm")

OSM_ATTRIBUTION = "OpenStreetMap contributors"
OSM_LICENSE = "ODbL"

# Region -> bbox presets (plan §5, §28: Erode District, Tamil Nadu).
# Format: (minlat, minlon, maxlat, maxlon). Presets are coarse
# administrative-town approximations for scheduled ingestion; pass --bbox
# to override with an exact rectangle.
REGION_BBOXES = {
    "erode": "11.20,77.30,11.85,77.90",
    "erode-sathyamangalam": "11.47,77.20,11.55,77.31",  # Sathyamangalam town & environs
    "sathyamangalam": "11.47,77.20,11.55,77.31",
    "erode-city": "11.28,77.66,11.40,77.82",
    "bhavani": "11.40,77.63,11.50,77.75",
    "gobichettipalayam": "11.41,77.38,11.50,77.48",
    "perundurai": "11.21,77.53,11.32,77.65",
    "thindal": "11.28,77.64,11.36,77.72",
    "anthiyur": "11.53,77.11,11.62,77.22",
}
DEFAULT_REGION = "erode"

# Signal keys considered when scoring a record's completeness (plan §6).
_COMPLETENESS_WEIGHTS = {
    "name": 0.35,          # the business is identified
    "address": 0.20,       # addr:street / addr:housenumber
    "contact": 0.20,       # phone / contact:phone
    "hours": 0.15,         # opening_hours
    "web": 0.10,           # website / email / contact:*
}


def _completeness_and_confidence(tags: dict) -> tuple[float, str]:
    """Per-record completeness (0..1) + confidence for an OSM element.

    Completeness reflects how much identifying/contact detail a mapper
    recorded, not data validity. Confidence maps that to the low|medium|high
    vocabulary: >=0.70 high, >=0.40 medium, else low.
    """
    present = 0.0
    if tags.get("name"):
        present += _COMPLETENESS_WEIGHTS["name"]
    if tags.get("addr:street") or tags.get("addr:housenumber"):
        present += _COMPLETENESS_WEIGHTS["address"]
    if tags.get("phone") or tags.get("contact:phone"):
        present += _COMPLETENESS_WEIGHTS["contact"]
    if tags.get("opening_hours"):
        present += _COMPLETENESS_WEIGHTS["hours"]
    if tags.get("website") or tags.get("email") or tags.get("contact:website"):
        present += _COMPLETENESS_WEIGHTS["web"]
    completeness = round(min(present, 1.0), 2)
    confidence = "high" if completeness >= 0.70 else "medium" if completeness >= 0.40 else "low"
    return completeness, confidence


# Food-processing is tagged ambiguously (shop/craft/man_made). We only assign
# it when the element's tags mention food-related words, so generic
# craft/man_made elements fall through to manufacturing/handicrafts (plan §4).
_FOOD_PROCESSING_KEYWORDS = (
    "food", "oil", "rice", "mill", "flour", "dairy", "milk", "sweet",
    "bakery", "bread", "butcher", "brewer", "cheese", "honey", "jaggery",
)


def _category_for_tags(tags: dict) -> Optional[str]:
    for code, tag_sets in CATEGORY_OSM_TAGS.items():
        for ts in tag_sets:
            if all(tags.get(k) == v for k, v in ts.items() if v is not None):
                # heuristic: any matching key
                if any(k in tags for k in ts):
                    if code == "food_processing" and not _is_food_processing(tags):
                        continue
                    return code
    return None


def _is_food_processing(tags: dict) -> bool:
    probe = " ".join(str(v).lower() for v in tags.values() if v)
    return any(kw in probe for kw in _FOOD_PROCESSING_KEYWORDS)


def _overpass_query(bbox: str, include_ways: bool = True) -> str:
    # Canonical union form; `out` then emits combined elements from all clauses.
    #
    # Businesses/amenities/offices/healthcare/schools/hospitals/hotels are
    # queried over `nwr` (node, way, relation) because village shops are
    # frequently mapped as polygon `way` outlines, not single nodes —
    # `out center` emits one center lat/lon for those.
    #
    # `highway` and `landuse=farmland` are deliberately kept NODE-only: as
    # `way`s they return tens of thousands of road segments / farm polygons
    # which flood infrastructure_points and drown the business signal. We only
    # want bus-stops/points-of-infrastructure from highway, not every segment.
    b = bbox
    return f"""
    [out:json][timeout:90];
    (
      nwr["shop"]({b});
      nwr["amenity"="restaurant"]({b});
      nwr["amenity"="cafe"]({b});
      nwr["amenity"="fast_food"]({b});
      nwr["amenity"="marketplace"]({b});
      nwr["amenity"="bank"]({b});
      nwr["amenity"="atm"]({b});
      nwr["amenity"="pharmacy"]({b});
      nwr["amenity"="clinic"]({b});
      nwr["amenity"="hospital"]({b});
      nwr["amenity"="school"]({b});
      nwr["amenity"="bus_station"]({b});
      nwr["railway"="station"]({b});
      nwr["craft"]({b});
      nwr["office"]({b});
      nwr["healthcare"]({b});
      nwr["tourism"="hotel"]({b});
      nwr["tourism"="guest_house"]({b});
      node["highway"]({b});
      node["landuse"="farmland"]({b});
    );
    out center tags;
    """


def _prov_geo_level(tags: dict) -> str:
    # Businesses/POIs are point-level regardless of node/way source
    return "point"


_INFRA_TAG_KIND = {
    "amenity=bank": "bank",
    "amenity=school": "school",
    "amenity=hospital": "hospital",
    "amenity=clinic": "hospital",
    "amenity=bus_station": "transport",
    "railway=station": "transport",
    "amenity=marketplace": "market",
    "highway=bus_stop": "transport",
}


def _infra_kind(tags: dict) -> Optional[str]:
    for comb, kind in _INFRA_TAG_KIND.items():
        k, v = comb.split("=", 1)
        if tags.get(k) == v:
            return kind
    # any highway node -> road/travel infrastructure
    if "highway" in tags:
        return "road"
    return None


def _upsert_infrastructure(session, kind: str, name: str, lat: float, lon: float, source_id: str, tags: dict):
    existing = session.query(InfrastructurePoint).filter(
        InfrastructurePoint.source_type == "osm",
        InfrastructurePoint.source_id == source_id,
    ).first()
    if existing:
        return
    completeness, confidence = _completeness_and_confidence(tags)
    session.add(InfrastructurePoint(
        kind=kind, name=name, latitude=lat, longitude=lon, source_id=source_id,
        source_name=OSM_ATTRIBUTION, source_type="osm",
        retrieved_at=datetime.now(timezone.utc), is_demo=False,
        confidence=confidence, completeness=completeness,
    ))


def fetch_overpass(bbox: str) -> list[dict]:
    url = settings.overpass_url
    headers = {"User-Agent": os.environ.get("OVERPASS_USER_AGENT", "GramBizAI/1.0 (scheduled OSM ingestion)")}
    try:
        resp = httpx.post(url, data={"data": _overpass_query(bbox)}, headers=headers, timeout=120)
        resp.raise_for_status()
    except httpx.HTTPStatusError:
        # Some Overpass mirrors reject POST at the Apache layer; the `data`
        # param is also accepted as a GET query string for read queries.
        resp = httpx.get(url, params={"data": _overpass_query(bbox)}, headers=headers, timeout=120)
        resp.raise_for_status()
    return resp.json().get("elements", [])


def _provenance(tags: Optional[dict] = None) -> dict:
    tags = tags or {}
    now = datetime.now(timezone.utc)
    completeness, confidence = _completeness_and_confidence(tags)
    return {
        "source_name": OSM_ATTRIBUTION,
        "source_url": "https://www.openstreetmap.org",
        "dataset_name": "OSM POIs (bbox)",
        "source_type": "osm",
        "retrieved_at": now,
        "geographic_level": _prov_geo_level(tags),
        "confidence": confidence,
        "completeness": completeness,
        "is_estimate": True,
        "is_demo": False,
        "methodology": "Overpass query for shop/amenity/tourism/infrastructure nodes; "
                       "completeness scored from tag richness (name/address/contact/hours/web); "
                       "mapped data may be incomplete.",
    }


def ingest(bbox: str, region: str, dry_run: bool = False) -> int:
    elements = fetch_overpass(bbox) if not dry_run else []
    snapshot = DataSnapshot(job_name=f"osm_{region}", status="running",
                            started_at=datetime.now(timezone.utc),
                            records_ingested=0)
    ingested = 0
    errors = 0
    ids_seen = set()
    with session_scope() as s:
        for el in elements:
            try:
                tags = el.get("tags", {})
                name = tags.get("name")
                lat = el.get("lat") or (el.get("center") or {}).get("lat")
                lon = el.get("lon") or (el.get("center") or {}).get("lon")
                if lat is None or lon is None:
                    errors += 1
                    continue
                if not (-90 <= float(lat) <= 90 and -180 <= float(lon) <= 180):
                    errors += 1
                    continue
                source_id = str(el.get("id"))
                if source_id in ids_seen:
                    continue
                ids_seen.add(source_id)
                cat = _category_for_tags(tags) or "other"
                kind = _infra_kind(tags)
                if name and (cat != "other" or kind):
                    if kind:
                        _upsert_infrastructure(s, kind, name, lat, lon, source_id, tags)
                        ingested += 1
                    else:
                        existing = s.query(Business).filter(Business.source == "osm",
                                                            Business.source_id == source_id).first()
                        if existing:
                            continue
                        b = Business(
                            name=name, category_code=cat, latitude=float(lat), longitude=float(lon),
                            source="osm", source_id=source_id,
                            address=tags.get("addr:street"),
                            tags=tags, **_provenance(tags),
                        )
                        s.add(b)
                        ingested += 1
            except Exception as e:  # noqa: BLE001
                errors += 1
                log.warning("error ingesting element: %s", e)
        snapshot.records_ingested = ingested
        snapshot.errors = errors
        snapshot.status = "completed"
        snapshot.finished_at = datetime.now(timezone.utc)
        s.add(snapshot)
    from app.log import log_event

    log_event("ingest", job=f"osm_{region}", records=ingested, errors=errors,
              dry_run=dry_run, status="completed")
    log.info("ingested=%s errors=%s", ingested, errors)
    return ingested


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--bbox", required=False, help="minlat,minlon,maxlat,maxlon (overrides region preset)")
    ap.add_argument("--region", default=DEFAULT_REGION,
                    help=("region key resolving to a preset bbox; one of "
                          + ", ".join(REGION_BBOXES.keys())))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO)
    bbox = args.bbox or REGION_BBOXES.get(args.region)
    if not bbox:
        raise SystemExit(f"Unknown region '{args.region}'. Known: {', '.join(REGION_BBOXES.keys())} "
                         "or pass --bbox explicitly.")
    ingest(bbox, args.region, args.dry_run)
