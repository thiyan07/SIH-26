"""Provider contract — DiscoveryProvider protocol.

All providers must produce the same normalized DiscoveryObservation contract.
Orchestrator only knows "execute provider", not provider internals.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from app.discovery.providers import DiscoveryObservation
from app.discovery.targets import DiscoveryTarget

PROVIDER_GOOGLE = "google_maps"
PROVIDER_OSM = "osm"
PROVIDER_LICENSED = "licensed"
PROVIDER_GEOAPIFY = "geoapify"

HEALTH_AVAILABLE = "AVAILABLE"
HEALTH_DEGRADED = "DEGRADED"
HEALTH_UNAVAILABLE = "UNAVAILABLE"
HEALTH_NOT_CONFIGURED = "NOT_CONFIGURED"

@dataclass
class ProviderResult:
    provider: str
    observations: list[DiscoveryObservation]
    status: str  # success | empty | unavailable | error | timeout
    termination_reason: str | None = None
    elapsed_s: float = 0.0
    error_detail: str | None = None
    cached: bool = False

@dataclass
class ProviderHealth:
    provider: str
    status: str
    reason: str
    latency_ms: int | None = None

@runtime_checkable
class DiscoveryProvider(Protocol):
    provider_name: str

    def discover(self, target: DiscoveryTarget, session=None) -> ProviderResult:
        """Execute discovery for a single target. Must never fabricate."""
        ...

    def health_check(self) -> ProviderHealth:
        """Cheap health check, no discovery."""
        ...

    def supports(self, category: str) -> bool:
        """Whether this provider can handle the category."""
        ...

    def cache_key(self, target: DiscoveryTarget) -> str:
        """Stable provider-aware cache key."""
        ...

    @property
    def rate_limit(self) -> dict:
        """Return rate limit config: {concurrency, delay, timeout, max_retries}"""
        ...

def stable_target_key(target: DiscoveryTarget, provider: str) -> str:
    raw = f"{target.district}|{target.locality}|{target.category}|{target.query}|{provider}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]
