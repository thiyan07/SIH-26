"""Google Maps provider — adaptive, bounded, configurable.

Configuration via env:
  GOOGLE_MAPS_PROVIDER=disabled|playwright|external  (default disabled, safe)
  GOOGLE_MAPS_MAX_TARGETS_PER_RUN, etc. via DiscoveryConfig

If disabled or Playwright not available, discover() returns status unavailable (not empty).
"""
from __future__ import annotations

import os
import time

from app.discovery.providers.base import (
    HEALTH_AVAILABLE,
    HEALTH_DEGRADED,
    HEALTH_UNAVAILABLE,
    PROVIDER_GOOGLE,
    ProviderHealth,
    ProviderResult,
    stable_target_key,
)
from app.discovery.targets import DiscoveryTarget

def _mode() -> str:
    # Support both DISCOVERY_GOOGLE_PROVIDER (spec) and legacy GOOGLE_MAPS_PROVIDER
    mode = os.getenv("DISCOVERY_GOOGLE_PROVIDER", "").strip() or os.getenv("GOOGLE_MAPS_PROVIDER", "").strip()
    return (mode or "disabled").lower()

def _is_playwright_available() -> tuple[bool, str]:
    try:
        from playwright.sync_api import sync_playwright
        # Check browser executable exists
        import shutil
        # Playwright uses bundled chromium; check if we can launch
        # We do a cheap check: try to import and not actually launch
        return True, "Playwright package available"
    except Exception as e:
        return False, f"Playwright not available: {e}"

