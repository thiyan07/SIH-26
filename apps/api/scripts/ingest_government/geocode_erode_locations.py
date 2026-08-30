"""Geocode Erode district Census 2011 towns into Location rows, then adopt
official Census population figures.

The 58 town/CT rows in ``erode_census_2011_towns.csv`` come from the official
DCHB Census 2011 extract (erode.nic.in).  Coordinates are NOT in the census
PDF; we derive geo (lat/lon) for each town from OpenStreetMap, which is free
and keyless (ODbL):

  1. an Overpass index of every named element inside the Erode district bbox
     (node/way/relation, `out center tags`), matched by normalized name; then
  2. Nominatim structured search, bounded to the same viewbox, as a fallback.

Locations that already exist in the DB (state/district/block/village) are
skipped - this is what lets ``scrape_erode_census --promote`` keep working for
the 4 demo towns while this script adds the remaining ~51.

Then ``adopt_census_rows`` is called over the full valid town set, which writes
official (is_demo=False, Census India) PopulationStatistic rows for every
Location that matches by name.

Usage:
  python -m scripts.ingest_government.geocode_erode_locations --no-download
  python -m scripts.ingest_government.geocode_erode_locations   # refetch index

Exit code 0 even with unresolved towns (they are reported on stdout); set
--strict to treat any unresolved town as an error.
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from app.db.models import Location
from app.db.session import session_scope
from app.log import log_event
from scripts.ingest_government.scrape_erode_census import (
    PROC_DIR,
    adopt_census_rows,
    read_csv,
)

log = logging.getLogger("geocode_erode_locations")

BASE_DIR = Path(__file__).resolve().parents[2]  # apps/api
RAW_DIR = BASE_DIR / "data" / "raw" / "erode_census"
INDEX_PATH = RAW_DIR / "erode_osm_names.json"

# Erode district administrative extent (from OSM relation bbox):
# lat 11.0227..11.9546, lon 76.8336..77.9330.  The earlier coarse town bbox
# (11.20 lat min) excluded south-Erode towns such as Kodumudi/Unjalur.
ERODE_BBOX = (11.02, 76.83, 11.96, 77.94)  # minlat, minlon, maxlat, maxlon
VIEWBOX = "76.8300,11.9600,77.9400,11.0200"  # nominatim viewbox (left,top,right,bottom)

UA = "GramBizAI/1.0 (erode census research; contact: dev)"


def _normalize(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def fetch_overpass_index() -> dict[str, dict]:
    if INDEX_PATH.exists():
        return json.loads(INDEX_PATH.read_text())
    q = (
        '[out:json][timeout:100];'
        '(node["name"]({b});way["name"]({b});rel["name"]({b}););'
        'out center tags 60000;'
    ).format(b=",".join(map(str, ERODE_BBOX)))
    req = urllib.request.Request(
        "https://overpass-api.de/api/interpreter",
        data=("data=" + urllib.parse.quote(q)).encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded", "User-Agent": UA},
    )
    with urllib.request.urlopen(req, timeout=120) as resp:  # noqa: S310 - OSM/Overpass public API
        payload = json.load(resp)
    index = {}
    for el in payload.get("elements", []):
        name = (el.get("tags") or {}).get("name")
        if not name:
            continue
        index.setdefault(_normalize(name), []).append(el)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    INDEX_PATH.write_text(json.dumps(index))
    log.info("indexed %d distinct OSM names -> %s", len(index), INDEX_PATH)
    return index


def _coord(el: dict) -> tuple[float, float]:
    lat = el.get("lat") or (el.get("center") or {}).get("lat")
    lon = el.get("lon") or (el.get("center") or {}).get("lon")
    return float(lat), float(lon)


def overpass_match(index: dict, name: str) -> list[dict]:
    hits = index.get(_normalize(name), [])
    # Prefer a place-tagged element (village/town/hamlet/suburb), else the
    # smallest-name approximation; sort place-tagged first, then by type.
    def key(e):
        t = (e.get("tags") or {}).get("place") or ""
        return (0 if t else 1, t)
    return sorted(hits, key=key)


def nominatim_match(name: str) -> list[dict]:
    params = urllib.parse.urlencode({
        "format": "jsonv2",
        "limit": "5",
        "q": name,
        "viewbox": VIEWBOX,
        "bounded": "1",
    })
    req = urllib.request.Request(
        "https://nominatim.openstreetmap.org/search?" + params,
        headers={"User-Agent": UA},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:  # noqa: S310
        hits = json.load(resp)
    # Reject same-named towns that resolve to a *different* district
    # (name collisions across Tamil Nadu are common).
    return [h for h in hits if "erode" in (h.get("display_name") or "").lower()]


def geocode(name: str, index: dict) -> dict | None:
    for el in overpass_match(index, name)[:3]:
        if el.get("type") in ("relation", "node", "way"):
            lat, lon = _coord(el)
            place = (el.get("tags") or {}).get("place")
            if place:
                return {"lat": lat, "lon": lon, "geo_precision": place,
                        "method": "overpass", "osm": True}
    try:
        hits = nominatim_match(name)
    except Exception as e:  # noqa: BLE001
        log.warning("nominatim failed for %s: %s", name, e)
        hits = []
    if hits:
        h = hits[0]
        lat, lon = float(h["lat"]), float(h["lon"])
        return {"lat": lat, "lon": lon,
                "geo_precision": h.get("type") or "village",
                "method": "nominatim", "osm": True}
    return None


def ensure_locations(rows: list[dict]) -> tuple[dict[str, dict], dict[str, str]]:
    index = fetch_overpass_index()
    coords: dict[str, dict] = {}
    unresolved = {}
    with session_scope() as s:
        existing = {
            r.village: r for r in s.query(Location).filter(
                Location.state == "Tamil Nadu", Location.district == "Erode"
            ).all()
        }
        for r in rows:
            name = r["village"]
            if name in existing:
                coords[name] = {"lat": existing[name].latitude,
                                "lon": existing[name].longitude,
                                "geo_precision": existing[name].geo_precision,
                                "method": "existing"}
                continue
            hit = geocode(name, index)
            if hit is None:
                unresolved[name] = "no OSM/Nominatim match in Erode viewbox"
                continue
            lat, lon = hit["lat"], hit["lon"]
            if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                unresolved[name] = f"bad coords {lat},{lon}"
                continue
            s.add(Location(
                state="Tamil Nadu", district="Erode", block=name, village=name,
                latitude=lat, longitude=lon,
                geo_precision=hit.get("geo_precision") or "village",
                source_name="OpenStreetMap contributors",
                source_url="https://www.openstreetmap.org",
                dataset_name="OSM place/name index (Erode bbox)",
                source_type="osm",
                retrieved_at=datetime.now(timezone.utc),
                geographic_level="village",
                confidence="medium",
                is_estimate=True,
                is_demo=False,
                methodology="Coordinate derived from OSM name/place match "
                            "(Overpass index or Nominatim viewbox-bounded); "
                            "used to locate the Census 2011 town row.",
                metadata_json={"geocode_method": hit.get("method")},
            ))
            coords[name] = hit
            time.sleep(1.1)  # Nominatim usage policy: ~1 req/s
    return coords, unresolved


def main(argv=None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-download", action="store_true",
                    help="reuse a previously cached Overpass name index")
    ap.add_argument("--strict", action="store_true",
                    help="exit non-zero if any town could not be geocoded")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    if args.no_download:
        INDEX_PATH.touch(exist_ok=True)

    rows = [r for r in read_csv(PROC_DIR / "erode_census_2011_towns.csv")
            if r["village"] not in ("(CT)", "(TP)", "m")]
    log.info("geocoding %d Census town rows", len(rows))

    coords, unresolved = ensure_locations(rows)
    log.info("geocoded=%d unresolved=%d", len(coords), len(unresolved))
    for name, why in unresolved.items():
        log.warning("UNRESOLVED %-24s %s", name, why)
    if unresolved:
        (BASE_DIR / "data" / "processed" / "erode_census"
         / "erode_census_2011_unresolved.json").write_text(
            json.dumps(unresolved, indent=2))

    n = adopt_census_rows(rows)
    log.info("adopted official census rows for %d locations", n)
    log_event("ingest", job="erode_census_geocode", locations=len(coords),
              unresolved=len(unresolved), adopted=n, status="completed")
    if args.strict and unresolved:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
