"""Ingest Census 2011 village-panchayat population for Erode district.

Source is the same official, keyless, government-open-data PDF as
``scrape_erode_census`` but the *Village* publication (2018062196.pdf,
"TOTAL POPULATION AND POPULATION OF SC AND ST FOR VILLAGE PANCHAYATS AND
PANCHAYAT UNIONS", erode.nic.in).  Unlike the DCHB town extract this table has
no households column, so only population/males/females are loaded.

Pipeline:

  1. rasterize the PDF with ``pdftotext -layout`` and parse the 14 per-union
     village tables (plus the ABSTRACT table on page 1);
  2. self-validate: per-union village count + population, and grand totals,
     must match the ABSTRACT, and males+females must equal population for
     every row (fail fast otherwise);
  3. write the parsed rows to ``erode_census_2011_villages.csv``;
  4. geocode every village against the cached OSM name index (Overpass) with a
     Nominatim viewbox fallback - identifiers are required because
     ``Location.latitude/longitude`` are NOT NULL.  Villages that cannot be
     located go to ``erode_census_2011_unresolved_villages.json`` (never
     fabricated);
  5. persist Locations + official (is_demo=False, Census India) 2011
     PopulationStatistic rows at level='village', block = Panchayat Union.

Villages whose name already matches a town-style Location (block==village,
such as Kodumudi) reuse the existing location and are skipped, because those
towns already carry official census rows with households from the DCHB pass.

Usage:
  python -m scripts.ingest_government.ingest_village_census --no-download
  python -m scripts.ingest_government.ingest_village_census --strict
"""
from __future__ import annotations

import argparse
import csv
import json
import logging
import re
import sys
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
from scripts.ingest_government.scrape_erode_census import (
    PROC_DIR,
    SOURCE_DOC,
    pdf_text,
)

log = logging.getLogger("ingest_village_census")

BASE_DIR = Path(__file__).resolve().parents[2]  # apps/api
RAW_DIR = BASE_DIR / "data" / "raw" / "erode_census"
VILLAGES_PDF = RAW_DIR / "villages.pdf"
CSV_PATH = PROC_DIR / "erode_census_2011_villages.csv"
UNRESOLVED_PATH = (BASE_DIR / "data" / "processed" / "erode_census"
                   / "erode_census_2011_unresolved_villages.json")

_UNION_RE = re.compile(r"^\s*([A-Z][A-Z .'()]+?)\s+PANCHAYAT UNION\b(\s*-\s*Cont\.?)?\s*$")
_ROW_RE = re.compile(
    r"^\s*(?P<sl>\d+)\s+(?P<name>[A-Za-z0-9][A-Za-z0-9 .'()-]*?)\s{2,}"
    r"(?P<pop>[\d,]+)\s+(?P<mal>[\d,]+)\s+(?P<fem>[\d,]+)"
)
_ABS_RE = re.compile(
    r"^\s*(?P<sl>\d+)\s+(?P<name>[A-Z][A-Za-z ]+?)\s+(?P<nv>\d+)\s+"
    r"(?P<pop>[\d,]+)\s+(?P<mal>[\d,]+)\s+(?P<fem>[\d,]+)"
)


def _num(raw: str) -> int:
    return int(raw.replace(",", ""))


def parse_village_panchayats(text: str) -> list[dict]:
    """Parse the per-union village tables and validate against the ABSTRACT."""
    abstract: dict[str, tuple[int, int]] = {}
    for ln in text.splitlines()[:45]:
        m = _ABS_RE.match(ln.rstrip())
        if m:
            abstract[m.group("name").upper()] = (
                int(m.group("nv")), _num(m.group("pop")))

    cur = None
    rows = []
    for ln in text.splitlines():
        m = _UNION_RE.match(ln)
        if m:
            cur = m.group(1).strip()
            continue
        if not cur:
            continue
        r = _ROW_RE.match(ln.rstrip())
        if not r:
            continue
        name = r.group("name").strip()
        if not any(ch.isalpha() for ch in name):
            continue  # column legend rows ("1 2 3 ...")
        if name.upper() in ("TOTAL", "GRAND TOTAL"):
            continue
        pop, mal, fem = (_num(r.group(k)) for k in ("pop", "mal", "fem"))
        if mal + fem != pop:
            raise ValueError(f"sanity failed {cur}/{name}: {mal}+{fem}!={pop}")
        rows.append({
            "state": "Tamil Nadu",
            "district": "Erode",
            "block": cur.title(),
            "village": name,
            "population": pop,
            "males": mal,
            "females": fem,
            "census_year": 2011,
        })

    by_union: dict[str, list[dict]] = {}
    for r in rows:
        by_union.setdefault(r["block"], []).append(r)
    for union, us in by_union.items():
        exp_n, exp_pop = abstract.get(union.upper(), (None, None))
        got_n, got_pop = len(us), sum(r["population"] for r in us)
        if exp_n is not None and (exp_n != got_n or exp_pop != got_pop):
            raise ValueError(
                f"union {union}: got n={got_n} pop={got_pop} "
                f"expected n={exp_n} pop={exp_pop}")
    missing = (set(abstract) - set(u.upper() for u in by_union)) - {"GRAND TOTAL"}
    if missing:
        raise ValueError(f"unions missing from parse: {sorted(missing)}")
    rows.sort(key=lambda r: (r["block"], r["village"]))
    return rows


