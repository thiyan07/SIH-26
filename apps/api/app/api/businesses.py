"""Business / competitor endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import distinct, func, select, text
from sqlalchemy.orm import Session

from app.db.models import Business, UdyamUnit
from app.db.session import get_db
from app.geo import find_nearby_with_distance
from app.schemas import CompetitorDiscoveryQuery, CompetitorQuery, MSMEClustersQuery, NearbyBusinessQuery

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
        "phone": b.phone,
        "website": b.website,
        "opening_hours": b.opening_hours,
        "brand": b.brand,
        "distance_km": round(dist, 2),
        "source_name": b.source_name,
        "source_type": b.source_type,
        "confidence": b.confidence,
        "confidence_score": b.confidence_score,
        "verification_status": b.verification_status,
        "source_url": b.source_url,
        "retrieved_at_date": b.retrieved_at.date().isoformat() if b.retrieved_at else None,
        "metadata": b.metadata_json or {},
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


@router.post("/msme-clusters")
def msme_clusters(q: MSMEClustersQuery, db: Session = Depends(get_db)):
    """Registered-MSME pincode clusters (GeoJSON) near a point.

    UDYAM units are pincode-resolved (no street coords in the official export).
    Return one cluster per pincode centroid within ``radius_km`` with real unit
    counts and, when requested, the per-unit list for a drill-down layer.
    """
    sql = text("""
        SELECT u.pincode,
               u.latitude  AS lat,
               u.longitude AS lon,
               count(*)                          AS total,
               count(DISTINCT u.nic_code)        AS activity_codes,
               (6371 * acos(least(1,
                 cos(radians(:lat))*cos(radians(u.latitude))
                 *cos(radians(u.longitude)-radians(:lon))
                 + sin(radians(:lat))*sin(radians(u.latitude))))) AS km
        FROM udyam_units u
        WHERE u.latitude IS NOT NULL
          AND u.longitude IS NOT NULL
          AND u.pincode IS NOT NULL
        GROUP BY u.pincode, u.latitude, u.longitude
        HAVING (6371 * acos(least(1,
                 cos(radians(:lat))*cos(radians(u.latitude))
                 *cos(radians(u.longitude)-radians(:lon))
                 + sin(radians(:lat))*sin(radians(u.latitude))))) <= :radius
        ORDER BY km
        LIMIT :maxclusters
    """)
    rows = db.execute(sql, {
        "lat": q.latitude, "lon": q.longitude,
        "radius": q.radius_km, "maxclusters": q.max_clusters,
    }).mappings().all()

    unit_lists = {}
    if q.include_units:
        pins = [str(r["pincode"]) for r in rows]
        if pins:
            unit_rows = db.execute(
                select(UdyamUnit.enterprise_name, UdyamUnit.address,
                       UdyamUnit.nic_code, UdyamUnit.pincode)
                .where(UdyamUnit.pincode.in_(pins),
                       UdyamUnit.latitude.is_not(None))
                .order_by(UdyamUnit.pincode, UdyamUnit.enterprise_name)
            ).all()
            by_pin: dict[str, list] = {}
            for uname, addr, nic, pin in unit_rows:
                by_pin.setdefault(str(pin), []).append({
                    "name": uname,
                    "address": addr,
                    "nic_code": nic,
                })
            unit_lists = {str(k): v for k, v in by_pin.items()}

    features = []
    for r in rows:
        pin = str(r["pincode"])
        props = {
            "pincode": pin,
            "total": int(r["total"]),
            "activity_codes": int(r["activity_codes"]),
            "distance_km": round(float(r["km"]), 2),
            "geo_resolution": "pincode",
            "units": unit_lists.get(pin, []) if q.include_units else None,
        }
        features.append({
            "type": "Feature",
            "properties": props,
            "geometry": {"type": "Point", "coordinates": [float(r["lon"]), float(r["lat"])]},
        })

    return {
        "type": "FeatureCollection",
        "features": features,
        "metadata": {
            "count": len(features),
            "radius_km": q.radius_km,
            "center": {"latitude": q.latitude, "longitude": q.longitude},
            "note": ("Registered UDYAM MSME units resolved at pincode granularity "
                     "(the official export has no street coordinates). Each pin is a "
                     "pincode centroid; zoom reveals the relative competitor density. "
                     "Not point-precise business locations."),
        },
    }
