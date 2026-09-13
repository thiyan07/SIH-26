"""OSM query adapter — provider-appropriate queries for Overpass.

Maps discovery category_code to OSM tag filters via app/catalog/business_categories.
Preserves provenance and does not invent tags when no reliable mapping exists.
"""
from __future__ import annotations

import datetime as dt
from typing import Optional

from app.catalog.business_categories import osm_filters
from app.discovery.providers import DiscoveryObservation
from app.discovery.targets import DiscoveryTarget

def osm_filters_for_category(category: str) -> list[dict]:
    return osm_filters(category) or []

def query_osm_for_target(
    target: DiscoveryTarget,
    ttl_hours: float = 24.0,
    session=None,
) -> list[DiscoveryObservation]:
    """Query Overpass for a single target, with cache reuse.

    Returns list of DiscoveryObservation (possibly from cache).
    """
    # Check cache first if session provided
    if session is not None:
        cached = _check_cache(session, target, ttl_hours)
        if cached is not None:
            return cached
    # Live query
    from app.providers import overpass as overpass_provider
    try:
        result = overpass_provider.query(
            lat=target.latitude,
            lon=target.longitude,
            radius_m=target.radius_m,
            category_code=target.category,
        )
    except Exception:
        # Treat failure as empty, not zero-business fact
        return []
    observations: list[DiscoveryObservation] = []
    for poi in result.pois:
        # poi already normalized by overpass provider
        observations.append(DiscoveryObservation(
            source="osm",
            source_id=poi.get("source_record_id") or "",
            name=poi.get("name") or "",
            normalized_name=poi.get("normalized_name") or (poi.get("name") or "").lower().strip(),
            category_code=target.category,
            latitude=poi.get("latitude"),
            longitude=poi.get("longitude"),
            address=poi.get("address"),
            phone=poi.get("phone"),
            website=poi.get("website"),
            source_url=None,
            retrieved_at=result.queried_at.isoformat() if isinstance(result.queried_at, dt.datetime) else str(result.queried_at),
            query=target.query,
            target_locality=target.locality,
            target_category=target.category,
            provenance={"provider": "overpass", "mirror": result.mirror, "matched_tags": poi.get("matched_tags")},
        ))
    # Store to cache if session
    if session is not None and observations:
        _store_cache(session, target, observations)
    return observations

def _cache_key(target: DiscoveryTarget) -> str:
    # Provider-aware key
    from app.discovery.targets import target_identity
    return f"osm:{target_identity(target, 'osm')}"

def _check_cache(session, target: DiscoveryTarget, ttl_hours: float):
    try:
        from app.db.models import CompetitorCache
        from sqlalchemy import select
        import datetime as dt
        key = _cache_key(target)
        row = session.execute(select(CompetitorCache).where(CompetitorCache.scope_key == key)).scalars().first()
        if row and row.queried_at:
            age_hours = (dt.datetime.now(dt.timezone.utc) - row.queried_at).total_seconds() / 3600
            if age_hours < ttl_hours and row.payload:
                # Rehydrate cached observations
                obs_list = []
                for p in row.payload:
                    obs_list.append(DiscoveryObservation(
                        source="osm",
                        source_id=p.get("source_record_id") or "",
                        name=p.get("name") or "",
                        normalized_name=p.get("normalized_name") or "",
                        category_code=target.category,
                        latitude=p.get("latitude"),
                        longitude=p.get("longitude"),
                        address=p.get("address"),
                        phone=p.get("phone"),
                        website=p.get("website"),
                        retrieved_at=row.queried_at.isoformat(),
                        query=target.query,
                        target_locality=target.locality,
                        target_category=target.category,
                        provenance={"cached": True, "mirror": row.mirror},
                    ))
                return obs_list
    except Exception:
        return None
    return None

def _store_cache(session, target: DiscoveryTarget, observations: list[DiscoveryObservation]):
    try:
        from app.db.models import CompetitorCache
        import datetime as dt, uuid
        key = _cache_key(target)
        payload = [
            {
                "source_record_id": o.source_id,
                "name": o.name,
                "normalized_name": o.normalized_name,
                "latitude": o.latitude,
                "longitude": o.longitude,
                "address": o.address,
                "phone": o.phone,
                "website": o.website,
            } for o in observations
        ]
        from sqlalchemy import select
        row = session.execute(select(CompetitorCache).where(CompetitorCache.scope_key == key)).scalars().first()
        if row:
            row.payload = payload
            row.queried_at = dt.datetime.now(dt.timezone.utc)
        else:
            cc = CompetitorCache(
                id=str(uuid.uuid4()),
                scope_key=key,
                source="osm",
                category_code=target.category,
                lat_center=target.latitude,
                lon_center=target.longitude,
                radius_m=target.radius_m,
                payload=payload,
                queried_at=dt.datetime.now(dt.timezone.utc),
                mirror="cache",
                response_ok=True,
            )
            session.add(cc)
            session.flush()
    except Exception:
        pass
