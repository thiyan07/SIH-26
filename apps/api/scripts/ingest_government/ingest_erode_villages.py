"""Ingest scrapled Erode village directory (Census 2011) into the DB.

Reads the JSONL produced by ``scrape_erode_villages`` and:

  1. matches each village to an existing Location by (state, district, block,
     village) -- updating its PopulationStatistic (level='village') where
     present, or adding a new one;
  2. for villages with no Location yet (they were missing entirely from our
     coverage), geocodes them against the cached OSM index and creates a
     Location + an official Census 2011 PopulationStatistic row.

Everything written is official (is_demo=False) Census 2011 data with
confidence='high' and is never fabricated.  Villages whose CD Block is
"Not Under Any CD Block" are skipped, as are rows with no population.

Usage:
  python -m scripts.ingest_government.ingest_erode_villages \
      [--input data/scrape/erode_villages/erode_villages.jsonl] [--strict]
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from app.db.models import DataSnapshot, Location, PopulationStatistic
from app.db.session import session_scope
from app.log import log_event
from scripts.ingest_government.geocode_erode_locations import (
    fetch_overpass_index,
    geocode,
)
from scripts.ingest_government.ingest import register_data_source
from scripts.ingest_government.scrape_erode_census import SOURCE_DOC

log = logging.getLogger("ingest_erode_villages")

BASE_DIR = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = BASE_DIR / "data" / "scrape" / "erode_villages" / "erode_villages.jsonl"


def load_rows(path: Path) -> list[dict]:
    rows = [json.loads(ln) for ln in path.open() if ln.strip()]
    keep = []
    for r in rows:
        block = (r.get("block") or "").strip()
        if block in ("", "Not Under Any CD Block"):
            continue
        if not r.get("population"):
            continue
        keep.append({**r, "block": block, "village": (r.get("village") or "").strip()})
    return keep


def ingest(rows: list[dict], strict: bool) -> dict:
    index = fetch_overpass_index()
    snapshot = DataSnapshot(job_name="census_villages_erode_scraped",
                            status="running", started_at=datetime.now(timezone.utc))
    unresolved: dict[str, str] = {}
    updated = created_stat = created_loc = matched = 0

    with session_scope() as s:
        register_data_source(
            s, "population_census_villages_scraped",
            "Erode Village Population (Census 2011 directory)",
            "demographics", "population_statistics",
            "Census 2011 village directory (DCHB Erode) - historical, "
            "not current population")
        existing = {
            (loc.block, loc.village): loc for loc in s.query(Location).filter(
                Location.state == "Tamil Nadu", Location.district == "Erode",
                Location.block.isnot(None), Location.village.isnot(None),
            ).all()
        }
        for r in rows:
            key = (r["block"], r["village"])
            loc = existing.get(key)
            if loc is None:
                time.sleep(1.1)  # Nominatim usage policy: ~1 req/s
                hit = geocode(r["village"], index)
                if hit is None:
                    unresolved[r["village"]] = "no OSM/Nominatim match"
                    continue
                lat, lon = hit["lat"], hit["lon"]
                if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                    unresolved[r["village"]] = f"bad coords {lat},{lon}"
                    continue
                loc = Location(
                    state="Tamil Nadu", district="Erode", block=r["block"],
                    village=r["village"], latitude=lat, longitude=lon,
                    geo_precision=hit.get("geo_precision") or "village",
                    source_name="OpenStreetMap contributors",
                    source_url="https://www.openstreetmap.org",
                    dataset_name="OSM place/name index (Erode bbox)",
                    source_type="osm",
                    retrieved_at=datetime.now(timezone.utc),
                    geographic_level="village", confidence="medium",
                    is_estimate=True, is_demo=False,
                    methodology="Coordinate from OSM name match (Overpass); "
                                "used to locate the Census 2011 village.",
                    metadata_json={"geocode_method": hit.get("method"),
                                   "census_code": r.get("census_code")},
                )
                s.add(loc)
                s.flush()
                created_loc += 1
                existing[key] = loc

            cy = r.get("census_year") or 2011
            stat = s.query(PopulationStatistic).filter(
                PopulationStatistic.location_id == loc.id,
                PopulationStatistic.census_year == cy,
            ).first()
            values = {
                "population": r["population"],
                "households": r.get("households"),
                "census_year": cy,
                "reference_year": cy,
                "level": "village",
                "source_name": "Census India",
                "source_url": SOURCE_DOC,
                "dataset_name": "Erode District Village Directory (DCHB "
                                "Census 2011, via vill.co.in)",
                "source_type": "government",
                "confidence": "high",
                "is_estimate": False,
                "is_demo": False,
                "methodology": "Official Census of India 2011 village figures "
                               "from the District Census Handbook, served by "
                               "the Erode village directory.",
                "metadata_json": {"census_code": r.get("census_code"),
                                  "gram_panchayat": r.get("gram_panchayat"),
                                  "area_ha": r.get("area_ha")},
            }
            if stat:
                for k, v in values.items():
                    setattr(stat, k, v)
                updated += 1
            else:
                s.add(PopulationStatistic(location_id=loc.id, **values))
                created_stat += 1
            matched += 1

        snapshot.records_ingested = matched
        snapshot.errors = len(unresolved)
        snapshot.status = "completed"
        snapshot.finished_at = datetime.now(timezone.utc)
        s.add(snapshot)

    if unresolved:
        out = BASE_DIR / "data" / "processed" / "erode_census" / "erode_villages_unresolved.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(unresolved, indent=2))
        log.warning("unresolved %d villages -> %s", len(unresolved), out)
        for name, why in list(unresolved.items())[:20]:
            log.warning("UNRESOLVED %-24s %s", name, why)

    log_event("ingest", job="census_villages_erode_scraped", records=matched,
              locations_created=created_loc, stats_created=created_stat,
              stats_updated=updated, unresolved=len(unresolved),
              errors=len(unresolved), status="completed")
    result = {"matched": matched, "created_loc": created_loc,
              "created_stat": created_stat, "updated": updated,
              "unresolved": unresolved}
    if strict and unresolved:
        raise SystemExit(1)
    return result


def main(argv=None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default=str(DEFAULT_INPUT))
    ap.add_argument("--strict", action="store_true")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    rows = load_rows(Path(args.input))
    if not rows:
        log.error("no rows loaded from %s", args.input)
        return 1
    log.info("loaded %d villages from %s", len(rows), args.input)
    result = ingest(rows, args.strict)
    log.info("matched=%d created_loc=%d created_stat=%d updated=%d unresolved=%d",
             result["matched"], result["created_loc"], result["created_stat"],
             result["updated"], len(result["unresolved"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
