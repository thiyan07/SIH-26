"""Geocoding service for exact place / address search.

Finds the exact proposed shop location by human-readable query and returns
latitude/longitude plus a display name. Providers are resolved server-side so
no API keys ever reach the browser:

* ``nominatim`` (default) — free OpenStreetMap geocoder, no key required.
* ``photon``              — free Photon (OSM) geocoder, no key required.
* ``google``              — Google Geocoding API (requires ``GEOCODER_API_KEY``).

Deterministic: every provider maps into a single :class:`GeoPlace`. Response
mapping also keeps the raw provider payload so the frontend can show provenance.
"""
from __future__ import annotations

from typing import Any, Literal, Optional

import httpx
from pydantic import BaseModel

from app.config import settings

ProviderName = Literal["nominatim", "photon", "google"]

_DEFAULT_BASE_URLS: dict[ProviderName, str] = {
    "nominatim": "https://nominatim.openstreetmap.org",
    "photon": "https://photon.komoot.io",
    "google": "https://maps.googleapis.com/maps/api/geocode/json",
}


class GeoPlace(BaseModel):
    name: str
    display_name: str
    latitude: float
    longitude: float
    provider: str
    confidence: Optional[str] = None
    raw: Optional[dict[str, Any]] = None


class GeocoderError(Exception):
    """Provider-level geocoding failure (network, auth, no provider support)."""


def _encode_params(params: dict[str, Any]) -> dict[str, Any]:
    # httpx url-encodes automatically; explicit tuple handlers not needed.
    out: dict[str, Any] = {}
    for k, v in params.items():
        if v is not None:
            out[k] = v
    return out


def _base_url(provider: ProviderName) -> str:
    if settings.geocoder_base_url:
        return settings.geocoder_base_url.rstrip("/")
    return _DEFAULT_BASE_URLS[provider]


def _geocode_nominatim(q: str, limit: int, bias: Optional[tuple[float, float]]) -> list[GeoPlace]:
    params: dict[str, Any] = {
        "q": q,
        "format": "jsonv2",
        "limit": limit,
        "addressdetails": 1,
        "countrycodes": "in",
        "bounded": 0,
    }
    # Bias results towards the selected admin area (a small viewbox around the
    # centroid). Viewbox order for Nominatim is left, top, right, bottom.
    if bias is not None:
        lat, lng = bias
        d = 0.15
        params["viewbox"] = f"{lng - d},{lat + d},{lng + d},{lat - d}"
    url = f"{_base_url('nominatim')}/search"
    resp = httpx.get(url, params=_encode_params(params), timeout=settings.geocoder_timeout_s,
                     headers={"User-Agent": settings.geocoder_user_agent})
    resp.raise_for_status()
    places: list[GeoPlace] = []
    for item in resp.json() or []:
        name = (item.get("name") or item.get("display_name") or "").split(",")[0].strip()
        display = item.get("display_name") or q
        lat = item.get("lat")
        lon = item.get("lon")
        if lat is None or lon is None:
            continue
        places.append(GeoPlace(
            name=name or q,
            display_name=display,
            latitude=float(lat),
            longitude=float(lon),
            provider="nominatim",
            confidence="high" if float(item.get("importance") or 0) >= 0.4 else "medium",
            raw=item,
        ))
    return places


def _geocode_photon(q: str, limit: int, bias: Optional[tuple[float, float]]) -> list[GeoPlace]:
    params: dict[str, Any] = {"q": q, "limit": limit, "lang": "en"}
    if bias is not None:
        lat, lng = bias
        d = 0.15
        params["bbox"] = f"{lng - d},{lat - d},{lng + d},{lat + d}"
    resp = httpx.get(f"{_base_url('photon')}/api", params=_encode_params(params),
                     timeout=settings.geocoder_timeout_s,
                     headers={"User-Agent": settings.geocoder_user_agent})
    resp.raise_for_status()
    places: list[GeoPlace] = []
    for feat in (resp.json().get("features") or []):
        props = feat.get("properties") or {}
        geo = feat.get("geometry") or {}
        coords = geo.get("coordinates")
        if not coords:
            continue
        display_parts = []
        for key in ("street", "housenumber", "city", "state", "postcode", "country"):
            if props.get(key):
                display_parts.append(str(props[key]))
        display = props.get("display_name") or ", ".join(display_parts) or str(props.get("name") or q)
        places.append(GeoPlace(
            name=str(props.get("name") or q),
            display_name=display,
            latitude=float(coords[1]),
            longitude=float(coords[0]),
            provider="photon",
            confidence=str(props.get("confidence") or "medium") if props.get("confidence") is not None else "medium",
            raw=feat,
        ))
    return places


def _geocode_google(q: str, limit: int, bias: Optional[tuple[float, float]]) -> list[GeoPlace]:
    if not settings.geocoder_api_key:
        raise GeocoderError("Google geocoder requires GEOCODER_API_KEY")
    params: dict[str, Any] = {
        "address": q,
        "key": settings.geocoder_api_key,
        "limit": limit,
    }
    if bias is not None:
        params["location"] = f"{bias[0]},{bias[1]}"
        params["result_type"] = "street_address|establishment|route|locality"
    resp = httpx.get(_base_url("google"), params=_encode_params(params),
                     timeout=settings.geocoder_timeout_s)
    resp.raise_for_status()
    body = resp.json()
    if body.get("status") not in ("OK", "ZERO_RESULTS"):
        raise GeocoderError(f"Google geocoder error: {body.get('status')}")
    places: list[GeoPlace] = []
    for item in (body.get("results") or [])[:limit]:
        loc = item.get("geometry", {}).get("location") or {}
        if "lat" not in loc or "lng" not in loc:
            continue
        places.append(GeoPlace(
            name=str(item.get("name") or q),
            display_name=item.get("formatted_address") or q,
            latitude=float(loc["lat"]),
            longitude=float(loc["lng"]),
            provider="google",
            confidence="high" if item.get("types") else "medium",
            raw=item,
        ))
    return places


_PROVIDERS: dict[ProviderName, Any] = {
    "nominatim": _geocode_nominatim,
    "photon": _geocode_photon,
    "google": _geocode_google,
}


def search_places(q: str, limit: int = 5, bias: Optional[tuple[float, float]] = None,
                  provider: Optional[str] = None) -> list[GeoPlace]:
    """Search for a place/address and return geocoded results.

    ``bias`` is an optional (lat, lng) tuple used to favour results near the
    selected administrative area. Never requires a key for the free providers.
    """
    q = (q or "").strip()
    if not q:
        return []
    provider_name = (provider or settings.geocoder_provider or "nominatim").lower()
    if provider_name not in _PROVIDERS:
        raise GeocoderError(f"unsupported geocoder provider: {provider_name}")
    return _PROVIDERS[provider_name](q, max(1, min(limit, 20)), bias)


def provider_label() -> str:
    return settings.geocoder_provider or "nominatim"
