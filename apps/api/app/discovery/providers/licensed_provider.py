"""Licensed geospatial provider — generic adapter (currently Geoapify).

Do not hardcode API key; configuration via env:
  DISCOVERY_PROVIDER=geoapify
  DISCOVERY_PROVIDER_API_KEY=...  or data_provider_keys JSON

If not configured, health is UNAVAILABLE and discover returns unavailable (not empty).
Never fabricate.
"""
from __future__ import annotations

import os
import time

from app.discovery.providers.base import (
    HEALTH_AVAILABLE,
    HEALTH_UNAVAILABLE,
    PROVIDER_LICENSED,
    ProviderHealth,
    ProviderResult,
    stable_target_key,
)
from app.discovery.targets import DiscoveryTarget

def _api_key() -> str | None:
    # Spec: DISCOVERY_LICENSED_API_KEY, fallback to DISCOVERY_PROVIDER_API_KEY, then data_provider_keys.geoapify
    for env in ("DISCOVERY_LICENSED_API_KEY", "DISCOVERY_PROVIDER_API_KEY"):
        key = os.getenv(env, "").strip()
        if key:
            return key
    try:
        import json
        from app.config import settings
        dpk = getattr(settings, "data_provider_keys", "") or ""
        if dpk:
            data = json.loads(dpk)
            return (data.get("geoapify") or data.get("licensed") or "").strip() or None
    except Exception:
        pass
    return None

