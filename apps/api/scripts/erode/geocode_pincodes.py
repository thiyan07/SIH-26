"""Geocode Erode-district UDYAM pincodes to centroids and backfill coords.

The UDYAM unit list ships pincode-level granularity. Units are located at
their pincode centroid so ``nearby_msmes`` / ``relevant_msmes`` (pincode-scoped
aggregation, not point-radius competitors) work for the map and analysis.

Steps:
  1. Collect distinct 638xxx pincodes from ``udyam_units``.
  2. Geocode each pincode via Nominatim (Erode viewbox), caching to
     ``data/erode/cache/pincode_geocode_cache.json`` (resumable).
  3. Write ``data/raw/pincode_centroids.csv`` (pincode,latitude,longitude).
  4. Backfill ``udyam_units.latitude/longitude`` from the centroids.

Usage::

    python -m scripts.erode.geocode_pincodes
"""
from __future__ import annotations

import csv
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import httpx
from sqlalchemy import text

from scripts.erode.geographic_index import nominatim_geocode

log = logging.getLogger("geocode_pincodes")

ROOT = Path(__file__).resolve().parents[1] / ".."
DATA_DIR = ROOT / "data" / "erode"
CACHE_DIR = DATA_DIR / "cache"
CACHE = CACHE_DIR / "pincode_geocode_cache.json"
RAW_DIR = ROOT / "data" / "raw"
CENTROIDS_CSV = RAW_DIR / "pincode_centroids.csv"

ERODE_PREFIXES = ("638", "6384", "6385")


def _distinct_pincodes(engine) -> dict[str, int]:
    with engine.connect() as c:
        rows = c.execute(text(
            "SELECT pincode, count(*) n FROM udyam_units "
            "WHERE pincode IS NOT NULL AND pincode ~ '^638' "
            "GROUP BY pincode ORDER BY pincode")).fetchall()
    return {str(r[0]): int(r[1]) for r in rows}


def _load_cache() -> dict:
    if CACHE.exists():
        try:
            return json.loads(CACHE.read_text())
        except (OSError, ValueError):
            pass
    return {}


def _save_cache(cache: dict):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = CACHE.with_suffix(".tmp")
    tmp.write_text(json.dumps(cache, indent=1))
    tmp.replace(CACHE)


def geocode_pincodes(max_tries: int = 3, delay: float = 1.2) -> dict[str, dict]:
    from app.db.session import get_engine
    engine = get_engine()
    pins = _distinct_pincodes(engine)
    log.info("distinct Erode-series pincodes to geocode: %d", len(pins))
    cache = _load_cache()
    resolved = {}
    remaining = [p for p in pins if p not in cache]

    with httpx.Client(timeout=40) as client:
        for i, pin in enumerate(remaining, 1):
            hit = None
            for attempt in range(max_tries):
                try:
                    hit = nominatim_geocode(f"{pin}, India", client)
                    break
                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 429:
                        log.warning("nominatim 429 at pincode %s; sleeping 15s", pin)
                        time.sleep(15)
                    elif e.response.status_code >= 500:
                        log.warning("nominatim %d at pincode %s; sleeping 8s",
                                    e.response.status_code, pin)
                        time.sleep(8)
                    else:
                        log.warning("nominatim %d at pincode %s; skipping",
                                    e.response.status_code, pin)
                        break
                except httpx.RequestError as e:
                    log.warning("request error %s; retry %d/3", type(e).__name__, attempt + 1)
                    time.sleep(3)
            cache[pin] = ({"lat": hit[0], "lon": hit[1],
                           "osm_display_name": hit[2]}
                          if hit else {"lat": None, "lon": None})
            if hit:
                resolved[pin] = cache[pin]
            if i % 10 == 0:
                _save_cache(cache)
            time.sleep(delay)
    _save_cache(cache)
    log.info("resolved %d/%d pincodes", len(resolved), len(pins))
    return resolved


def _write_centroids(all_pins: dict[str, int], cache: dict) -> int:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    n = 0
    with CENTROIDS_CSV.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["pincode", "latitude", "longitude", "district", "state"])
        for pin, count in sorted(all_pins.items()):
            c = cache.get(pin) or {}
            if c.get("lat") is None:
                continue
            w.writerow([pin, c["lat"], c["lon"], "ERODE", "TAMIL NADU"])
            n += 1
    log.info("wrote %d centroids to %s", n, CENTROIDS_CSV)
    return n


def _backfill(engine) -> int:
    """Set udyam_units.latitude/longitude from the centroid CSV."""
    if not CENTROIDS_CSV.exists():
        log.warning("no centroids CSV at %s; nothing to backfill", CENTROIDS_CSV)
        return 0
    centroids = {}
    with CENTROIDS_CSV.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            try:
                pin = str(row["pincode"]).strip()
                lat = float(row["latitude"])
                lon = float(row["longitude"])
                centroids[pin] = (lat, lon)
            except (KeyError, ValueError, TypeError):
                continue
    updates = 0
    with engine.begin() as c:
        for pin, (lat, lon) in sorted(centroids.items()):
            res = c.execute(text(
                "UPDATE udyam_units SET latitude=:lat, longitude=:lon "
                "WHERE pincode=:pin AND latitude IS NULL AND longitude IS NULL"),
                {"lat": lat, "lon": lon, "pin": pin})
            updates += res.rowcount
    return updates


def main(argv=None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    from app.db.session import get_engine
    engine = get_engine()
    resolved = geocode_pincodes()
    pins = _distinct_pincodes(engine)
    cache = _load_cache()
    n_csv = _write_centroids(pins, cache)
    done = _backfill(engine)
    log.info("wrote %d centroid rows; backfilled %d udyam_units", n_csv, done)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())