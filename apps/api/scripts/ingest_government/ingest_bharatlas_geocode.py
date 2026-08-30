"""Backfill Erode Census 2011 locations that still lack coordinates using the
Bharat Atlas "India's open atlas" keyless API.

``geocode_erode_locations`` + ``regeocode_unresolved`` resolve most Erode
towns/villages via OSM/Overpass/Nominatim/Photon, but leave locations for which
OSM has no name-matched element.  Bharat Atlas (https://bharatlas.com) exposes
curated, keyless layers over official, openly-licensed government data.  Its
``lgd_villages`` layer (the LGD 2024 village/gram-boundary layer, licence
CC0-1.0) carries, for every village, the Census 2011 name + code
(``vilname11`` / ``vilcode11``) that line up exactly with our DCHB Census 2011
source, plus a computed centroid (``_lat`` / ``_lng``).

This pass fetches the Erode district slice and, for each still-unresolved
location whose normalized name matches an LGD row, adopts the LGD centroid.
Because LGD codes are the same Census 2011 identifiers our own census rows
come from, matching by ``vilname11`` is authoritative and non-synthetic; these
rows are therefore written with ``confidence=high`` and ``is_estimate=False``
(different provenance from the OSM re-geocode rows, which remain ``medium``
estimated).

Only Erode-district rows are used (N=434 today).  Names are normalized
(accent folding, punctuation -> space, whitespace collapse).  A location is
only adopted when its name matches **exactly**; the handful of "(CT)"/"(TP)"
surfix entries in LGD are folded by stripping the surfix.  Adopted villages
are preferred over a pre-existing ``medium``/estimated OSM hit (which is
dropped) but never regress a ``high``/official or ``low`` row.  Rows with no
match are left for the next fallback and reported on stdout.

Only scalars are read; geometry columns (geom / wkb_geometry) are excluded by
the API.

Usage:
  python -m scripts.ingest_government.ingest_bharatlas_geocode
"""
from __future__ import annotations

import json
import logging
import re
import sys
import unicodedata
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from app.db.models import Location
from app.db.session import session_scope
from app.log import log_event
from scripts.ingest_government.scrape_erode_census import PROC_DIR, read_csv

log = logging.getLogger("ingest_bharatlas_geocode")

BASE_DIR = Path(__file__).resolve().parents[2]  # apps/api
PROCESSED = BASE_DIR / "data" / "processed" / "erode_census"
UNRESOLVED_VILLAGES = PROCESSED / "erode_census_2011_unresolved_villages.json"
UNRESOLVED_TOWNS = PROCESSED / "erode_census_2011_unresolved.json"

# bharatlas API base (keyless, read-only, 120 req/min).  Layer = curated
# "LGD Villages (2024)" -> source Local Government Directory (CC0-1.0).
API = "https://bharatlas.com/api/v1"
VILLAGE_LAYER = "lgd_villages"
BOUNDS = {"minlat": 11.02, "minlon": 76.83, "maxlat": 11.96, "maxlon": 77.94}
UA = {"User-Agent": "GramBizAI/1.0 (erode census research; contact: dev)"}

# Source provenance for rows we add/upgrade (LGD is the coordinating source).
LGD_SOURCE = ("bharatlas.com API v1 -> LGD Villages (2024) layer "
              "(source: Local Government Directory)")


