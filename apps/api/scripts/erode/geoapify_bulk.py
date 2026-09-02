"""Bulk secondary-source discovery via the Geoapify Places API.

The OSM Overpass sweep in ``discovery.py`` is the primary, but by itself racks
up most rural categories thinly. Geoapify is a genuinely independent provider
that covers many categories OSM under-samples in rural Tamil Nadu (salon,
laundry, printing, internet_centre, vegetable/fruit shops, ...). This module
queries Geoapify around every village center for those categories and hands the
normalized POIs to ``discovery.persist`` (which dedupes across sources by
normalized name + proximity, so a Geoapify hit never doubles-up an OSM one).

It is fully optional: if no Geoapify key is available the module is a no-op and
the pipeline still succeeds on the Overpass tier alone.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import dotenv

from scripts.erode.geographic_index import Village, index_with_coords

BASE_DIR = Path(__file__).resolve().parents[2]
dotenv.load_dotenv(BASE_DIR / ".env")

PLACES_URL = "https://api.geoapify.com/v2/places"
_UA = "GramBizAI/1.1 (erode bulk discovery; geoapify)" 
RADIUS_M = 2500  # ~ radius matching a village bbox sweep
LIMIT = 100

# Geoapify category token per GramBiz category (v2 taxonomy, valid 2026).
# These were verified against https://apidocs.geoapify.com/docs/places/ —
# unknown tokens return HTTP 400, so only valid tokens are used.
GEOAPIFY_CATEGORIES = {
    "grocery": ["commercial.supermarket", "commercial.convenience", "commercial.department_store"],
    "restaurant": ["catering.restaurant", "catering.food_court"],
    "fast_food": ["catering.fast_food"],
    "tea_shop": ["catering.cafe", "catering.cafe.tea", "catering.cafe.coffee"],
    "bakery": ["commercial.food_and_drink.bakery"],
    "sweet_shop": ["commercial.food_and_drink.confectionery", "catering.cafe.dessert"],
    "fish_shop": ["commercial.food_and_drink.seafood"],
    "vegetable_shop": ["commercial.food_and_drink.fruit_and_vegetable"],
    "fruit_shop": ["commercial.food_and_drink.fruit_and_vegetable"],
    "meat_shop": ["commercial.food_and_drink.butcher"],
    "dairy": ["commercial.food_and_drink.cheese_and_dairy"],
    "clothing": ["commercial.clothing", "commercial.clothing.clothes",
                 "commercial.clothing.men", "commercial.clothing.women", "commercial.clothing.kids"],
    "footwear": ["commercial.clothing.shoes"],
    "electronics": ["commercial.elektronics", "commercial.hobby.photo"],
    "mobile_shop": ["commercial.elektronics"],
    "home_appliances": ["commercial.furniture_and_interior", "commercial.elektronics"],
    "furniture": ["commercial.furniture_and_interior", "commercial.furniture_and_interior.kitchen",
                  "commercial.furniture_and_interior.bed", "commercial.furniture_and_interior.lighting"],
    "stationery": ["commercial.stationery", "commercial.books"],
    "printing": ["commercial.stationery", "service.photographer"],
    "internet_centre": ["commercial.elektronics", "commercial.newsagent"],
    "photography": ["service.photographer", "commercial.hobby.photo"],
    "travel_agency": ["service.travel_agency"],
    "finance": ["service.financial.bank", "service.financial.money_transfer",
                "service.financial.atm"],
    "salon": ["service.beauty", "service.beauty.hairdresser", "service.beauty.spa"],
    "laundry": ["service.cleaning.laundry", "service.cleaning.dry_cleaning"],
    "tailoring": ["service.tailor", "commercial.hobby.sewing_and_knitting"],
    "optical_shop": ["commercial.health_and_beauty.optician"],
    "pharmacy": ["commercial.health_and_beauty.pharmacy", "commercial.chemist"],
    "clinic": ["healthcare.clinic_or_praxis", "healthcare.clinic_or_praxis.general"],
    "hospital": ["healthcare.hospital"],
    "dental_clinic": ["healthcare.dentist"],
    "hardware": ["commercial.houseware_and_hardware.hardware_and_tools"],
    "building_materials": ["commercial.houseware_and_hardware.building_materials",
                           "commercial.houseware_and_hardware.building_materials.tiles",
                           "commercial.houseware_and_hardware.building_materials.paint"],
    "plywood": ["commercial.houseware_and_hardware.building_materials",
                "commercial.houseware_and_hardware.doityourself"],
    "mechanic": ["service.vehicle.repair", "service.vehicle.repair.car",
                 "service.vehicle.repair.motorcycle"],
    "car_service": ["service.vehicle.repair.car"],
    "welding": ["service.metal_construction", "service.blacksmith"],
    "fertilizer": ["commercial.agrarian"],
    "seed_shop": ["commercial.agrarian"],
    "agricultural_equipment": ["commercial.agrarian", "commercial.vehicle"],
    "tractor_dealer": ["commercial.vehicle"],
    "animal_feed": ["commercial.pet", "commercial.agrarian"],
    "hotel": ["accommodation.hotel", "accommodation.motel", "accommodation.guest_house"],
    "handicrafts": ["commercial.art", "commercial.gift_and_souvenir", "commercial.antiques"],
    "grocery_general": ["commercial.kiosk"],
}


def _key() -> Optional[str]:
    k = os.environ.get("GEOAPIFY_API_KEY", "").strip()
    return k or None


def configured() -> bool:
    return _key() is not None


# Geoapify token -> GramBiz category codes that use it (reverse lookup).
# A feature's ``properties.categories`` are reverse-classified through this.
_TOKEN_TO_CODES: dict[str, str] = {}
_ORDER: dict[str, int] = {}
for _code_i, (_code, _tokens) in enumerate(GEOAPIFY_CATEGORIES.items()):
    _ORDER[_code] = _code_i
    for _tok in _tokens:
        _TOKEN_TO_CODES.setdefault(_tok, _code)

ALL_GEOAPIFY_TOKENS: list[str] = sorted(_TOKEN_TO_CODES)


def _classify(cats: list[str]) -> Optional[str]:
    """Pick the best GramBiz category for a Geoapify feature's categories.

    Prefers the most specific (deepest) matching token; ties break toward the
    GramBiz category that appears earlier in GEOAPIFY_CATEGORIES.
    """
    if not cats:
        return None
    best: Optional[str] = None
    best_depth = -1
    best_order = 10**6
    for c in cats:
        code = _TOKEN_TO_CODES.get(c)
        if code is None:
            continue
        depth = c.count(".")
        order = _ORDER[code]
        if depth > best_depth or (depth == best_depth and order < best_order):
            best = code
            best_depth, best_order = depth, order
    return best


def _build_url(lat, lon, categories: list[str], key: str) -> str:
    params = {
        "categories": ",".join(categories),
        "filter": f"circle:{lon},{lat},{RADIUS_M}",
        "limit": str(LIMIT),
        "apiKey": key,
    }
    return f"{PLACES_URL}?{urllib.parse.urlencode(params)}"


def _normalize(feature: dict, category_code: str) -> Optional[dict]:
    props = feature.get("properties") or {}
    name = (props.get("name") or "").strip()
    if not name:
        return None
    lon, lat = props.get("lon"), props.get("lat")
    if lon is None or lat is None:
        return None
    cats = props.get("categories") or []
    return {
        "name": name,
        "category": category_code,
        "lat": float(lat),
        "lon": float(lon),
        "source": "geoapify",
        "source_id": f"geoapify/{props.get('place_id', '')}",
        "tags": {"categories": cats[:4]},
        "address": props.get("address_line1") or props.get("formatted"),
        "phone": props.get("phone"),
        "website": props.get("website"),
        "opening_hours": None,
        "brand": props.get("brand"),
        "confidence": 0.6,
        "completeness": 0.5,
        "verification": "UNVERIFIED",
    }


def query_village(v: Village, delay: float = 0.4) -> tuple[list[dict], list[str]]:
    """Query Geoapify for all covered categories around one village.

    Issues a single request with every valid category token merged, then
    reverse-classifies each feature from its own ``categories`` property.
    Returns (elements, errors).
    """
    if not configured():
        return [], []
    key = _key()
    elements: list[dict] = []
    errors: list[str] = []
    try:
        url = _build_url(v.lat, v.lon, ALL_GEOAPIFY_TOKENS, key)
        req = urllib.request.Request(url, headers={"User-Agent": _UA})
        with urllib.request.urlopen(req, timeout=25) as r:
            payload = json.load(r)
        for feat in payload.get("features", []):
            props = feat.get("properties") or {}
            code = _classify(props.get("categories") or [])
            if code is None:
                continue
            n = _normalize(feat, code)
            if n is not None:
                elements.append(n)
    except (urllib.error.URLError, urllib.error.HTTPError, OSError,
            json.JSONDecodeError) as e:
        code_ = getattr(e, "code", None)
        if code_ == 403 or code_ == 429:
            errors.append(f"geoapify {v.name} {code_}: {e}")
        else:
            errors.append(f"geoapify {code_} around {v.name}: {e}")
        return elements, errors
    if delay:
        time.sleep(delay)
    return elements, errors


def run_geoapify_sweep(limit: Optional[int] = None, delay: float = 0.5,
                       force: bool = False) -> dict:
    """Sweep Geoapify across the whole village index and persist results."""
    from scripts.erode.discovery import persist

    if not configured():
        return {"skipped": "no GEOAPIFY_API_KEY in .env"}
    villages = index_with_coords()

    from scripts.erode.discovery import _load_state, _save_state, _idx_key
    state = {} if force else _load_state()
    done = set(state.get("geoapify_done", []))
    total_found = 0
    total_ins = 0
    total_mat = 0
    errors = 0

    for i, v in enumerate(villages, 1):
        if limit and i > limit:
            break
        key_ = _idx_key(v)
        if key_ in done:
            continue
        elements, errs = query_village(v, delay=delay)
        ins, mat = 0, 0
        if elements:
            ins, mat = persist(elements)
        total_found += len(elements)
        total_ins += ins
        total_mat += mat
        errors += len(errs)
        done.add(key_)
        state["geoapify_done"] = sorted(done)
        state["geoapify_found"] = total_found
        if i % 25 == 0:
            _save_state(state)
            log_progress(i, v, total_found, ins, mat, errors)
        if delay:
            time.sleep(delay)
    _save_state(state)
    return {"villages": len(villages), "found": total_found, "inserted": total_ins,
            "matched": total_mat, "errors": errors}


def log_progress(i, v, found, ins, mat, errors):
    import logging
    logging.getLogger("erode.geoapify").info(
        "village %s (%s): found=%d inserted=%d matched=%d err=%d",
        v.name, i, found, ins, mat, errors)


if __name__ == "__main__":
    import argparse
    import logging
    logging.basicConfig(level=logging.INFO)
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--delay", type=float, default=0.5)
    args = ap.parse_args()
    print(json.dumps(run_geoapify_sweep(limit=args.limit, delay=args.delay), indent=2))