class GoogleMapsProvider:
    provider_name = PROVIDER_GOOGLE

    def __init__(self, mode: str | None = None):
        self.mode = (mode or _mode()).lower()
        self._health_cache = None

    @property
    def rate_limit(self) -> dict:
        from app.discovery.config import CONFIG
        return {
            "concurrency": CONFIG.concurrency,
            "delay": CONFIG.delay_s,
            "timeout": CONFIG.timeout_s,
            "max_retries": CONFIG.retry_count,
            "max_targets_per_run": int(os.getenv("GOOGLE_MAPS_MAX_TARGETS_PER_RUN", "200")),
        }

    def supports(self, category: str) -> bool:
        # Google Maps supports all categories via query text
        return True

    def cache_key(self, target: DiscoveryTarget) -> str:
        return f"google_maps:{stable_target_key(target, PROVIDER_GOOGLE)}"

    def health_check(self) -> ProviderHealth:
        from app.discovery.providers.base import HEALTH_NOT_CONFIGURED
        mode = self.mode
        if mode == "disabled":
            return ProviderHealth(provider=PROVIDER_GOOGLE, status=HEALTH_NOT_CONFIGURED, reason="DISCOVERY_GOOGLE_PROVIDER=disabled (safe default) — Google Maps provider not configured")
        if mode == "external":
            return ProviderHealth(provider=PROVIDER_GOOGLE, status=HEALTH_NOT_CONFIGURED, reason="DISCOVERY_GOOGLE_PROVIDER=external not configured — external provider not set")
        if mode == "playwright":
            ok, reason = _is_playwright_available()
            if not ok:
                return ProviderHealth(provider=PROVIDER_GOOGLE, status=HEALTH_UNAVAILABLE, reason=reason)
            try:
                from playwright.sync_api import sync_playwright
                return ProviderHealth(provider=PROVIDER_GOOGLE, status=HEALTH_AVAILABLE, reason="Playwright runtime available — Google Maps provider READY")
            except Exception as e:
                return ProviderHealth(provider=PROVIDER_GOOGLE, status=HEALTH_UNAVAILABLE, reason=str(e))
        return ProviderHealth(provider=PROVIDER_GOOGLE, status=HEALTH_NOT_CONFIGURED, reason=f"Unknown mode {mode} — treated as not configured")

    def discover(self, target: DiscoveryTarget, session=None, refresh: bool = False) -> ProviderResult:
        from app.discovery.providers.base import HEALTH_NOT_CONFIGURED
        from app.discovery.providers.base import HEALTH_NOT_CONFIGURED
        health = self.health_check()
        if health.status == HEALTH_NOT_CONFIGURED:
            return ProviderResult(
                provider=PROVIDER_GOOGLE,
                observations=[],
                status="not_configured",
                termination_reason="PROVIDER_NOT_CONFIGURED",
                elapsed_s=0.0,
                error_detail=health.reason,
            )
        if health.status != HEALTH_AVAILABLE:
            return ProviderResult(
                provider=PROVIDER_GOOGLE,
                observations=[],
                status="unavailable",
                termination_reason="PROVIDER_UNAVAILABLE",
                elapsed_s=0.0,
                error_detail=health.reason,
            )
        # Cache check — respect refresh
        if not refresh:
            cached = self._check_cache(target, session)
            if cached is not None:
                return ProviderResult(
                    provider=PROVIDER_GOOGLE,
                    observations=cached,
                    status="empty" if not cached else "success",
                    termination_reason="CACHE_HIT",
                    elapsed_s=0.0,
                    cached=True,
                )
        # Check cache first (DiscoveryObservationModel)
        cached = self._check_cache(target, session)
        if cached is not None:
            return ProviderResult(
                provider=PROVIDER_GOOGLE,
                observations=cached,
                status="empty" if not cached else "success",
                termination_reason="CACHE_HIT",
                elapsed_s=0.0,
                cached=True,
            )
        # Live discovery via adaptive provider
        try:
            from app.discovery.providers.google_maps import scrape_target_adaptive
            # Need a browser — we create one per call (orchestrator will batch with delay)
            # For health, we already verified Playwright available; now try to run
            # To avoid creating browser per target in health check, we do it here
            from playwright.sync_api import sync_playwright
            start = time.time()
            observations = []
            termination = "UNKNOWN"
            # Use a single browser per discover call (orchestrator will handle pooling)
            with sync_playwright() as pw:
                browser = pw.chromium.launch(channel="chrome", headless=True)
                try:
                    # Use bounded retry with exponential backoff
                    from app.discovery.config import CONFIG
                    last_err = None
                    for attempt in range(CONFIG.retry_count + 1):
                        try:
                            result = scrape_target_adaptive(browser, target, fast=True)
                            observations = result.observations
                            termination = result.termination_reason
                            break
                        except Exception as e:
                            last_err = e
                            if attempt < CONFIG.retry_count:
                                time.sleep(CONFIG.retry_backoff_s * (2 ** attempt))
                            else:
                                raise
                finally:
                    browser.close()
            elapsed = time.time() - start
            # Persist to cache/observation handled by orchestrator; we just return
            status = "empty" if not observations else "success"
            return ProviderResult(
                provider=PROVIDER_GOOGLE,
                observations=observations,
                status=status,
                termination_reason=termination,
                elapsed_s=elapsed,
            )
        except Exception as e:
            # Distinguish timeout vs error
            msg = str(e).lower()
            status = "timeout" if "timeout" in msg else "error"
            return ProviderResult(
                provider=PROVIDER_GOOGLE,
                observations=[],
                status=status,
                termination_reason="TIMEOUT" if status == "timeout" else "ERROR",
                elapsed_s=0.0,
                error_detail=str(e)[:500],
            )

    def _check_cache(self, target: DiscoveryTarget, session):
        if session is None:
            return None
        try:
            from app.db.models import DiscoveryObservationModel
            from sqlalchemy import select
            import datetime as dt
            from app.discovery.config import CONFIG
            ttl = CONFIG.fresh_days * 24  # use fresh_days as TTL for Google
            rows = session.execute(
                select(DiscoveryObservationModel).where(
                    DiscoveryObservationModel.district == target.district,
                    DiscoveryObservationModel.locality == target.locality,
                    DiscoveryObservationModel.category_code == target.category,
                    DiscoveryObservationModel.source == PROVIDER_GOOGLE,
                    DiscoveryObservationModel.query == target.query,
                )
            ).scalars().all()
            if not rows:
                return None
            # Find freshest
            fresh_cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=ttl)
            fresh_rows = [r for r in rows if r.retrieved_at and r.retrieved_at >= fresh_cutoff]
            if not fresh_rows:
                return None  # stale, need refresh
            # Distinguish successful zero-result vs error: if we have a coverage record with ERROR, don't return cached zero
            # For now, if we have fresh rows with at least one observation, it's a successful discovery; if zero rows but we have a row with retrieved_at and no observation, it's zero-result
            # Our cache currently stores observations as rows; zero-result would have no rows, so we can't distinguish without CoverageAudit
            # So we return the fresh observations (could be empty list if zero-result was stored as 0 rows? We need explicit zero-result cache)
            # For Google, we store observations as rows; zero-result would be 0 rows, so we need to check CoverageAudit for zero-result vs not searched
            # To handle correctly, we check CoverageAudit
            from app.db.models import CoverageAudit
            cov = session.execute(
                select(CoverageAudit).where(
                    CoverageAudit.district == target.district,
                    CoverageAudit.locality == target.locality,
                    CoverageAudit.category_code == target.category,
                    CoverageAudit.source == PROVIDER_GOOGLE,
                )
            ).scalars().first()
            if cov and cov.coverage_status == "ERROR":
                return None  # don't reuse error as zero
            # If we have rows, return them as observations
            if fresh_rows:
                from app.discovery.providers import DiscoveryObservation
                obs_list = []
                for r in fresh_rows:
                    obs_list.append(DiscoveryObservation(
                        source=PROVIDER_GOOGLE,
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
            # Zero-result successful discovery would have no rows but would have a CoverageAudit with success and 0 uniques
            # In that case, we should return empty list to indicate cached zero-result (not unavailable)
            if cov and cov.queries_successful and cov.unique_results == 0:
                return []  # cached zero-result
            return None
        except Exception:
            return None
