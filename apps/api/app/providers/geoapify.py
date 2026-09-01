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
# Only GramBiz categories with a faithful Geoapify equivalent are mapped; the
# rest intentionally map to empty (provider does not cover them).
GEOAPIFY_CATEGORIES: dict[str, list[str]] = {
    "grocery": ["commercial.supermarket", "commercial.convenience_store"],
    "restaurant": ["commercial.restaurant"],
    "tea_shop": ["commercial.cafe"],
    "bakery": ["commercial.bakery"],
    "meat_shop": ["commercial.meat_and_fish"],
    "dairy": ["commercial.dairy"],
    "clothing": ["commercial.clothing_store"],
    "footwear": ["commercial.shoes_store"],
    "electronics": ["commercial.electronics", "commercial.computer_store"],
    "mobile_shop": ["commercial.mobile_store"],
    "furniture": ["commercial.furniture_store"],
    "stationery": ["commercial.stationery_store", "commercial.books_stationery"],
    "pharmacy": ["health.pharmacy"],
    "clinic": ["health.clinic", "health.hospital"],
    "salon": ["commercial.beauty", "commercial.hairdresser"],
    "tailoring": ["commercial.alterations_and_tailor"],
    "hardware": ["commercial.hardware_and_building_materials"],
    "mechanic": ["commercial.repairing_servicing"],
    "car_service": ["commercial.repairing_servicing"],
    "fertilizer": ["commercial.agricultural_inputs"],
    "seed_shop": ["commercial.agricultural_inputs"],
    "animal_feed": ["commercial.agricultural_inputs"],
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
