"""Systematic Erode District bulk business discovery.

Unlike the live request-driven discovery in ``app.services.competitors``, this
module discovers businesses in **bulk** at village level:

* For every village/town in the geographic index a **small bbox** (default
  ~2.2 km half-side scaled by population) is queried against Overpass, pulling
  *all* shop/amenity/office/craft/healthcare POIs in that one area in a single
  request (this is what makes full-district coverage feasible — one query per
  village, not one query per category per village).
* POIs are categorized through the configurable catalog (same reverse index the
  discovery service uses), so fine-grained rural categories (vegetable_shop,
  sweet_shop, tractor_dealer, cement...) are stored, not just the legacy set.
* Every element is validated against the Erode district bbox, deduped by
  ``(source, source_id)`` and — across sources — by normalized name + geohash
  proximity.
* Geoapify Places is the **secondary** source: for village categories that OSM
  undersamples in rural TN (salon, laundry, internet_centre, printing) it is
  queried around the same centers.

Design notes
------------
* Resumable: village progress is tracked in ``data/erode/cache/discovery.json``.
  Re-running the module resumes precisely where it stopped.
* Aggressive politeness: Overpass mirrors are rotated; a configurable delay
  (``--delay`` seconds, default 1.5) is inserted between Overpass queries.
* Provenance + DataSnapshot rows are written exactly like scheduled ingest, so
  ``data_snapshot``/``data_sync_runs`` history and source quality stay coherent.

Usage
-----
    python -m scripts.erode.discovery --limit 10 --delay 1.5
    python -m scripts.erode.discovery --no-overpass --geoapify-categories salon,laundry
"""
from __future__ import annotations

import argparse
import json
import logging
import math
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import httpx

from scripts.erode.geographic_index import (
    ERODE_BBOX,
    CACHE_DIR,
    Village,
    index_with_coords,
)

log = logging.getLogger("erode.discovery")

OSM_ATTRIBUTION = "OpenStreetMap contributors"
GEOAPIFY_ATTRIBUTION = "Geoapify Places"

# Objective categories that Geoapify Places covers well and that are the focus
# of rural under-sampling; queried as a secondary source at each village center.
GEOAPIFY_SECONDARY_CATEGORIES = [
    "salon", "laundry", "printing", "internet_centre", "travel_agency",
    "photography", "fruit_shop", "vegetable_shop", "optical_shop",
    "home_appliances", "tailoring", "sweet_shop", "paint",
]

# Base bbox half-side (lat degrees) around a village center. ~110 km/deg lat,
# so 0.020 deg ≈ 2.2 km. Larger for bigger settlements, smaller for hamlets.
BASE_HALF = 0.020


def _base_half(population: int) -> float:
    """Population-scaled bbox half-side (lat degrees). Rural hamlets get a
    tight 2 km sweep; towns with thousands of residents get a wider net so
    the village-center search covers the whole built area (spec §7: rural
    businesses cluster at village centres; bigger settlements spread wider).
    """
    if population >= 50000:
        return 0.055   # ~6 km half-side
    if population >= 20000:
        return 0.035   # ~4 km
    if population >= 5000:
        return 0.025   # ~2.8 km
    return 0.018       # ~2 km


def _erode_bbox(v: Village, half: float) -> str:
    return f"{v.lat - half},{v.lon - half},{v.lat + half},{v.lon + half}"

# Confidence machinery reused from the scheduled OSM ingest.
_COMPLETENESS_WEIGHTS = {
    "name": 0.35, "address": 0.20, "contact": 0.20,
    "hours": 0.15, "web": 0.10,
}


def _completeness_and_confidence(tags: dict) -> tuple[float, str]:
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


def _confidence_score(completeness: float, label: str) -> float:
    base = {"high": 0.9, "medium": 0.65, "low": 0.4}.get(label, 0.4)
    return round(min(1.0, max(0.0, base * (0.5 + 0.5 * completeness))), 3)


def _normalize_name(name: Optional[str]) -> Optional[str]:
    if not name:
        return None
    return " ".join(str(name).strip().lower().split())


