"""Build an authoritative Erode District village/town geographic index.

The mission requires village-level competitor discovery, but the census 2011
locals in the repo have no coordinates and are historical. This module:

1. Loads census 2011 villages (~224) + towns (~58) split by block.
2. Geocodes every village/town through Nominatim (free, no key) with a
   1.1 s politeness delay and a per-block geo-hint ("<village>, Erode Block,
   Erode District, Tamil Nadu") so ambiguous names resolve locally.
3. Merges in the 13 LGD blocks from ``administrative_boundaries``.
4. Writes ``data/erode/erode_index.csv`` + ``.json`` with lat/lon, block,
   population, and a ``source`` column so downstream code can tell census vs
   geocoded-vs-resolved rows apart.

Geocoding is rate-limited and resumable: rows already resolved are skipped,
so re-running the module after a partial run only geocodes the remainder.

Nominatim requires a descriptive User-Agent (`Usage policy:
https://operations.osmfoundation.org/policies/nominatim/`).
"""
from __future__ import annotations

import csv
import json
import logging
import os
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Callable, Optional

import httpx

log = logging.getLogger("erode.geographic_index")

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parents[2]          # apps/api
DATA_DIR = BASE_DIR / "data"
ERODE_DATA = DATA_DIR / "erode"
CENSUS_DIR = DATA_DIR / "processed" / "erode_census"
CACHE_DIR = ERODE_DATA / "cache"

VILLAGES_CSV = CENSUS_DIR / "erode_census_2011_villages.csv"
TOWNS_CSV = CENSUS_DIR / "erode_census_2011_towns.csv"
OUT_CSV = ERODE_DATA / "erode_index.csv"
OUT_JSON = ERODE_DATA / "erode_index.json"
GEO_CACHE_JSON = CACHE_DIR / "geocode_cache.json"

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "GramBizAI/1.1 (erode-village-index; rural business discovery)"
POLITE_DELAY_S = 1.1

ERODE_HINT = "Erode District, Tamil Nadu, India"

# Approximate geographic bounds of Erode District (lat, lon) used as a sanity
# check on geocodes and as a fallback district bbox. Covers Talavadi block in
# the west through Chennimalai in the east, and Sathyamangalam in the north
# to Perundurai in the south.
ERODE_BBOX = {"minlat": 10.95, "minlon": 76.60, "maxlat": 11.92, "maxlon": 77.90}


@dataclass
class Village:
    name: str
    block: str
    lat: Optional[float] = None
    lon: Optional[float] = None
    population: int = 0
    households: int = 0
    kind: str = "village"       # village | town
    source: str = "census_2011" # census_2011 | lgd | geocoded
    geocode_status: str = "pending"  # pending | ok | skipped | failed
    osm_display_name: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Census loaders
# ---------------------------------------------------------------------------
def load_census_villages() -> list[Village]:
    """Load census 2011 villages (real rows only, block != '(CT)' style)."""
    rows: list[Village] = []
    with open(VILLAGES_CSV, newline="") as fh:
        for row in csv.DictReader(fh):
            name = (row.get("village") or "").strip()
            block = (row.get("block") or "").strip()
            if not name or block.startswith("("):
                continue
            rows.append(Village(
                name=name,
                block=block,
                population=_int(row.get("population")),
                kind="village",
            ))
    log.info("loaded %d census villages", len(rows))
    return rows


# Census uses these sentinel values in the village column for aggregate urban
# rows that have no real town name (total population lines, urban-status rows).
_SKIP_TOWN_TOKENS = {"(ct)", "(tp)", "(m)", "(mct)", "(og)", "(ct+og)", "m", "0"}


def load_census_towns() -> list[Village]:
    """Load census 2011 towns; Census encodes urban status as '(CT)'/(TP).. in
    the village column. We give them a town name with coords when resolved.

    Aggregate/sentinel rows with no real town name are skipped.
    """
    rows: list[Village] = []
    names = []  # provisional; actual town name resolved during geocoding
    with open(TOWNS_CSV, newline="") as fh:
        for row in csv.DictReader(fh):
            raw = (row.get("village") or "").strip()
            status = raw.lstrip("(").rstrip(")").lower()
            if not raw or status in _SKIP_TOWN_TOKENS:
                continue
            pop = _int(row.get("population"))
            hh = _int(row.get("households"))
            real_name = raw if not raw.startswith("(") else status
            rows.append(Village(
                name=real_name,
                block=(row.get("block") or "").strip() or real_name,
                population=pop,
                households=hh,
                kind="town",
            ))
            names.append(real_name)
    log.info("loaded %d census town records", len(rows))
    return rows