def write_csv(rows: list[dict]) -> int:
    PROC_DIR.mkdir(parents=True, exist_ok=True)
    fields = ["state", "district", "block", "village", "population",
              "males", "females", "census_year"]
    with open(CSV_PATH, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def geocode_and_adopt(rows: list[dict]) -> dict:
    """Create Locations for villages and write official census statistics."""
    index = fetch_overpass_index()
    unresolved: dict[str, str] = {}
    created = matched = skipped = 0

    snapshot = DataSnapshot(job_name="census_villages_erode", status="running",
                            started_at=datetime.now(timezone.utc))
    with session_scope() as s:
        register_data_source(
            s, "population_census_villages",
            "Village Panchayat Population (Census 2011)",
            "demographics", "population_statistics",
            "Census 2011 village-panchayat baseline - historical, not current population")
        existing = {
            loc.village: loc for loc in s.query(Location).filter(
                Location.state == "Tamil Nadu",
                Location.district == "Erode",
                Location.village.isnot(None),
            ).all()
        }
        logged = 0
        for r in rows:
            name, union = r["village"], r["block"]
            loc = existing.get(name)
            if loc is None:
                hit = geocode(name, index)
                if hit is None:
                    unresolved[name] = "no OSM/Nominatim match in Erode viewbox"
                    continue
                lat, lon = hit["lat"], hit["lon"]
                if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                    unresolved[name] = f"bad coords {lat},{lon}"
                    continue
                loc = Location(
                    state="Tamil Nadu", district="Erode", block=union,
                    village=name, latitude=lat, longitude=lon,
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
                                "used to locate the Census 2011 village "
                                "panchayat row.",
                    metadata_json={"geocode_method": hit.get("method"),
                                   "panchayat_union": union},
                )
                s.add(loc)
                s.flush()
                created += 1
                existing[name] = loc
            if name in existing and loc.block == loc.village:
                skipped += 1  # pre-existing town-style location carries census row
                continue
            cy = r["census_year"]
            stat = s.query(PopulationStatistic).filter(
                PopulationStatistic.location_id == loc.id,
                PopulationStatistic.census_year == cy,
            ).first()
            values = {
                "population": r["population"],
                "males": r["males"],
                "females": r["females"],
                "census_year": cy,
                "reference_year": cy,
                "level": "village",
                "source_name": "Census India",
                "source_url": SOURCE_DOC,
                "dataset_name": "Village & Village Panchayat population by "
                                "Panchayat Union (DCHB Erode, via erode.nic.in)",
                "source_type": "government",
                "confidence": "high",
                "is_estimate": False,
                "is_demo": False,
                "methodology": "Official Census of India 2011 figures for "
                               "village panchayats from the Erode district "
                               "government portal (erode.nic.in/documents/census).",
            }
            if r["males"] and r["females"]:
                values["sex_ratio"] = round(r["females"] / r["males"] * 1000, 1)
            if stat:
                for k, v in values.items():
                    setattr(stat, k, v)
            else:
                s.add(PopulationStatistic(location_id=loc.id, **values))
            matched += 1
            logged += 1
            if logged % 50 == 0:
                log.info("progress: %d matched, %d created, %d unresolved",
                         matched, created, len(unresolved))

        snapshot.records_ingested = matched
        snapshot.errors = 0
        snapshot.status = "completed"
        snapshot.finished_at = datetime.now(timezone.utc)
        s.add(snapshot)

    if unresolved:
        UNRESOLVED_PATH.parent.mkdir(parents=True, exist_ok=True)
        UNRESOLVED_PATH.write_text(json.dumps(unresolved, indent=2))
    log_event("ingest", job="census_villages_erode", records=matched,
              locations_created=created, skipped=skipped,
              unresolved=len(unresolved), errors=0, status="completed")
    return {"matched": matched, "created": created, "skipped": skipped,
            "unresolved": unresolved}


def main(argv=None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-download", action="store_true",
                    help="parse already-downloaded villages.pdf only")
    ap.add_argument("--strict", action="store_true",
                    help="exit non-zero if any village could not be geocoded")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    if not VILLAGES_PDF.exists():
        log.error("missing %s; run scrape_erode_census first (fetch pdfs)", VILLAGES_PDF)
        return 1

    text = pdf_text(VILLAGES_PDF)
    rows = parse_village_panchayats(text)
    grand = sum(r["population"] for r in rows)
    log.info("parsed %d village panchayats across %d unions; total pop %s",
             len(rows), len({r["block"] for r in rows}), f"{grand:,}")
    n = write_csv(rows)
    log.info("wrote %d rows -> %s", n, CSV_PATH)

    result = geocode_and_adopt(rows)
    log.info("matched=%d created=%d skipped=%d unresolved=%d",
             result["matched"], result["created"], result["skipped"],
             len(result["unresolved"]))
    for name, why in result["unresolved"].items():
        log.warning("UNRESOLVED %-24s %s", name, why)
    if args.strict and result["unresolved"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