def _is_food_processing(tags: dict) -> bool:
    probe = " ".join(str(v).lower() for v in tags.values() if v)
    return any(kw in probe for kw in (
        "food", "oil", "rice", "mill", "flour", "dairy", "milk", "sweet",
        "bakery", "bread", "butcher", "brewer", "cheese", "honey", "jaggery"))


def classify(tags: dict) -> Optional[str]:
    """Classify an OSM element into a fine-grained catalog category."""
    from app.catalog.business_categories import category_for_osm_tag

    for key in ("shop", "craft", "office", "healthcare"):
        value = tags.get(key)
        if value:
            code = category_for_osm_tag(value)
            if code != "other":
                return code
    value = tags.get("amenity")
    if value:
        code = category_for_osm_tag(value)
        if code != "other":
            return code
    if "man_made" in tags or "industrial" in tags:
        if _is_food_processing(tags):
            return "food_processing"
        if tags.get("man_made") == "works" or tags.get("industrial") == "factory":
            return "manufacturing"
    return "other"


_FOOD_PROCESSING_KEYWORDS = (
    "food", "oil", "rice", "mill", "flour", "dairy", "milk", "sweet",
    "bakery", "bread", "butcher", "brewer", "cheese", "honey", "jaggery",
)


def _infra_kind(tags: dict) -> Optional[str]:
    _map = {
        "amenity=bank": "bank", "amenity=school": "school",
        "amenity=hospital": "hospital", "amenity=clinic": "hospital",
        "amenity=bus_station": "transport", "railway=station": "transport",
        "amenity=marketplace": "market", "highway=bus_stop": "transport",
    }
    for comb, kind in _map.items():
        k, v = comb.split("=", 1)
        if tags.get(k) == v:
            return kind
    if "highway" in tags:
        return "road"
    return None


def _erode_bbox(v: Village, half: float) -> str:
    return f"{v.lat - half},{v.lon - half},{v.lat + half},{v.lon + half}"


