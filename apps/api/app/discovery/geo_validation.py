"""Geographic validation — classify observations vs intended target.

Each observation carries target_locality + actual lat/lon. We compute
distance_from_target and status:
  IN_TARGET_LOCALITY / NEAR_TARGET_LOCALITY / OUTSIDE_TARGET_AREA / OUTSIDE_DISTRICT / GEOGRAPHICALLY_UNCERTAIN

District polygon containment (via AdministrativeBoundary bbox) is attempted first
when available; otherwise radius-based validation is used. Never auto-discard.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sqlalchemy.orm import Session

from app.discovery.providers import DiscoveryObservation
from app.discovery.targets import DiscoveryTarget
from app.geo import haversine_km

STATUS_IN = "IN_TARGET_LOCALITY"
STATUS_NEAR = "NEAR_TARGET_LOCALITY"
STATUS_OUTSIDE = "OUTSIDE_TARGET_AREA"
STATUS_OUTSIDE_DISTRICT = "OUTSIDE_DISTRICT"
STATUS_UNCERTAIN = "GEOGRAPHICALLY_UNCERTAIN"

@dataclass
class GeoValidation:
    target_locality: str
    actual_latitude: float | None
    actual_longitude: float | None
    distance_from_target_km: float | None
    geographic_match_status: str
    reason: str | None = None

def haversine_m(lat1, lon1, lat2, lon2) -> float:
    return haversine_km(lat1, lon1, lat2, lon2) * 1000.0

def _district_bbox_contains(session: Optional[Session], district: str, lat: float, lon: float) -> Optional[bool]:
    """Check district bbox containment when AdministrativeBoundary geometry available.

    Returns None if no bbox data, True/False otherwise.
    """
    if session is None:
        return None
    try:
        from app.db.models import AdministrativeBoundary
        from sqlalchemy import select
        row = session.execute(
            select(AdministrativeBoundary).where(
                AdministrativeBoundary.level == "district",
                AdministrativeBoundary.name.ilike(district),
            )
        ).scalars().first()
        if row and row.bbox:
            bbox = row.bbox
            # Expect bbox as [min_lon, min_lat, max_lon, max_lat] or dict
            if isinstance(bbox, dict):
                min_lat = bbox.get("min_lat") or bbox.get("south")
                max_lat = bbox.get("max_lat") or bbox.get("north")
                min_lon = bbox.get("min_lon") or bbox.get("west")
                max_lon = bbox.get("max_lon") or bbox.get("east")
            elif isinstance(bbox, (list, tuple)) and len(bbox) == 4:
                min_lon, min_lat, max_lon, max_lat = bbox
            else:
                return None
            if None in (min_lat, max_lat, min_lon, max_lon):
                return None
            return (min_lat <= lat <= max_lat) and (min_lon <= lon <= max_lon)
    except Exception:
        return None
    return None


def validate_observation(
    obs: DiscoveryObservation,
    target: DiscoveryTarget,
    session: Optional[Session] = None,
) -> GeoValidation:
    if obs.latitude is None or obs.longitude is None or target.latitude is None:
        return GeoValidation(
            target_locality=target.locality,
            actual_latitude=obs.latitude,
            actual_longitude=obs.longitude,
            distance_from_target_km=None,
            geographic_match_status=STATUS_UNCERTAIN,
            reason="Missing coordinates",
        )
    # First: district polygon/bbox containment when available
    outside_district = _district_bbox_contains(session, target.district, obs.latitude, obs.longitude)
    if outside_district is False:
        # Point outside district bbox — strong signal, but still classify with distance
        dist_km = haversine_km(target.latitude, target.longitude, obs.latitude, obs.longitude)
        return GeoValidation(
            target_locality=target.locality,
            actual_latitude=obs.latitude,
            actual_longitude=obs.longitude,
            distance_from_target_km=round(dist_km, 3),
            geographic_match_status=STATUS_OUTSIDE_DISTRICT,
            reason=f"Outside district {target.district} boundary (bbox check)",
        )
    dist_km = haversine_km(target.latitude, target.longitude, obs.latitude, obs.longitude)
    dist_m = dist_km * 1000.0
    radius_m = target.radius_m or 3000
    if dist_m <= radius_m:
        status = STATUS_IN
        reason = f"Within target radius {radius_m}m"
    elif dist_m <= max(radius_m * 2, 5000):
        status = STATUS_NEAR
        reason = f"Near target (up to {max(radius_m*2,5000)}m)"
    elif dist_m <= 20000:
        status = STATUS_OUTSIDE
        reason = f"Outside target area ({int(dist_m)}m away)"
    else:
        status = STATUS_OUTSIDE
        reason = f"Geographically distant ({int(dist_m)}m) — likely different area"
    return GeoValidation(
        target_locality=target.locality,
        actual_latitude=obs.latitude,
        actual_longitude=obs.longitude,
        distance_from_target_km=round(dist_km, 3),
        geographic_match_status=status,
        reason=reason,
    )

def suspicious_result(obs: DiscoveryObservation, target: DiscoveryTarget, threshold_km: float = 10.0) -> bool:
    v = validate_observation(obs, target)
    return v.geographic_match_status == STATUS_OUTSIDE and (v.distance_from_target_km or 0) > threshold_km
