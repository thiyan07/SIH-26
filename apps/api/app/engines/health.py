"""Health-access evidence engine: distance to the nearest public health facility.

Reads only real (non-demo) ``InfrastructurePoint`` rows with ``kind=hospital``
— official NIC health establishments (GODL-India, via Bharat Atlas) plus mapped
OSM hospitals — and reports the nearest one plus a nearby count. Coordinates
come straight from the source; nothing is estimated. Absence of facilities is
reported as ``available=False``, never as a fabricated distance.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import InfrastructurePoint
from app.geo import find_nearby_with_distance

SEARCH_KM = 20.0


def health_access_evidence(
    db: Session,
    latitude: float,
    longitude: float,
    search_km: float = SEARCH_KM,
    limit: int = 100,
) -> dict:
    """Nearest public health facility + nearby count within ``search_km``.

    Returns a provenance-bearing dict (nearest facility metadata included) so
    the accessibility and risk scores are traceable to a real row.
    """
    pairs = find_nearby_with_distance(
        db, InfrastructurePoint, latitude, longitude, search_km,
        {"kind": "hospital"}, limit=limit)
    points = [p for p, _ in pairs]
    nearest = points[0] if points else None
    return {
        "available": bool(nearest),
        "nearest_health_km": round(pairs[0][1], 2) if pairs else None,
        "health_facilities_nearby": len(points),
        "nearest_health": (
            {
                "name": nearest.name,
                "source_name": nearest.source_name,
                "source_type": nearest.source_type,
                "dataset_name": nearest.dataset_name,
                "confidence": nearest.confidence,
            }
            if nearest else None
        ),
    }
