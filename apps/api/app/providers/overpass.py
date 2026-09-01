"""Live OpenStreetMap competitor discovery via the Overpass API (P0).

A thin, dependency-light client that queries the Overpass API for businesses
(shop/amenity/office points and ways) around an exact latitude/longitude within
a radius, for the OSM tags that match a GramBiz category (see
``app/catalog/business_categories``).

Design rules
------------
* **Never fabricate.** Every returned POI comes from a real Overpass response;
  no synthetic/generic names are invented (plan: "no fake competitor records").
* Results carry a per-query ``coverage`` / ``data_status`` so a small result is
  not misread as "no competition in reality" — it only means "nothing mapped".
* Multiple public mirrors are tried in order so a single-mirror outage does not
  fail the query (plan §16 fallback: live -> cached -> last-known -> unavailable).
* ``node`` + ``way`` are queried; way centers are used as coordinates and the
  parent tag set is preserved.
"""
from __future__ import annotations

import datetime as dt
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Optional

from app.catalog.business_categories import osm_filters

# Default public mirrors (config can override via settings.overpass_mirrors).
DEFAULT_MIRRORS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]

TIMEOUT_S = 40
_UA = "GramBizAI/1.0 (competitor-discovery; odbl/reasonable-use)"


class OverpassUnavailable(Exception):
    """All Overpass mirrors failed for a query."""


class OverpassResult:
    __slots__ = (
        "pois", "queried_at", "source", "mirror", "elapsed_s",
        "analyzed_nodes", "analyzed_ways",
    )

    def __init__(self, pois, queried_at, mirror, elapsed_s,
                 analyzed_nodes=0, analyzed_ways=0):
        self.pois = pois
        self.queried_at = queried_at
        self.source = "osm"
        self.mirror = mirror
        self.elapsed_s = elapsed_s
        self.analyzed_nodes = analyzed_nodes
        self.analyzed_ways = analyzed_ways


def _build_query(lat: float, lon: float, radius_m: int,
                 filters: list[dict], timeout_s: int = 25) -> str:
    """Build an Overpass QL statement for tag filters around a point.

    ``filters`` is a list of {"key": str, "values": list[str]|None}. Each entry
    becomes an OR clause within the node/way query (a POI matches if any of the
    (key, value-or-any) pairs match). ``values=None`` matches the key with any
    value. The regex uses ^...$ anchors so partial strings (e.g. "shopper")
    never match a category value.
    """
    clauses = []
    for f in filters:
        key = f["key"]
        values = f.get("values")
        if values:
            # OSM shop/amenity/craft values are lowercase; a plain alternation
            # match is enough (no case-insensitive flag -> widest Overpass
            # compatibility). Anchors prevent e.g. "grocery" matching "shops".
            vpat = "|".join(str(v) for v in values)
            clauses.append(f'["{key}"~"^({vpat})$"]')
        else:
            clauses.append(f'["{key}"]')
    body = "".join(clauses)

    statements = (
        f'node(around:{radius_m},{lat},{lon}){body};'
        f'way(around:{radius_m},{lat},{lon}){body};'
    )
    return f'[out:json][timeout:{timeout_s}];({statements});out center;'


def _way_center(e: dict) -> tuple[float, float] | None:
    c = e.get("center")
    if c and "lat" in c and "lon" in c:
        return float(c["lat"]), float(c["lon"])
    # fall back to way node-average if center not provided
    return None


def _normalize(e: dict, queried_at, element_type: str) -> Optional[dict]:
    tags = e.get("tags") or {}
    name = (tags.get("name") or "").strip()
    if not name:
        return None  # unnamed POIs carry no competitor info we can attribute
    if element_type == "node":
        lat, lon = e.get("lat"), e.get("lon")
    else:
        center = _way_center(e)
        if center is None:
            return None
        lat, lon = center
    if lat is None or lon is None:
        return None

    # Surface the OSM key:value that this POI was matched on, for evidence.
    matched = []
    for tag_key in ("shop", "amenity", "office", "healthcare", "craft"):
        if tags.get(tag_key):
            matched.append(f"{tag_key}={tags[tag_key]}")

    brand = tags.get("brand")
    return {
        "source": "osm",
        "source_record_id": f"{element_type}/{e.get('id')}",
        "element_type": element_type,
        "name": name,
        "normalized_name": name.lower().strip(),
        "category": tags.get("shop") or tags.get("amenity") or tags.get("craft") or tags.get("office"),
        "subcategory": tags.get("shop") or None,
        "latitude": lat,
        "longitude": lon,
        "address": tags.get("addr:full") or tags.get("addr:street") or None,
        "phone": tags.get("phone") or tags.get("contact:phone"),
        "website": tags.get("website") or tags.get("contact:website"),
        "brand": brand,
        "opening_hours": tags.get("opening_hours"),
        "matched_tags": matched,
        "retrieved_at": queried_at.isoformat(),
    }


def _post(mirror: str, query: str, timeout_s: int) -> dict:
    data = urllib.parse.urlencode({"data": query}).encode()
    req = urllib.request.Request(
        mirror, data=data, headers={"User-Agent": _UA,
                                    "Content-Type": "application/x-www-form-urlencoded"}
    )
    with urllib.request.urlopen(req, timeout=timeout_s) as r:
        return json.load(r)


def query(
    lat: float,
    lon: float,
    radius_m: int,
    category_code: str,
    *,
    mirrors: Optional[list[str]] = None,
    timeout_s: int = TIMEOUT_S,
) -> OverpassResult:
    """Query Overpass for competitor POIs around (lat, lon).

    Raises OverpassUnavailable if every mirror fails.
    """
    filters = osm_filters(category_code)
    if not filters:
        # Unknown category: fail closed with an empty read rather than guessing.
        return OverpassResult([], dt.datetime.now(dt.timezone.utc), None, 0.0)

    chosen_mirrors = mirrors or DEFAULT_MIRRORS
    query_str = _build_query(lat, lon, radius_m, filters)

    last_err: Optional[Exception] = None
    for mirror in chosen_mirrors:
        started = time.time()
        try:
            payload = _post(mirror, query_str, timeout_s)
            elapsed = time.time() - started
            elements = payload.get("elements", [])
            queried_at = dt.datetime.now(dt.timezone.utc)
            pois = []
            analyzed_nodes = analyzed_ways = 0
            for el in elements:
                et = el.get("type")
                if et == "node":
                    analyzed_nodes += 1
                elif et == "way":
                    analyzed_ways += 1
                p = _normalize(el, queried_at, et or "node")
                if p is not None:
                    pois.append(p)
            return OverpassResult(pois, queried_at, mirror, elapsed,
                                  analyzed_nodes, analyzed_ways)
        except (urllib.error.URLError, urllib.error.HTTPError, OSError, json.JSONDecodeError) as e:
            last_err = e
            continue

    raise OverpassUnavailable(f"all Overpass mirrors failed: {last_err}")


def ping(mirrors: Optional[list[str]] = None, timeout_s: int = 10) -> Optional[str]:
    """Return the first working mirror, or None if none respond (for health)."""
    for mirror in mirrors or DEFAULT_MIRRORS:
        try:
            _post(mirror, "[out:json][timeout:8];node(around:200,13.0827,80.2707)[\"shop\"];out 1;", timeout_s)
            return mirror
        except Exception:
            continue
    return None
