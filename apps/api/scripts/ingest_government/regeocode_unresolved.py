"""Re-geocode the Erode Census 2011 locations that OSM/Overpass could not name-match.

The original geocoders (``geocode_erode_locations``, ``ingest_village_census``)
resolve most towns/villages from an Overpass name index inside the Erode
district bbox, with a strict Nominatim fallback that demands "Erode" in the
display name.  ~167 locations are still unresolved because OSM simply has no
(name-matched) element for them.

This pass uses two keyless fallbacks, but only *auto-adopts* a coordinate when
it lands strictly inside the official Erode district bbox (the OSM relation
bbox used by the primary geocoder) and, for Photon, carries a real place tag:

  1. Nominatim `q = "<name>, Erode, Tamil Nadu"` (countrycodes=IN) - accepted
     when the hit coordinate is inside the bbox (the older strict "erode in
     display_name" test is dropped because Namenoun variant spellings lack the
     district token; the bbox test is the integrity guard instead).
  2. Photon (komoot) near the Erode district centroid - accepted only when the
     coordinate is inside the bbox and osm_value is a place type.

Out-of-bbox hits are *not* adopted (name collisions across Tamil Nadu are
common); they are written to ``erode_census_2011_nearmiss.json`` for manual
review.

Every newly geocoded location also adopts its official Census 2011 population
statistic from the same source CSVs the primary ingests use (never a demo
proxy, is_demo=False, confidence high).

Usage:
  python -m scripts.ingest_government.regeocode_unresolved
"""
from __future__ import annotations

import json
import logging
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from app.db.models import Location, PopulationStatistic
from app.db.session import session_scope
from app.log import log_event
from scripts.ingest_government.scrape_erode_census import PROC_DIR, read_csv

log = logging.getLogger("regeocode_unresolved")

BASE_DIR = Path(__file__).resolve().parents[2]  # apps/api
PROCESSED = BASE_DIR / "data" / "processed" / "erode_census"
UNRESOLVED_VILLAGES = PROCESSED / "erode_census_2011_unresolved_villages.json"
UNRESOLVED_TOWNS = PROCESSED / "erode_census_2011_unresolved.json"
NEARMISS_PATH = PROCESSED / "erode_census_2011_nearmiss.json"

CENTER = (11.3415, 77.7161)  # (~) Erode district centroid for Photon searches
# Official Erode district bbox (OSM relation), same as the primary geocoder.
BBOX = {"minlat": 11.02, "minlon": 76.83, "maxlat": 11.96, "maxlon": 77.94}
PLACE_TYPES = {"village", "town", "hamlet", "suburb", "locality"}
UA = {"User-Agent": "GramBizAI/1.0 (erode census research; contact: dev)"}


def _inside_bbox(lat: float, lon: float) -> bool:
    return (BBOX["minlat"] <= lat <= BBOX["maxlat"]
            and BBOX["minlon"] <= lon <= BBOX["maxlon"])


def _geocode_loose(name: str) -> tuple[dict | None, dict | None]:
    """Return (adopted_hit, nearmiss_hit) - never both."""
    near = None
    # 1. Nominatim, relaxed (accept by bbox, not display_name token)
    try:
        q = urllib.parse.urlencode({
            "q": f"{name}, Erode, Tamil Nadu", "countrycodes": "IN",
            "format": "jsonv2", "limit": "5"})
        with urllib.request.urlopen(  # noqa: S310 - Nominatim public API
            urllib.request.Request("https://nominatim.openstreetmap.org/search?" + q, headers=UA),
            timeout=15) as resp:
            hits = json.load(resp)
        for h in hits:
            lat, lon = float(h["lat"]), float(h["lon"])
            if _inside_bbox(lat, lon):
                return ({"lat": lat, "lon": lon,
                         "precision": h.get("type") or "village",
                         "method": "nominatim"},
                        None)
            if near is None:
                near = {"lat": lat, "lon": lon, "method": "nominatim",
                        "display": h.get("display_name")}
    except Exception as exc:  # noqa: BLE001
        log.warning("  nominatim failed for %s: %s", name, exc)
    if near is not None:
        time.sleep(1.0)
    # 2. Photon near district centroid
    try:
        q = urllib.parse.urlencode({"q": name, "lat": CENTER[0], "lon": CENTER[1], "limit": "5"})
        with urllib.request.urlopen(  # noqa: S310 - Photon public API
            urllib.request.Request("https://photon.komoot.io/api/?" + q, headers=UA),
            timeout=15) as resp:
            payload = json.load(resp)
        for f in payload.get("features", []):
            lon, lat = f["geometry"]["coordinates"]
            pr = f.get("properties") or {}
            if not _inside_bbox(lat, lon):
                if near is None:
                    near = {"lat": lat, "lon": lon, "method": "photon",
                            "display": pr.get("city") or pr.get("state") or ""}
                continue
            if pr.get("osm_value") in PLACE_TYPES:
                return ({"lat": lat, "lon": lon,
                         "precision": pr.get("osm_value") or "village",
                         "method": "photon"}, None)
    except Exception as exc:  # noqa: BLE001
        log.warning("  photon failed for %s: %s", name, exc)
    return None, near


