"""Optional live competitor discovery via the Geoapify Places API (P0 multi-source).

A second, independent real-data provider for competitor discovery. It is
deliberately **optional**: it only runs when a ``geoapify`` API key is
configured in ``settings.data_provider_keys`` (a JSON object, e.g.
``{"geoapify": "YOUR_KEY"}``). With no key it is a no-op that raises
``GeoapifyUnavailable`` so the discovery ladder falls through to the reliable
Overpass / cache / DB tiers (plan §16). It never fabricates: every returned POI
comes from a real Geoapify response.

Geoapify does not tag rural India as finely as OSM, so many GramBiz categories
have no good Geoapify category token; for those we return an **honest empty**
result (``data_status``-safe) rather than guessing a category.
"""
from __future__ import annotations

import datetime as dt
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Optional

# Geoapify Places category tokens (https://apidocs.geoapify.com/docs/places/).
# v2 taxonomy tokens are hierarchical (group.subgroup); these were verified
# against the live API — unknown tokens return HTTP 400, not an empty list.
# Only GramBiz categories with a faithful Geoapify equivalent are mapped; the
# rest intentionally map to empty (provider does not cover them).
GEOAPIFY_CATEGORIES: dict[str, list[str]] = {
    "grocery": ["commercial.supermarket", "commercial.convenience", "commercial.department_store"],
    "restaurant": ["catering.restaurant", "catering.food_court"],
    "tea_shop": ["catering.cafe", "catering.cafe.coffee", "catering.cafe.tea"],
    "bakery": ["commercial.food_and_drink.bakery"],
    "meat_shop": ["commercial.food_and_drink.butcher"],
    "fish_shop": ["commercial.food_and_drink.seafood"],
    "dairy": ["commercial.food_and_drink.cheese_and_dairy"],
    "clothing": ["commercial.clothing", "commercial.clothing.clothes"],
    "footwear": ["commercial.clothing.shoes"],
    "electronics": ["commercial.elektronics"],
    "mobile_shop": ["commercial.elektronics"],
    "furniture": ["commercial.furniture_and_interior", "commercial.furniture_and_interior.lighting"],
    "stationery": ["commercial.stationery", "commercial.books"],
    "pharmacy": ["commercial.health_and_beauty.pharmacy", "commercial.chemist"],
    "clinic": ["healthcare.clinic_or_praxis", "healthcare.clinic_or_praxis.general"],
    "hospital": ["healthcare.hospital"],
    "dental_clinic": ["healthcare.dentist"],
    "optical_shop": ["commercial.health_and_beauty.optician"],
    "salon": ["service.beauty", "service.beauty.hairdresser"],
    "tailoring": ["service.tailor"],
    "laundry": ["service.cleaning.laundry", "service.cleaning.dry_cleaning"],
    "photography": ["service.photographer", "commercial.hobby.photo"],
    "travel_agency": ["service.travel_agency"],
    "finance": ["service.financial.bank", "service.financial.money_transfer"],
    "hardware": ["commercial.houseware_and_hardware.hardware_and_tools"],
    "building_materials": ["commercial.houseware_and_hardware.building_materials"],
    "mechanic": ["service.vehicle.repair", "service.vehicle.repair.car"],
    "car_service": ["service.vehicle.repair.car"],
    "welding": ["service.metal_construction", "service.blacksmith"],
    "fertilizer": ["commercial.agrarian"],
    "seed_shop": ["commercial.agrarian"],
    "agricultural_equipment": ["commercial.agrarian"],
    "animal_feed": ["commercial.pet", "commercial.agrarian"],
    "hotel": ["accommodation.hotel", "accommodation.guest_house"],
}

TIMEOUT_S = 20
_UA = "GramBizAI/1.0 (competitor-discovery; geoapify-terms)"
PLACES_URL = "https://api.geoapify.com/v2/places"


class GeoapifyUnavailable(Exception):
    """Geoapify is not configured or failed for this query. Callers fall back."""


def configured_keys(provider_keys: str) -> dict:
    """Parse the ``data_provider_keys`` config string (JSON object) safely."""
    if not provider_keys:
        return {}
    try:
        data = json.loads(provider_keys)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, ValueError):
        return {}


