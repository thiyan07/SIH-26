"""Business / competitor endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.models import Business
from app.db.session import get_db
from app.geo import find_nearby_with_distance
from app.schemas import CompetitorDiscoveryQuery, CompetitorQuery, NearbyBusinessQuery

router = APIRouter(prefix="/businesses", tags=["businesses"])


def _out(b, dist):
    return {
        "id": b.id,
        "name": b.name,
        "category_code": b.category_code,
        "subcategory": b.subcategory,
        "latitude": b.latitude,
        "longitude": b.longitude,
        "address": b.address,
        "distance_km": round(dist, 2),
        "source_name": b.source_name,
        "source_type": b.source_type,
        "confidence": b.confidence,
        "source_url": b.source_url,
        "retrieved_at_date": b.retrieved_at.date().isoformat() if b.retrieved_at else None,
    }


@router.post("/nearby")
def nearby_businesses(q: NearbyBusinessQuery, db: Session = Depends(get_db)):
    filters = {"category_code": q.category_code} if q.category_code else None
    rows = find_nearby_with_distance(db, Business, q.latitude, q.longitude, q.radius_km, filters, 300)
    return {
        "count": len(rows),
        "radius_km": q.radius_km,
        "note": "Mapped business data may be incomplete.",
        "businesses": [_out(r, d) for r, d in rows],
    }


@router.post("/competitors")
def competitors(q: CompetitorQuery, db: Session = Depends(get_db)):
    rows = find_nearby_with_distance(db, Business, q.latitude, q.longitude, q.radius_km,
                                     {"category_code": q.category_code}, 300)
    distances = [d for _, d in rows]
    nearest = min(distances) if distances else None
    return {
        "category_code": q.category_code,
        "radius_km": q.radius_km,
        "count": len(rows),
        "mapped_competitors": len(rows),
        "nearest_competitor_km": round(nearest, 2) if nearest else None,
        "mean_distance_km": round(sum(distances) / len(distances), 2) if distances else None,
        "data_completeness": "medium",
        "note": "Mapped competitors are not guaranteed to represent all real businesses.",
        "businesses": [_out(r, d) for r, d in rows],
    }


@router.post("/discovery")
def discovery(q: CompetitorDiscoveryQuery, db: Session = Depends(get_db)):
    """P0 exact-location competitor discovery (live OSM/Overpass + geo cache).

    Uses the map-marker latitude/longitude + radius + category to discover real,
    provenance-bearing competitors and compute analytics. Refreshes when the
    marker moves; caches by geographic bucket to avoid hammering Overpass.
    """
    from app.services.competitors import discover_competitors
    result = discover_competitors(
        db, latitude=q.latitude, longitude=q.longitude,
        category_code=q.category_code,
        radius_m=q.radius_m, radius_km=q.radius_km,
    )
    return result