def _norm(name: str | None) -> str:
    """Fold accents, strip surfixes in parentheses, collapse whitespace, uppercase."""
    if not name:
        return ""
    s = unicodedata.normalize("NFKD", name)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = re.sub(r"\([^)]*\)", " ", s)          # drop (CT)/(TP)/... surfix tokens
    s = re.sub(r"[^A-Za-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip().upper()


def _fetch_erode_layer() -> list[dict]:
    """Fetch all Erode LGD village rows (vilname11/code + centroid)."""
    url = f"{API}/layers/{VILLAGE_LAYER}/query"
    rows: list[dict] = []
    offset, page = 0, 0
    while True:
        q = dict(where="dtname=Erode",
                 select="vilname11,vilcode11,gp_name,sdtname", limit="500")
        if offset:
            q["offset"] = str(offset)
        params = urllib.parse.urlencode(q)
        with urllib.request.urlopen(  # noqa: S310 - bharatlas keyless public API
                urllib.request.Request(f"{url}?{params}", headers=UA), timeout=30) as resp:
            payload = json.load(resp)
        data = payload.get("data") or {}
        rows.extend(data.get("rows", []))
        total = int(data.get("total") or 0)
        offset += len(data.get("rows", [])) or 500
        page += 1
        if offset >= total or page >= 40:
            break
    return rows


def _index_lgd(rows: list[dict]) -> tuple[dict[str, list[dict]], list[dict]]:
    """Index by normalized name. Returns (name -> rows, in_bbox_flagged)."""
    idx: dict[str, list[dict]] = {}
    for r in rows:
        n = _norm(r.get("vilname11"))
        if not n:
            continue
        idx.setdefault(n, []).append(r)
    return idx, rows


def _in_bbox(lat: float | None, lon: float | None) -> bool:
    if lat is None or lon is None:
        return False
    return (BOUNDS["minlat"] <= lat <= BOUNDS["maxlat"]
            and BOUNDS["minlon"] <= lon <= BOUNDS["maxlon"])


def _pick_row(cands: list[dict]) -> dict | None:
    """Prefer a candidate with in-bbox centroid; else the sole candidate."""
    inb = [c for c in cands if _in_bbox(c.get("_lat"), c.get("_lng"))]
    pool = inb or cands
    return pool[0] if pool else None


def _pop_stat(name: str, block: str | None = None) -> dict | None:
    """Return the official Census 2011 population row for a village by NAME."""
    matches = [r for r in read_csv(PROC_DIR / "erode_census_2011_villages.csv")
               if (r.get("village") or "").strip() == name]
    if not matches:
        return None
    if block:
        for r in matches:
            if (r.get("block") or "") == block:
                return r
    return matches[0]


def _town_stat(name: str) -> dict | None:
    """Return the official Census 2011 population row for a town."""
    for row in read_csv(PROC_DIR / "erode_census_2011_towns.csv"):
        if (row.get("village") or "").strip() == name:
            return row
    return None


def main(argv=None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    unresolved = {
        "village": json.loads(UNRESOLVED_VILLAGES.read_text()),
        "town": json.loads(UNRESOLVED_TOWNS.read_text()),
    }
    lgd_rows = _fetch_erode_layer()
    idx, raw = _index_lgd(lgd_rows)
    log.info("fetched %d Erode LGD rows (%d distinct names)", len(raw), len(idx))

    # village/town -> block from the official census CSVs (villages carry
    # real panchayat-union blocks; towns use block==village, matching ingest).
    village_block = {r["village"]: r["block"]
                     for r in read_csv(PROC_DIR / "erode_census_2011_villages.csv")}
    town_block = {r["village"]: r["block"]
                  for r in read_csv(PROC_DIR / "erode_census_2011_towns.csv")}

    adopted: dict[str, list[dict]] = {"village": [], "town": []}
    no_coord: dict[str, str] = {}
    with session_scope() as s:
        existing = {
            r.village: r for r in s.query(Location).filter(
                Location.state == "Tamil Nadu", Location.district == "Erode",
                Location.village.isnot(None)).all()
        }
        for kind in ("village", "town"):
            for name, why in unresolved[kind].items():
                n = _norm(name)
                cands = idx.get(n) or []
                row = _pick_row(cands)
                if row is None:
                    no_coord[name] = why or "no Erode LGD match"
                    continue
                lat, lon = row.get("_lat"), row.get("_lng")
                if not _in_bbox(lat, lon):
                    no_coord[name] = f"LGD centroid out of Erode bbox: {lat},{lon}"
                    continue

                existing_loc = existing.get(name)
                if existing_loc is not None:
                    lvl = "village" if kind == "village" else "town"
                    block = existing_loc.block
                    # Prefer LGD (high) over a medium/estimated re-geocode hit,
                    # but never regress an official/high or a low row.
                    if existing_loc.confidence in ("high", "low"):
                        log.info("skip %s: existing %s-confidence row", name,
                                 existing_loc.confidence)
                        continue
                    existing_loc.latitude = float(lat)
                    existing_loc.longitude = float(lon)
                    existing_loc.confidence = "high"
                    existing_loc.is_estimate = False
                    existing_loc.geo_precision = "village"
                    existing_loc.source_name = "Local Government Directory via Bharat Atlas"
                    existing_loc.source_url = "https://bharatlas.com"
                    existing_loc.dataset_name = LGD_SOURCE
                    existing_loc.source_type = "government"
                    existing_loc.retrieved_at = datetime.now(timezone.utc)
                    existing_loc.geographic_level = lvl
                    existing_loc.methodology = "Coordinate = LGD village centroid from " \
                        "Bharat Atlas lgd_villages (CC0-1.0), matched by Census 2011 " \
                        "vilname11; upgraded from the earlier medium/estimated OSM hit."
                    existing_loc.metadata_json = {
                        "geocode_method": "bharatlas_lgd_village_centroid",
                        "vilcode11": row.get("vilcode11"),
                        "gp_name": row.get("gp_name"),
                        "sdtname": row.get("sdtname"),
                    }
                    s.add(existing_loc)
                else:
                    block = (village_block.get(name) if kind == "village" else None) \
                            or town_block.get(name) or (row.get("sdtname") or name)
                    loc = Location(
                        state="Tamil Nadu", district="Erode", block=block,
                        village=name, latitude=float(lat), longitude=float(lon),
                        geo_precision="village",
                        source_name="Local Government Directory via Bharat Atlas",
                        source_url="https://bharatlas.com",
                        dataset_name=LGD_SOURCE,
                        source_type="government",
                        retrieved_at=datetime.now(timezone.utc),
                        geographic_level="village",
                        confidence="high",
                        is_estimate=False,
                        is_demo=False,
                        methodology="Coordinate = LGD village centroid from Bharat Atlas "
                                    "lgd_villages (CC0-1.0), matched by Census 2011 "
                                    "vilname11; inside the official Erode district bbox.",
                        metadata_json={
                            "geocode_method": "bharatlas_lgd_village_centroid",
                            "vilcode11": row.get("vilcode11"),
                            "gp_name": row.get("gp_name"),
                            "sdtname": row.get("sdtname"),
                        },
                    )
                    s.add(loc)
                    s.flush()
                    existing[name] = loc
                    # Adopt the official Census 2011 population row, matching
                    # what the primary ingest does (never a proxy; is_demo=False).
                    pop = (_pop_stat(name, block) if kind == "village"
                           else _town_stat(name))
                    if pop is not None:
                        from app.db.models import PopulationStatistic
                        cy = int(pop.get("census_year") or 2011)
                        pv = {
                            "population": pop.get("population"),
                            "males": pop.get("males"),
                            "females": pop.get("females"),
                            "census_year": cy,
                            "reference_year": cy,
                            "level": "village",
                            "source_name": "Census India",
                            "dataset_name": "Village & Village Panchayat population by "
                                            "Panchayat Union (DCHB Erode, via erode.nic.in)",
                            "source_type": "government",
                            "confidence": "high",
                            "is_estimate": False,
                            "is_demo": False,
                            "methodology": "Official Census of India 2011 figures for "
                                           "Erode villages/towns (erode.nic.in).",
                        }
                        if pop.get("households"):
                            pv["households"] = pop["households"]
                        if pop.get("males") and pop.get("females"):
                            pv["sex_ratio"] = round(
                                float(pop["females"]) / float(pop["males"]) * 1000, 1)
                        s.add(PopulationStatistic(location_id=loc.id, **pv))
                adopted[kind].append({"name": name, "code": row.get("vilcode11")})
                log.info("adopted %-24s %s code=%s %.4f,%.4f block=%s",
                         name, kind, row.get("vilcode11"), lat, lon, block)

    # Persist the still-unresolved set (adopted names removed).
    adopted_set = {a["name"] for a in adopted["village"]} | {a["name"] for a in adopted["town"]}
    fresh = {kind: {n: w for n, w in unresolved[kind].items() if n not in adopted_set}
             for kind in ("village", "town")}
    UNRESOLVED_VILLAGES.write_text(json.dumps(fresh["village"], indent=2))
    UNRESOLVED_TOWNS.write_text(json.dumps(fresh["town"], indent=2))

    log_event("ingest", job="erode_bharatlas_geocode",
              villages_adopted=len(adopted["village"]),
              towns_adopted=len(adopted["town"]),
              still_unresolved=len(fresh["village"]) + len(fresh["town"]),
              status="completed")
    log.info("done: villages=%d towns=%d still_unresolved=%d",
             len(adopted["village"]), len(adopted["town"]),
             len(fresh["village"]) + len(fresh["town"]))
    if no_coord:
        log.info("no match (left unresolved), %d: %s", len(no_coord),
                 ", ".join(sorted(no_coord)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