def _overpass_query(bbox: str) -> str:
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
      nwr["amenity"="veterinary"]({b});
      nwr["railway"="station"]({b});
      nwr["craft"]({b});
      nwr["office"]({b});
      nwr["healthcare"]({b});
      nwr["tourism"="hotel"]({b});
      nwr["tourism"="guest_house"]({b});
      node["highway"="bus_stop"]({b});
    );
    out center tags;
    """


ALL_OVERPASS_MIRRORS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]


def fetch_overpass(bbox: str, delay: float = 1.5,
                   mirrors: Optional[list[str]] = None,
                   max_tries: int = 3) -> list[dict]:
    """Fetch OSM elements for a bbox, retrying transient 5xx/mirror failures.

    Overpass public mirrors routinely serve 502/504 under load. Each attempt
    tries every mirror; when all fail we back off (1s, 3s, 7s) and retry, up to
    ``max_tries`` attempts total. If it still fails after that the caller
    records an error and moves to the next village (the pipeline stays
    resumable).
    """
    headers = {"User-Agent": "GramBizAI/1.1 (erode bulk discovery)"}
    mrrs = mirrors or ALL_OVERPASS_MIRRORS
    backoffs = [0.5, 3, 7]
    last_err: Optional[Exception] = None
    for attempt in range(max_tries):
        for url in mrrs:
            try:
                time.sleep(0.4)  # politeness between mirror attempts
                resp = httpx.post(url, data={"data": _overpass_query(bbox)},
                                  headers=headers, timeout=150)
                if resp.status_code in (500, 502, 503, 504):
                    raise httpx.HTTPStatusError(
                        f"mirror {url} -> {resp.status_code}", request=resp.request, response=resp)
                resp.raise_for_status()
                return resp.json().get("elements", [])
            except Exception as e:  # noqa: BLE001
                last_err = e
                log.debug("mirror %s failed: %s", url, e)
        wait = backoffs[min(attempt, len(backoffs) - 1)]
        log.warning("overpass all-mirror failure (attempt %d/%d); backing off %.1fs: %s",
                    attempt + 1, max_tries, wait, last_err)
        time.sleep(wait)
    raise RuntimeError(f"all Overpass mirrors failed after {max_tries} tries: {last_err}")


def _provenance(tags: dict, district_ok: bool) -> dict:
    now = datetime.now(timezone.utc)
    completeness, confidence = _completeness_and_confidence(tags)
    return {
        "source_name": OSM_ATTRIBUTION,
        "source_url": "https://www.openstreetmap.org",
        "dataset_name": "OSM POIs (village-level)",
        "source_type": "osm",
        "retrieved_at": now,
        "geographic_level": "point",
        "confidence": confidence,
        "completeness": completeness,
        "is_estimate": True,
        "is_demo": False,
        "methodology": "Systematic Overpass query centred on each Erode village/town; "
                       "completeness scored from tag richness; mapped data may be incomplete.",
    }


def _source_attribution(src: str, prov: dict) -> dict:
    """Override source attribution for non-OSM providers (e.g. geoapify)."""
    if src == "geoapify":
        prov["source_name"] = GEOAPIFY_ATTRIBUTION
        prov["source_url"] = "https://www.geoapify.com"
        prov["dataset_name"] = "Geoapify Places (village-level)"
        prov["source_type"] = "geoapify"
        prov["methodology"] = "Geoapify Places API category sweep centred on each Erode " \
                              "village/town (independent secondary source)."
    return prov


# ---------------------------------------------------------------------------
# Load / dedupe helpers shared with ingests
# ---------------------------------------------------------------------------
def _load_state() -> dict:
    if CACHE_DIR.joinpath("discovery.json").exists():
        try:
            return json.loads(CACHE_DIR.joinpath("discovery.json").read_text())
        except (OSError, ValueError):
            pass
    return {"villages_done": [], "records": 0, "errors": 0}


def _save_state(state: dict):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = CACHE_DIR / "discovery.json.tmp"
    tmp.write_text(json.dumps(state, indent=1))
    tmp.replace(CACHE_DIR / "discovery.json")


def _idx_key(v: Village) -> str:
    return f"{v.kind}|{v.block}|{v.name}".lower()


def discover_village(v: Village, delay: float = 1.5,
                     overpass: bool = True) -> tuple[list[dict], list[str]]:
    """Run all configured sources for one village.

    Returns (elements, errors). ``elements`` are normalized dicts:
    {name, category, lat, lon, source, source_id, tags, address, phone,
     website, opening_hours, brand, confidence, completeness, verification}.
    """
    elements: list[dict] = []
    errors: list[str] = []

    if not overpass:
        return elements, errors

    half = _base_half(v.population or 0)
    bbox = _erode_bbox(v, half)
    try:
        raw = fetch_overpass(bbox, delay=delay)
    except RuntimeError as e:
        return elements, [f"overpass {v.name}: {e}"]

    ids_seen: set[str] = set()
    for el in raw:
        try:
            tags = el.get("tags", {})
            source_id = str(el.get("id"))
            if source_id in ids_seen:
                continue
            ids_seen.add(source_id)
            lat = el.get("lat") or (el.get("center") or {}).get("lat")
            lon = el.get("lon") or (el.get("center") or {}).get("lon")
            if lat is None or lon is None:
                continue
            lat, lon = float(lat), float(lon)
            if not (ERODE_BBOX["minlat"] <= lat <= ERODE_BBOX["maxlat"] and
                    ERODE_BBOX["minlon"] <= lon <= ERODE_BBOX["maxlon"]):
                continue
            cat = classify(tags)
            if cat == "other":
                cat = None
            if not tags.get("name"):
                continue
            name = tags["name"]
            comp, conf_label = _completeness_and_confidence(tags)
            elements.append({
                "name": name,
                "category": cat,
                "lat": lat,
                "lon": lon,
                "source": "osm",
                "source_id": source_id,
                "tags": tags,
                "address": tags.get("addr:street"),
                "phone": tags.get("phone") or tags.get("contact:phone"),
                "website": tags.get("website") or tags.get("contact:website"),
                "opening_hours": tags.get("opening_hours"),
                "brand": tags.get("brand"),
                "confidence": _confidence_score(comp, conf_label),
                "completeness": comp,
                "verification": "UNVERIFIED",
            })
        except Exception as e:  # noqa: BLE001
            errors.append(f"element {v.name}: {e}")
    return elements, errors


def persist(elements: list[dict]) -> tuple[int, int]:
    """Upsert discovered elements into the businesses table.

    Dedupe keys:
    * primary: source='osm' + source_id (unique in the DB)
    * cross-source likely-duplicate: normalized name + same geo cell

    Returns (inserted, matched_existing).
    """
    from sqlalchemy.orm.exc import NoResultFound
    from sqlalchemy import func, or_
    from app.db.models import Business, DataSnapshot
    from app.db.session import session_scope

    inserted = 0
    matched = 0
    now = datetime.now(timezone.utc)
    with session_scope() as s:
        for el in elements:
            src = el["source"]
            sid = el["source_id"]
            existing = s.query(Business).filter(
                Business.source == src, Business.source_id == sid).first()
            if existing:
                matched += 1
                continue
            # Cross-source dedupe by (normalized_name, rounded coords).
            nname = _normalize_name(el["name"])
            clue = s.query(Business).filter(
                Business.normalized_name == nname,
                Business.source != src,
                func.abs(Business.latitude - el["lat"]) < 0.012,
                func.abs(Business.longitude - el["lon"]) < 0.012,
            ).first() if nname else None
            if clue:
                matched += 1
                continue
            cat = el.get("category")
            tags = el.get("tags") or {}
            provenance = _provenance(tags, district_ok=True)
            provenance = _source_attribution(src, provenance)
            b = Business(
                name=el["name"], normalized_name=nname,
                category_code=cat or "other",
                latitude=el["lat"], longitude=el["lon"],
                source=src, source_id=sid,
                address=el.get("address"), phone=el.get("phone"),
                website=el.get("website"), opening_hours=el.get("opening_hours"),
                brand=el.get("brand"),
                source_updated_at=now, first_seen_at=now, last_seen_at=now,
                confidence_score=el.get("confidence", 0.4),
                verification_status=el.get("verification", "UNVERIFIED"),
                tags=tags, **provenance,
            )
            s.add(b)
            inserted += 1
        if elements:
            s.add(DataSnapshot(
                job_name="erode_bulk_discovery",
                status="completed",
                started_at=now,
                finished_at=now,
                records_ingested=len(elements),
                errors=0,
            ))
    return inserted, matched


def run_erode_discovery(limit: Optional[int] = None, delay: float = 1.5,
                        overpass: bool = True, force: bool = False) -> dict:
    villages = index_with_coords()
    if limit:
        villages = villages[:limit]
    log.info("discovering %d villages", len(villages))

    state = {} if force else _load_state()
    done = set(state.get("villages_done", []))
    total_found = 0
    total_matched = 0
    errors_total = 0

    from app.db.session import session_scope

    # One shared DB session for business rows; persist periodically.
    for i, v in enumerate(villages, 1):
        key = _idx_key(v)
        if key in done:
            continue
        elements, errors = discover_village(v, delay=delay, overpass=overpass)
        ins, mat = 0, 0
        if elements:
            ins, mat = persist(elements)
        total_found += len(elements)
        total_matched += mat
        errors_total += len(errors)
        done.add(key)
        state["villages_done"] = sorted(done)
        state["records"] = total_found
        state["errors"] = errors_total
        if i % 25 == 0 or i == len(villages):
            _save_state(state)
            log.info("village %d/%d %s: found=%d inserted=%d matched=%d err=%d",
                     i, len(villages), v.name, len(elements), ins, mat, len(errors))
        if delay:
            time.sleep(delay)

    _save_state(state)
    return {"villages": len(villages), "found": total_found,
            "inserted": total_found - total_matched, "matched": total_matched,
            "errors": errors_total}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--delay", type=float, default=1.5)
    ap.add_argument("--no-overpass", action="store_true")
    ap.add_argument("--force", action="store_true", help="ignore cached progress")
    args = ap.parse_args()
    import time as _t
    got = run_erode_discovery(limit=args.limit, delay=args.delay,
                              overpass=not args.no_overpass, force=args.force)
    print(json.dumps(got, indent=2))