def api_key(settings) -> Optional[str]:
    """Return the Geoapify key from settings, or None if not configured."""
    keys = configured_keys(getattr(settings, "data_provider_keys", "") or "")
    key = keys.get("geoapify")
    return (key or "").strip() or None


def _build_url(lat: float, lon: float, radius_m: int, categories: list[str],
               key: str, limit: int = 50) -> str:
    params = {
        "categories": ",".join(categories),
        "filter": f"circle:{lon},{lat},{radius_m}",
        "limit": str(limit),
        "apiKey": key,
    }
    return f"{PLACES_URL}?{urllib.parse.urlencode(params)}"


class GeoapifyResult:
    __slots__ = ("pois", "queried_at", "source", "elapsed_s", "raw_features")

    def __init__(self, pois, queried_at, elapsed_s, raw_features=0):
        self.pois = pois
        self.queried_at = queried_at
        self.source = "geoapify"
        self.elapsed_s = elapsed_s
        self.raw_features = raw_features


def _normalize(feature: dict, queried_at) -> Optional[dict]:
    props = feature.get("properties") or {}
    name = (props.get("name") or "").strip()
    if not name:
        return None  # unnamed POIs carry no attributable competitor info
    lon = props.get("lon")
    lat = props.get("lat")
    if lon is None or lat is None:
        return None
    cats = props.get("categories") or []
    matched = [f"geoapify:{c}" for c in cats[:4]]
    return {
        "source": "geoapify",
        "source_record_id": f"geoapify/{props.get('place_id')}",
        "element_type": "point",
        "name": name,
        "normalized_name": name.lower().strip(),
        "category": cats[0] if cats else None,
        "subcategory": None,
        "latitude": float(lat),
        "longitude": float(lon),
        "address": props.get("address_line1") or props.get("formatted"),
        "phone": props.get("phone"),
        "website": props.get("website"),
        "brand": props.get("brand"),
        "opening_hours": None,
        "matched_tags": matched,
        "retrieved_at": queried_at.isoformat(),
    }


def query(lat: float, lon: float, radius_m: int, category_code: str,
          *, key: Optional[str] = None, timeout_s: int = TIMEOUT_S,
          provider_keys: str = "") -> GeoapifyResult:
    """Query Geoapify for competitor POIs around (lat, lon).

    Raises GeoapifyUnavailable when not configured / request fails. Returns an
    honest empty result when the category is not covered by this provider.
    """
    if key is None or not key:
        if provider_keys:
            k = configured_keys(provider_keys).get("geoapify")
            key = (k or "").strip() or None
    if key is None:
        raise GeoapifyUnavailable("Geoapify not configured (no geoapify key in data_provider_keys)")

    categories = GEOAPIFY_CATEGORIES.get(category_code)
    if not categories:
        # Category intentionally not covered by Geoapify -> honest empty read.
        return GeoapifyResult([], dt.datetime.now(dt.timezone.utc), 0.0, 0)

    url = _build_url(lat, lon, radius_m, categories, key)
    started = time.time()
    try:
        req = urllib.request.Request(url, headers={"User-Agent": _UA})
        with urllib.request.urlopen(req, timeout=timeout_s) as r:
            payload = json.load(r)
    except (urllib.error.URLError, urllib.error.HTTPError, OSError, json.JSONDecodeError) as e:
        raise GeoapifyUnavailable(f"Geoapify request failed: {e}") from e

    elapsed = time.time() - started
    queried_at = dt.datetime.now(dt.timezone.utc)
    features = payload.get("features", [])
    pois = []
    for feat in features:
        p = _normalize(feat, queried_at)
        if p is not None:
            pois.append(p)
    return GeoapifyResult(pois, queried_at, elapsed, raw_features=len(features))


def ping(key: Optional[str] = None, timeout_s: int = 8) -> bool:
    """Return True if Geoapify is reachable with the configured key (for health)."""
    if key is None or not key:
        return False
    try:
        url = _build_url(13.0827, 80.2707, 500, ["commercial.supermarket"], key, limit=1)
        req = urllib.request.Request(url, headers={"User-Agent": _UA})
        with urllib.request.urlopen(req, timeout=timeout_s) as r:
            r.read()
        return True
    except Exception:
        return False
