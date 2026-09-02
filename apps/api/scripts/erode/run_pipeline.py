"""Orchestrates the Erode District bulk expansion pipeline.

Steps
-----
1. Build geographic index (geocode census villages/towns)  → scripts.erode.geographic_index
2. Bulk discovery (per-village Overpass queries)          → scripts.erode.discovery
3. Reports                                               → scripts.erode.coverage

Usage
-----
    python -m scripts.erode.run_pipeline --index
    python -m scripts.erode.run_pipeline --discovery --limit 5
    python -m scripts.erode.run_pipeline --all --limit 10
"""
from __future__ import annotations

import argparse
import json
import logging

log = logging.getLogger("erode.run_pipeline")


def run_index(no_geocode: bool = False):
    from scripts.erode.geographic_index import build_index
    villages = build_index(geocode=not no_geocode)
    ok = sum(1 for v in villages if v.geocode_status == "ok")
    print(json.dumps({"indexed": len(villages), "with_coords": ok}, indent=2))
    return villages


def run_discovery(limit=None, delay=1.5, no_overpass=False, force=False):
    from scripts.erode.discovery import run_erode_discovery
    print(json.dumps(run_erode_discovery(limit=limit, delay=delay,
                                         overpass=not no_overpass, force=force), indent=2))


def run_geoapify(limit=None, delay=0.5, force=False):
    from scripts.erode.geoapify_bulk import run_geoapify_sweep
    print(json.dumps(run_geoapify_sweep(limit=limit, delay=delay, force=force), indent=2))


def run_reports():
    from scripts.erode.coverage import write_reports
    out = write_reports()
    print(json.dumps({"reports": out}, indent=2, default=str)[:2000])


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", action="store_true", help="build geographic index")
    ap.add_argument("--no-geocode", action="store_true")
    ap.add_argument("--discovery", action="store_true", help="run bulk discovery")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--delay", type=float, default=1.5)
    ap.add_argument("--no-overpass", action="store_true")
    ap.add_argument("--geoapify", action="store_true", help="run Geoapify secondary sweep")
    ap.add_argument("--geoapify-delay", type=float, default=0.5)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--reports", action="store_true", help="write coverage reports")
    ap.add_argument("--all", action="store_true", help="index + discovery + reports")
    args = ap.parse_args()

    if args.all or args.index:
        run_index(no_geocode=args.no_geocode)
    if args.all or args.discovery:
        run_discovery(limit=args.limit, delay=args.delay,
                      no_overpass=args.no_overpass, force=args.force)
    if args.all or args.geoapify:
        run_geoapify(limit=args.limit, delay=args.geoapify_delay, force=args.force)
    if args.all or args.reports:
        run_reports()
    if not any([args.index, args.discovery, args.geoapify, args.reports, args.all]):
        ap.print_help()