class LicensedGeospatialProvider:
    provider_name = PROVIDER_LICENSED
    # For now, licensed provider is Geoapify; can be extended to other licensed sources
    licensed_source = "geoapify"

    @property
    def rate_limit(self) -> dict:
        return {
            "concurrency": 2,
            "delay": 0.8,
            "timeout": 20,
            "max_retries": 1,
            "max_targets_per_run": int(os.getenv("LICENSED_MAX_TARGETS_PER_RUN", "300")),
        }

    def supports(self, category: str) -> bool:
        from app.providers.geoapify import GEOAPIFY_CATEGORIES
        return category in GEOAPIFY_CATEGORIES

    def cache_key(self, target: DiscoveryTarget) -> str:
        return f"licensed:{stable_target_key(target, PROVIDER_LICENSED)}"

    def health_check(self) -> ProviderHealth:
        from app.discovery.providers.base import HEALTH_NOT_CONFIGURED
        key = _api_key()
        if not key:
            return ProviderHealth(
                provider=PROVIDER_LICENSED,
                status=HEALTH_NOT_CONFIGURED,
                reason="Licensed provider NOT_CONFIGURED: set DISCOVERY_LICENSED_API_KEY or DISCOVERY_PROVIDER_API_KEY or data_provider_keys.geoapify",
            )
        try:
            from app.providers.geoapify import ping
            ok = ping(key=key)
            if ok:
                return ProviderHealth(provider=PROVIDER_LICENSED, status=HEALTH_AVAILABLE, reason="Geoapify reachable — licensed provider READY")
            return ProviderHealth(provider=PROVIDER_LICENSED, status=HEALTH_UNAVAILABLE, reason="Geoapify ping failed with configured key")
        except Exception as e:
            return ProviderHealth(provider=PROVIDER_LICENSED, status=HEALTH_UNAVAILABLE, reason=str(e)[:300])

    def discover(self, target: DiscoveryTarget, session=None, refresh: bool = False) -> ProviderResult:
        from app.discovery.providers.base import HEALTH_NOT_CONFIGURED
        key = _api_key()
        if not key:
            return ProviderResult(
                provider=PROVIDER_LICENSED,
                observations=[],
                status="not_configured",
                termination_reason="PROVIDER_NOT_CONFIGURED",
                elapsed_s=0.0,
                error_detail="Licensed provider API key not configured — set DISCOVERY_LICENSED_API_KEY",
            )
        if not self.supports(target.category):
            return ProviderResult(
                provider=PROVIDER_LICENSED,
                observations=[],
                status="empty",
                termination_reason="CATEGORY_NOT_SUPPORTED",
                elapsed_s=0.0,
            )
        if not refresh:
            cached = self._check_cache(target, session)
        else:
            cached = None
        if cached is not None:
            return ProviderResult(
                provider=PROVIDER_LICENSED,
                observations=cached,
                status="empty" if not cached else "success",
                termination_reason="CACHE_HIT",
                elapsed_s=0.0,
                cached=True,
            )
        start = time.time()
        try:
            from app.providers.geoapify import query as geo_query
            result = geo_query(
                lat=target.latitude,
                lon=target.longitude,
                radius_m=target.radius_m,
                category_code=target.category,
                key=key,
            )
            elapsed = time.time() - start
            from app.discovery.providers import DiscoveryObservation
            observations = []
            for poi in result.pois:
                observations.append(DiscoveryObservation(
                    source=PROVIDER_LICENSED,
                    source_id=poi.get("source_record_id") or "",
                    name=poi.get("name") or "",
                    normalized_name=poi.get("normalized_name") or "",
                    category_code=target.category,
                    latitude=poi.get("latitude"),
                    longitude=poi.get("longitude"),
                    address=poi.get("address"),
                    phone=poi.get("phone"),
                    website=poi.get("website"),
                    retrieved_at=poi.get("retrieved_at"),
                    query=target.query,
                    target_locality=target.locality,
                    provenance={"provider": "geoapify", "matched_tags": poi.get("matched_tags")},
                ))
            status = "empty" if not observations else "success"
            return ProviderResult(
                provider=PROVIDER_LICENSED,
                observations=observations,
                status=status,
                termination_reason="NO_MORE_RESULTS" if status == "empty" else "SUCCESS",
                elapsed_s=elapsed,
            )
        except Exception as e:
            from app.providers.geoapify import GeoapifyUnavailable
            msg = str(e).lower()
            if isinstance(e, GeoapifyUnavailable) and "not configured" in msg:
                return ProviderResult(provider=PROVIDER_LICENSED, observations=[], status="unavailable", termination_reason="PROVIDER_NOT_CONFIGURED", elapsed_s=0.0, error_detail=str(e)[:500])
            status = "timeout" if "timeout" in msg else "error"
            return ProviderResult(
                provider=PROVIDER_LICENSED,
                observations=[],
                status=status,
                termination_reason="TIMEOUT" if status == "timeout" else "ERROR",
                elapsed_s=time.time() - start,
                error_detail=str(e)[:500],
            )

    def _check_cache(self, target: DiscoveryTarget, session):
        if session is None:
            return None
        try:
            from app.db.models import DiscoveryObservationModel
            from sqlalchemy import select
            import datetime as dt
            rows = session.execute(
                select(DiscoveryObservationModel).where(
                    DiscoveryObservationModel.district == target.district,
                    DiscoveryObservationModel.locality == target.locality,
                    DiscoveryObservationModel.category_code == target.category,
                    DiscoveryObservationModel.source == PROVIDER_LICENSED,
                    DiscoveryObservationModel.query == target.query,
                )
            ).scalars().all()
            if not rows:
                return None
            fresh_cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=24)
            fresh = [r for r in rows if r.retrieved_at and r.retrieved_at >= fresh_cutoff]
            if not fresh:
                return None
            from app.discovery.providers import DiscoveryObservation
            obs_list = []
            for r in fresh:
                obs_list.append(DiscoveryObservation(
                    source=PROVIDER_LICENSED,
                    source_id=r.source_record_id or "",
                    name=r.name or "",
                    normalized_name=r.normalized_name or "",
                    category_code=r.category_code or target.category,
                    latitude=r.latitude,
                    longitude=r.longitude,
                    address=r.address,
                    phone=r.phone,
                    website=r.website,
                    retrieved_at=r.retrieved_at.isoformat() if r.retrieved_at else None,
                    query=r.query,
                    target_locality=r.locality,
                    provenance=r.raw_payload.get("provenance", {}) if r.raw_payload else {},
                ))
            return obs_list
        except Exception:
            return None
