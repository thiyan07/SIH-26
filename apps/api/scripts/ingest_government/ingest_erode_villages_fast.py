"""Fast ingest for remaining Erode villages — concurrent Photon geocoding (no 1.1s throttle).

Uses same JSONL as ingest_erode_villages.py but geocodes 197 unresolved villages
via Photon (komoot) concurrently (10 workers, ~0.2s per village = ~40s total vs 197*1.1s = 3.6min Nominatim sequential).

Usage:
  python -m scripts.ingest_government.ingest_erode_villages_fast
"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import httpx

from app.db.models import Location, PopulationStatistic
from app.db.session import session_scope
from scripts.ingest_government.ingest_erode_villages import load_rows

log = logging.getLogger("ingest_erode_villages_fast")
BASE_DIR = Path(__file__).resolve().parents[2]
PHOTON_URL = "https://photon.komoot.io/api/"

def photon_geocode(village: str, block: str) -> dict | None:
    # Try village + block + Erode + Tamil Nadu for bias
    q = f"{village}, {block}, Erode, Tamil Nadu"
    try:
        resp = httpx.get(PHOTON_URL, params={"q": q, "limit": 1, "lang": "en"}, timeout=10)
        resp.raise_for_status()
        feats = resp.json().get("features", [])
        if not feats:
            # fallback village only
            resp = httpx.get(PHOTON_URL, params={"q": f"{village}, Erode", "limit": 1}, timeout=10)
            resp.raise_for_status()
            feats = resp.json().get("features", [])
        if feats:
            lon, lat = feats[0]["geometry"]["coordinates"]
            props = feats[0].get("properties", {})
            # bias check: must be roughly Erode district bbox 11.02-11.96, 76.83-77.94
            if 10.5 <= lat <= 12.5 and 76.5 <= lon <= 78.5:
                return {"lat": lat, "lon": lon, "geo_precision": "village", "method": "photon", "raw": props}
    except Exception as e:
        log.debug("photon fail %s: %s", village, e)
    return None

def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default=str(BASE_DIR / "data/scrape/erode_villages/erode_villages.jsonl"))
    ap.add_argument("--jobs", type=int, default=10)
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    rows = load_rows(Path(args.input))
    print(f"loaded {len(rows)} villages")

    # Find unresolved
    # Use session to get existing
    with session_scope() as s:
        existing = {(loc.block, loc.village) for loc in s.query(Location).filter(
            Location.state=="Tamil Nadu", Location.district=="Erode", Location.village.isnot(None)).all()}
    todos = [r for r in rows if (r["block"], r["village"]) not in existing]
    print(f"todos {len(todos)} unresolved, existing {len(existing)}")
    if not todos:
        print("all villages already ingested")
        return 0

    # Concurrent geocode
    results = {}
    with ThreadPoolExecutor(max_workers=args.jobs) as ex:
        futs = {ex.submit(photon_geocode, r["village"], r["block"]): r for r in todos}
        for fut in as_completed(futs):
            r = futs[fut]
            try:
                hit = fut.result()
                if hit:
                    results[(r["block"], r["village"])] = (r, hit)
                    log.info("geocoded %-24s %s %.5f,%.5f", r["village"], r["block"], hit["lat"], hit["lon"])
                else:
                    log.info("no hit %-24s %s", r["village"], r["block"])
            except Exception as e:
                log.warning("error %s: %s", r["village"], e)

    print(f"geocoded {len(results)}/{len(todos)}")

    # Ingest hits
    from scripts.ingest_government.ingest import register_data_source
    from scripts.ingest_government.scrape_erode_census import SOURCE_DOC

    created_loc = created_stat = 0
    with session_scope() as s:
        register_data_source(s, "population_census_villages_scraped", "Erode Village Population (Census 2011 directory)", "demographics", "population_statistics", "Census 2011 village directory (DCHB Erode)")
        # reload existing map for FK
        existing_map = {(loc.block, loc.village): loc for loc in s.query(Location).filter(
            Location.state=="Tamil Nadu", Location.district=="Erode", Location.block.isnot(None)).all()}
        for (block, village), (r, hit) in results.items():
            if (block, village) in existing_map:
                continue
            loc = Location(
                state="Tamil Nadu", district="Erode", block=block, village=village,
                latitude=hit["lat"], longitude=hit["lon"],
                geo_precision=hit.get("geo_precision", "village"),
                source_name="Photon (OSM)", source_url="https://photon.komoot.io",
                dataset_name="Photon geocode (OSM)",
                source_type="osm", retrieved_at=datetime.now(timezone.utc),
                geographic_level="village", confidence="medium",
                is_estimate=True, is_demo=False,
                methodology="Coordinate from Photon (OSM) — fast concurrent geocode for Census village.",
                metadata_json={"geocode_method": hit.get("method"), "census_code": r.get("census_code")},
            )
            s.add(loc)
            s.flush()
            created_loc += 1
            existing_map[(block, village)] = loc
            # pop stat
            s.add(PopulationStatistic(
                location_id=loc.id,
                population=r["population"], households=r.get("households"),
                census_year=r.get("census_year", 2011), reference_year=2011,
                level="village",
                source_name="Census India", source_url=SOURCE_DOC,
                dataset_name="Erode District Village Directory (DCHB Census 2011, via vill.co.in)",
                source_type="government", confidence="high", is_estimate=False, is_demo=False,
                methodology="Official Census 2011 village figures",
                metadata_json={"census_code": r.get("census_code"), "gram_panchayat": r.get("gram_panchayat"), "area_ha": r.get("area_ha")},
            ))
            created_stat += 1
        print(f"created_loc {created_loc} created_stat {created_stat}")

    print("done")
    return 0

if __name__ == "__main__":
    import sys
    sys.exit(main())
