"""GeoJSON map-layer endpoint (plan §26).

Serves point FeatureCollections for the businesses, infrastructure and
markets layers around a pin, built from the portable lat/lng + provenance
columns. The frontend map renders each layer as a separate toggle.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.db.models import Business, InfrastructurePoint
from app.db.session import get_db
from app.geo import find_nearby_with_distance, geography_enabled
from app.geojson import (
    businesses_feature_collection,
    infrastructure_feature_collection,
)
from app.limiter import limiter
from app.schemas import LayerQuery

router = APIRouter(prefix="/geojson", tags=["geojson"])


@router.post("/layers")
@limiter.limit("120/minute")
def geojson_layers(request: Request, q: LayerQuery, db: Session = Depends(get_db)):
    layers = q.layers or ["businesses", "infrastructure", "markets"]
    out: dict = {}
    counts: dict = {}

    if "businesses" in layers:
        rows = find_nearby_with_distance(db, Business, q.latitude, q.longitude,
                                         q.radius_km, None, 500)
        out["businesses"] = businesses_feature_collection(rows)
        counts["businesses"] = len(rows)

    infra_rows = (
        find_nearby_with_distance(db, InfrastructurePoint, q.latitude, q.longitude,
                                  q.radius_km, None, 500)
        if "infrastructure" in layers or "markets" in layers
        else []
    )
    if "infrastructure" in layers:
        out["infrastructure"] = infrastructure_feature_collection(infra_rows)
        counts["infrastructure"] = len(infra_rows)
    if "markets" in layers:
        market_rows = [(i, d) for i, d in infra_rows if i.kind == "market"]
        out["markets"] = infrastructure_feature_collection(market_rows)
        counts["markets"] = len(market_rows)

    return {
        "center": {"latitude": q.latitude, "longitude": q.longitude},
        "radius_km": q.radius_km,
        "geo_backend": "postgis" if geography_enabled(db, Business) else "haversine",
        "layers": out,
        "counts": counts,
        "note": "GeoJSON built from Mapped lat/lng + provenance; data may be incomplete.",
    }