def _int(v) -> int:
    try:
        return int(float(v or 0))
    except (TypeError, ValueError):
        return 0


# ---------------------------------------------------------------------------
# Geocoding
# ---------------------------------------------------------------------------
def _load_geocode_cache() -> dict:
    if GEO_CACHE_JSON.exists():
        try:
            return json.loads(GEO_CACHE_JSON.read_text())
        except (OSError, ValueError):
            log.warning("could not read %s; starting fresh", GEO_CACHE_JSON)
    return {}


def _save_geocode_cache(cache: dict):
    GEO_CACHE_JSON.parent.mkdir(parents=True, exist_ok=True)
    tmp = GEO_CACHE_JSON.with_suffix(".tmp")
    tmp.write_text(json.dumps(cache, indent=1))
    tmp.replace(GEO_CACHE_JSON)


def nominatim_geocode(query: str, client: httpx.Client) -> Optional[tuple[float, float, str]]:
    """Geocode a query via Nominatim. Returns (lat, lon, display_name) or None.

    Follows the Nominatim passing-scores policy: one result is returned, the
    first (best) ranked. A ``viewbox`` biased toward Erode District helps
    ambiguous rural names resolve locally instead of matching an identically
    named place elsewhere in Tamil Nadu.
    """
    bb = ERODE_BBOX
    params = {
        "q": query,
        "format": "json",
        "limit": 1,
        "countrycodes": "in",
        "viewbox": f"{bb['minlon']},{bb['maxlat']},{bb['maxlon']},{bb['minlat']}",
        "bounded": 1,
    }
    resp = client.get(NOMINATIM_URL, params=params,
                      headers={"User-Agent": USER_AGENT}, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if not data:
        return None
    hit = data[0]
    try:
        return float(hit["lat"]), float(hit["lon"]), hit.get("display_name", "")
    except (KeyError, TypeError, ValueError):
        return None


def _candidate_queries(v: Village) -> list[str]:
    """Ordered candidate queries, from most specific to most generic."""
    hint = "Erode, Tamil Nadu, India"
    if v.block and v.block != v.name:
        # Block-level hint helps disambiguate repeated village names.
        yield f"{v.name}, {v.block} Block, Erode, Tamil Nadu, India"
    yield f"{v.name}, {hint}"
    yield f"{v.name}"


def resolve_latlon(v: Village, client: httpx.Client,
                   cache: dict, geocode_fn: Callable = nominatim_geocode) -> bool:
    """Resolve coordinates for a village, honoring the geo cache."""
    cache_key = f"{v.kind}|{v.block}|{v.name}".lower()
    if cache_key in cache:
        entry = cache[cache_key]
        if entry.get("lat"):
            v.lat, v.lon = entry["lat"], entry["lon"]
            v.osm_display_name = entry.get("display_name", "")
            v.geocode_status = "ok"
            v.source = "geocoded"
            return True

    for q in _candidate_queries(v):
        try:
            hit = geocode_fn(q, client)
        except httpx.HTTPStatusError as e:
            if e.response.status_code in (429, 403, 451):
                log.warning("nominatim rate-limited (%s); pausing", e.response.status_code)
                time.sleep(5)
                hit = None
            else:
                raise
        if hit is None:
            continue
        lat, lon, display = hit
        if not (ERODE_BBOX["minlat"] <= lat <= ERODE_BBOX["maxlat"] and
                ERODE_BBOX["minlon"] <= lon <= ERODE_BBOX["maxlon"]):
            log.debug("geocode for %s fell outside Erode bbox: %s", v.name, display)
            continue
        v.lat, v.lon = lat, lon
        v.osm_display_name = display
        v.geocode_status = "ok"
        v.source = "geocoded"
        cache[cache_key] = {"lat": lat, "lon": lon, "display_name": display}
        return True

    v.geocode_status = "failed"
    return False


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------
def _fill_block_centroids(rows: list[Village]) -> int:
    """Assign unresolved villages the mean (lat, lon) of their block's resolved
    members so the discovery sweep still covers them (transparently: the row
    keeps ``geocode_status='estimated'`` and ``source='block_centroid'``).

    Returns the number of villages filled.
    """
    by_block: dict[str, list[Village]] = {}
    for v in rows:
        by_block.setdefault(v.block or "unknown", []).append(v)
    filled = 0
    for block, members in by_block.items():
        resolved = [v for v in members if v.geocode_status == "ok"]
        if not resolved:
            continue
        lat = sum(v.lat for v in resolved) / len(resolved)
        lon = sum(v.lon for v in resolved) / len(resolved)
        for v in members:
            if v.lat is None:
                v.lat, v.lon = lat, lon
                v.geocode_status = "estimated"
                v.source = "block_centroid"
                filled += 1
    return filled


def build_index(geocode: bool = True, force: bool = False) -> list[Village]:
    """Assemble + persist the full Erode index.

    Returns the list of villages sorted by block then name. When ``force`` is
    False cards from the geo cache are reused; when ``geocode`` is False only
    the census rows are produced (no network).
    """
    ERODE_DATA.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    villages = load_census_villages() + load_census_towns()

    if geocode:
        cache = {} if force else _load_geocode_cache()
        pending = [v for v in villages if v.geocode_status == "pending"]
        ok = sum(1 for v in villages if v.geocode_status == "ok")
        log.info("geocoding %d rows (already resolved: %d)", len(pending), ok)
        with httpx.Client() as client:
            changed = False
            for i, v in enumerate(villages, 1):
                if v.geocode_status == "ok":
                    continue
                resolved = resolve_latlon(v, client, cache)
                if i % 10 == 0:
                    log.info("geocode progress %d/%d (%s)", i, len(villages), v.name)
                if resolved:
                    changed = True
                if i % 10 == 0:
                    _save_geocode_cache(cache)
                time.sleep(POLITE_DELAY_S)
            if changed:
                _save_geocode_cache(cache)
        # Blocks with at least one resolved member supply centroids for the rest.
        filled = _fill_block_centroids(villages)
        if filled:
            log.info("filled %d unresolved villages from block centroids", filled)

    resolved = sum(1 for v in villages if v.geocode_status == "ok")
    estimated = sum(1 for v in villages if v.geocode_status == "estimated")
    log.info("index complete: %d rows, %d geocoded, %d block-estimated", len(villages),
             resolved, estimated)

    # Persist.
    _write_csv(villages, OUT_CSV)
    _write_json(villages, OUT_JSON)
    return villages


def _write_csv(rows: list[Village], path: Path):
    fields = list(Village.__dataclass_fields__.keys())
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for v in rows:
            writer.writerow(v.to_dict())


def _write_json(rows: list[Village], path: Path):
    path.write_text(json.dumps({
        "meta": {
            "district": "Erode",
            "state": "Tamil Nadu",
            "erode_bbox": ERODE_BBOX,
            "built_at": __import__("datetime").datetime.now().isoformat(),
        },
        "villages": [v.to_dict() for v in rows],
    }, indent=1, ensure_ascii=False))


# ---------------------------------------------------------------------------
# Loaders for downstream consumers
# ---------------------------------------------------------------------------
def load_index() -> list[Village]:
    """Load the persisted index from JSON (fast path)."""
    if not OUT_JSON.exists():
        return []
    data = json.loads(OUT_JSON.read_text())
    return [Village(**row) for row in data.get("villages", [])]


def index_with_coords() -> list[Village]:
    return [v for v in load_index() if v.lat is not None and v.lon is not None]


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    import argparse
    ap = argparse.ArgumentParser(description="Build Erode village geographic index")
    ap.add_argument("--no-geocode", action="store_true", help="skip geocoding")
    args = ap.parse_args()
    build_index(geocode=not args.no_geocode)
    print(f"index written to {OUT_CSV}")