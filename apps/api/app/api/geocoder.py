"""Geocoder endpoint — exact place / address search for the proposed shop marker.

Proxy that keeps provider credentials server-side. The frontend never talks to
Nominatim/Photon/Google directly; it calls this endpoint with a plain query and
an optional bias point (the selected admin-area centroid).
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

from app.limiter import limiter
from app.services.geocoder import GeocoderError, GeoPlace, provider_label, search_places

router = APIRouter(prefix="/geocode", tags=["geocode"])


@router.get("/search", response_model=list[GeoPlace])
@limiter.limit("60/minute")
def geocode_search(
    request: Request,
    q: str = Query(min_length=2, max_length=200),
    limit: int = Query(default=5, ge=1, le=20),
    lat: float | None = Query(default=None),
    lng: float | None = Query(default=None),
):
    if len(q.strip()) < 3:
        return []
    bias = None
    if lat is not None and lng is not None:
        bias = (lat, lng)
    try:
        return search_places(q, limit=limit, bias=bias)
    except GeocoderError as e:
        raise HTTPException(status_code=502, detail=f"Geocoder unavailable: {e}")
    except Exception as e:  # network / http errors from the upstream provider
        raise HTTPException(status_code=502, detail=f"Geocoder request failed: {e}")


@router.get("/provider")
def geocode_provider_info():
    return {"provider": provider_label()}
