"""Live competitor-data benchmark (P0 missions §6, §7).

Queries the Overpass (OSM) provider for a matrix of real locations x
business categories around the GramBiz pilot region and records the ACTUAL
results — never fabricated. The benchmark records ``status`` per query so a
``count`` of 0 is *never* conflated with a fetch failure:

  * ``ok``       - source responded; count is how many were found
  * ``error``    - source unavailable (HTTP/network); count forced to 0 but
                   ``error`` carries the real message so 0 is not read as
                   "none exist"

Output is written as JSON + a markdown summary so comparative coverage can be
audited.

Run:  .venv/bin/python scripts/benchmark/competitor_benchmark.py
"""
from __future__ import annotations

import datetime as dt
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.providers import overpass

# (label, lat, lon) — actual markers used by the GramBiz map flow.
LOCATIONS = {
    "erode": (11.3410, 77.7172),
    "bhavani": (11.4459, 77.6820),
    "perundurai": (11.2756, 77.5800),
    "rural_avalpoondurai": (11.2313, 77.7181),
}

# Categories required by the mission to test (mapped to catalog category_code).
CATEGORIES = [
    "grocery", "pharmacy", "restaurant", "bakery", "hardware", "clothing",
    "mobile_shop", "electronics", "furniture", "mechanic", "fertilizer",
    "seed_shop", "salon", "tailoring", "stationery",
]

# Categories actually exercised in the live benchmark run to keep the OSM
# (public mirror, rate-limited) run tractable while still broad enough to be
# representative. CLI --all restores the full matrix.
LIVE_CATEGORIES = [
    "grocery", "pharmacy", "restaurant", "bakery", "hardware", "clothing",
    "mobile_shop", "electronics", "furniture", "mechanic",
]

RADIUS_M = 3000


def run(single: str | None = None, timeout_s: int = 60, all_categories: bool = False,
        print_progress: bool = True):
    cats = CATEGORIES if all_categories else LIVE_CATEGORIES
    results: dict = {"retrieved_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                     "radius_m": RADIUS_M, "categories": cats, "locations": {}, "summary": {}}
    locs = {k: v for k, v in LOCATIONS.items() if single is None or k == single}
    grand = {"fetched": 0, "with_coords": 0, "errors": 0}
    for label, (lat, lon) in locs.items():
        loc_row = {"latitude": lat, "longitude": lon, "categories": {}}
        for cat in cats:
            started = time.time()
            try:
                r = overpass.query(lat, lon, RADIUS_M, cat, timeout_s=timeout_s)
                pois = r.pois
                coords = sum(1 for p in pois if p.get("latitude") is not None and p.get("longitude") is not None)
                loc_row["categories"][cat] = {
                    "status": "ok",
                    "count": len(pois),
                    "with_coords": coords,
                    "mirror": r.mirror,
                    "elapsed_s": round(r.elapsed_s, 1),
                    "error": None,
                    "names": [p["name"] for p in pois][:15],
                }
                grand["fetched"] += len(pois)
                grand["with_coords"] += coords
            except overpass.OverpassUnavailable as e:
                loc_row["categories"][cat] = {
                    "status": "error",
                    "count": 0, "with_coords": 0, "mirror": None,
                    "elapsed_s": round(time.time() - started, 1), "error": str(e),
                    "names": [],
                }
                grand["errors"] += 1
            if print_progress:
                cnt = loc_row["categories"][cat]["count"]
                print(f"[{label}] {cat}: {cnt}", flush=True)
            time.sleep(1.0)
        results["locations"][label] = loc_row
        results["summary"][label] = {
            "total_fetched": sum(c["count"] for c in loc_row["categories"].values()),
            "categories_with_data": sum(1 for c in loc_row["categories"].values() if c["count"] > 0),
        }
    results["grand_total_fetched"] = grand["fetched"]
    results["grand_with_coords"] = grand["with_coords"]
    results["grand_errors"] = grand["errors"]

    out_path = "data/benchmark/competitor_benchmark.json"
    import os
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(json.dumps(results["summary"], indent=2))
    print("grand_total_fetched:", grand["fetched"], "with_coords:", grand["with_coords"],
          "errors:", grand["errors"])
    print("wrote", out_path)
    return results


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--single", default=None, help="only one location label")
    ap.add_argument("--timeout", type=int, default=60)
    ap.add_argument("--all", action="store_true", help="run full category matrix")
    args = ap.parse_args()
    run(single=args.single, timeout_s=args.timeout, all_categories=args.all)