def _census_values(r: dict) -> dict:
    cy = int(r.get("census_year") or 2011)
    values = {
        "population": r.get("population"),
        "males": r.get("males"),
        "females": r.get("females"),
        "census_year": cy,
        "reference_year": cy,
        "level": "village",
        "source_name": "Census India",
        "dataset_name": "Village & Village Panchayat population by Panchayat "
                        "Union (DCHB Erode, via erode.nic.in)",
        "source_type": "government",
        "confidence": "high",
        "is_estimate": False,
        "is_demo": False,
        "methodology": "Official Census of India 2011 figures for Erode "
                       "villages/towns (erode.nic.in).",
    }
    if r.get("households"):
        values["households"] = r["households"]
    if r.get("males") and r.get("females"):
        values["sex_ratio"] = round(float(r["females"]) / float(r["males"]) * 1000, 1)
    return values


def main(argv=None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    villages = [r for r in read_csv(PROC_DIR / "erode_census_2011_villages.csv")]
    towns = [r for r in read_csv(PROC_DIR / "erode_census_2011_towns.csv")
             if r["village"] not in ("(CT)", "(TP)", "m")]

    unresolved = {
        "village": json.loads(UNRESOLVED_VILLAGES.read_text()),
        "town": json.loads(UNRESOLVED_TOWNS.read_text()),
    }
    rows_by_kind = {"village": villages, "town": towns}
    near = {}
    adopted: dict[str, list[str]] = {"village": [], "town": []}
    stats_written = 0

    with session_scope() as s:
        existing = {
            r.village: r for r in s.query(Location).filter(
                Location.state == "Tamil Nadu", Location.district == "Erode",
                Location.village.isnot(None)).all()
        }
        for kind in ("village", "town"):
            for name, why in unresolved[kind].items():
                if name in existing:
                    continue
                for r in rows_by_kind[kind]:
                    if r["village"] == name:
                        row = r
                        break
                else:
                    row = None
                hit, near_hit = _geocode_loose(name)
                if hit is None:
                    if near_hit is not None:
                        near[name] = near_hit
                    time.sleep(1.0)
                    continue
                block = row["block"] if kind == "village" else name
                loc = Location(
                    state="Tamil Nadu", district="Erode", block=block,
                    village=name, latitude=hit["lat"], longitude=hit["lon"],
                    geo_precision=hit["precision"],
                    source_name="OpenStreetMap contributors",
                    source_url="https://www.openstreetmap.org",
                    dataset_name="OSM place/name index (Erode bbox)",
                    source_type="osm",
                    retrieved_at=datetime.now(timezone.utc),
                    geographic_level="village",
                    confidence="medium",
                    is_estimate=True,
                    is_demo=False,
                    methodology="Coordinate recovered in re-geocode pass from "
                                f"{hit['method']}; inside the official Erode "
                                "district bbox.",
                    metadata_json={"geocode_method": hit["method"],
                                   "regecode_pass": True},
                )
                s.add(loc)
                s.flush()
                existing[name] = loc
                if row is not None:
                    s.add(PopulationStatistic(location_id=loc.id,
                                              **_census_values(row)))
                    stats_written += 1
                adopted[kind].append(name)
                log.info("adopted %-22s %s %.4f,%.4f (block=%s)",
                         name, hit["method"], hit["lat"], hit["lon"], block)
                time.sleep(1.0)

    fresh = {
        "village": {n: w for n, w in unresolved["village"].items() if n not in adopted["village"]},
        "town": {n: w for n, w in unresolved["town"].items() if n not in adopted["town"]},
    }
    UNRESOLVED_VILLAGES.write_text(json.dumps(fresh["village"], indent=2))
    UNRESOLVED_TOWNS.write_text(json.dumps(fresh["town"], indent=2))
    NEARMISS_PATH.write_text(json.dumps(near, indent=2))

    log_event("ingest", job="erode_regeocode", adopted=sum(map(len, adopted.values())),
              stats_written=stats_written,
              still_unresolved=len(fresh["village"]) + len(fresh["town"]),
              nearmiss=len(near), status="completed")
    log.info("done: adopted villages=%d towns=%d stats_written=%d "
             "still_unresolved=%d nearmiss=%d",
             len(adopted["village"]), len(adopted["town"]), stats_written,
             len(fresh["village"]) + len(fresh["town"]), len(near))
    return 0


if __name__ == "__main__":
    sys.exit(main())
