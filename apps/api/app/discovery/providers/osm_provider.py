"""OSM provider — Overpass with cache, provenance, and health."""
from __future__ import annotations

import time

from app.discovery.providers.base import (
    HEALTH_AVAILABLE,
    HEALTH_DEGRADED,
    HEALTH_NOT_CONFIGURED,
    HEALTH_UNAVAILABLE,
    PROVIDER_OSM,
    ProviderHealth,
    ProviderResult,
    stable_target_key,
)
from app.discovery.targets import DiscoveryTarget

class OSMProvider:
    provider_name = PROVIDER_OSM

    @property
    def rate_limit(self) -> dict:
        from app.discovery.config import CONFIG
        import os
        return {
            "concurrency": 2,  # Overpass is shared, be gentle
            "delay": 1.0,
            "timeout": 40,
            "max_retries": 1,
            "max_targets_per_run": int(os.getenv("OSM_MAX_TARGETS_PER_RUN", "500")),
        }

    def supports(self, category: str) -> bool:
        from app.catalog.business_categories import osm_filters
        return bool(osm_filters(category))

    def cache_key(self, target: DiscoveryTarget) -> str:
        return f"osm:{stable_target_key(target, PROVIDER_OSM)}"

    def health_check(self) -> ProviderHealth:
        try:
            from app.providers.overpass import ping
            mirror = ping(timeout_s=5)
            if mirror:
                return ProviderHealth(provider=PROVIDER_OSM, status=HEALTH_AVAILABLE, reason=f"Overpass mirror reachable: {mirror}")
            return ProviderHealth(provider=PROVIDER_OSM, status=HEALTH_UNAVAILABLE, reason="Overpass unavailable: no mirror responded (will be recorded as provider unavailable, not zero businesses)")
        except Exception as e:
            return ProviderHealth(provider=PROVIDER_OSM, status=HEALTH_UNAVAILABLE, reason=str(e)[:200])

    def discover(self, target: DiscoveryTarget, session=None, refresh: bool = False) -> ProviderResult:
        if not self.supports(target.category):
            return ProviderResult(
                provider=PROVIDER_OSM,
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
                provider=PROVIDER_OSM,
                observations=cached,
                status="empty" if not cached else "success",
                termination_reason="CACHE_HIT",
                elapsed_s=0.0,
                cached=True,
            )
        start = time.time()
        try:
            from app.discovery.providers.osm_adapter import query_osm_for_target
            observations = query_osm_for_target(target, session=session)
            elapsed = time.time() - start
            status = "empty" if not observations else "success"
            return ProviderResult(
                provider=PROVIDER_OSM,
                observations=observations,
                status=status,
                termination_reason="NO_MORE_RESULTS" if status == "empty" else "SUCCESS",
                elapsed_s=elapsed,
            )
        except Exception as e:
            msg = str(e).lower()
            status = "timeout" if "timeout" in msg else "error"
            return ProviderResult(
                provider=PROVIDER_OSM,
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
            from app.discovery.providers.osm_adapter import _check_cache as osm_check
            return osm_check(session, target, ttl_hours=24)
        except Exception:
            return None
