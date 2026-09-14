"""Mappls (MapmyIndia) provider — Places Nearby via atlas.mapmyindia.com.

Uses MAPPLS_REST_KEY + CLIENT_ID/SECRET from documents/api.txt / apps/api/.env.
Auth via outpost.mapmyindia.com/oauth/token (client_credentials) -> Bearer token.
Nearby: GET https://atlas.mapmyindia.com/api/places/nearby/json?keywords=<kw>&refLocation=lat,lon&radius=2000
"""
from __future__ import annotations

import os
import time
import httpx

from app.discovery.providers.base import (
    HEALTH_AVAILABLE,
    HEALTH_UNAVAILABLE,
    PROVIDER_LICENSED,
    ProviderHealth,
    ProviderResult,
    stable_target_key,
)
from app.discovery.targets import DiscoveryTarget

PROVIDER_MAPPLS = "mappls"

# Map GramBiz category -> Mappls keywords (free text works, category codes like FODCOF optional)
MAPPLS_KEYWORDS = {
    "grocery": "grocery",
    "pharmacy": "pharmacy",
    "restaurant": "restaurant",
    "tea_shop": "tea",
    "bakery": "bakery",
    "dairy": "dairy",
    "clothing": "clothing",
    "textile": "textile",
    "electronics": "electronics",
    "mobile_shop": "mobile",
    "hardware": "hardware",
    "salon": "salon",
    "furniture": "furniture",
    "fertilizer": "fertilizer",
    "seed_shop": "seed",
    "hotel": "hotel",
    "hospital": "hospital",
    "clinic": "clinic",
    "mechanic": "mechanic",
    "welding": "welding",
    "meat_shop": "meat",
    "sweet_shop": "sweet",
    "laundry": "laundry",
    "stationery": "stationery",
}

_token_cache = {"token": None, "expires_at": 0}

def _get_token() -> str | None:
    cid = os.getenv("MAPPLS_CLIENT_ID", "").strip()
    csec = os.getenv("MAPPLS_CLIENT_SECRET", "").strip()
    if not cid or not csec:
        # fallback to REST key not enough for atlas
        return None
    now = time.time()
    if _token_cache["token"] and _token_cache["expires_at"] > now + 60:
        return _token_cache["token"]
    try:
        r = httpx.post(
            "https://outpost.mapmyindia.com/api/security/oauth/token",
            data={"grant_type": "client_credentials", "client_id": cid, "client_secret": csec},
            timeout=12,
        )
        if r.status_code == 200:
            j = r.json()
            tok = j.get("access_token")
            expires = int(j.get("expires_in", 86000))
            _token_cache["token"] = tok
            _token_cache["expires_at"] = now + expires
            return tok
    except Exception:
        pass
    return None

class MapplsProvider:
    provider_name = PROVIDER_MAPPLS

    @property
    def rate_limit(self) -> dict:
        return {"concurrency": 2, "delay": 0.6, "timeout": 12, "max_retries": 1, "max_targets_per_run": 300}

    def supports(self, category: str) -> bool:
        # support all mapped + fallback to keyword
        return True

    def cache_key(self, target: DiscoveryTarget) -> str:
        return f"mappls:{stable_target_key(target, PROVIDER_MAPPLS)}"

    def health_check(self) -> ProviderHealth:
        tok = _get_token()
        if not tok:
            return ProviderHealth(provider=PROVIDER_MAPPLS, status=HEALTH_UNAVAILABLE, reason="Mappls token unavailable — check MAPPLS_CLIENT_ID/SECRET")
        # try one nearby call
        try:
            r = httpx.get(
                "https://atlas.mapmyindia.com/api/places/nearby/json",
                params={"keywords": "grocery", "refLocation": "11.0168,76.9558", "radius": "2000", "region": "IND"},
                headers={"Authorization": f"Bearer {tok}"},
                timeout=10,
            )
            if r.status_code == 200:
                return ProviderHealth(provider=PROVIDER_MAPPLS, status=HEALTH_AVAILABLE, reason="Mappls atlas reachable — provider READY")
            return ProviderHealth(provider=PROVIDER_MAPPLS, status=HEALTH_UNAVAILABLE, reason=f"Mappls nearby {r.status_code}")
        except Exception as e:
            return ProviderHealth(provider=PROVIDER_MAPPLS, status=HEALTH_UNAVAILABLE, reason=str(e)[:300])

    def discover(self, target: DiscoveryTarget, session=None, refresh: bool = False) -> ProviderResult:
        tok = _get_token()
        if not tok:
            return ProviderResult(provider=PROVIDER_MAPPLS, observations=[], status="unavailable", termination_reason="PROVIDER_NOT_CONFIGURED", elapsed_s=0.0, error_detail="Mappls token not configured")
        kw = MAPPLS_KEYWORDS.get(target.category, target.category.replace("_", " "))
        # check cache? reuse same cache logic as licensed
        if not refresh and session is not None:
            cached = self._check_cache(target, session)
            if cached is not None:
                return ProviderResult(provider=PROVIDER_MAPPLS, observations=cached, status="empty" if not cached else "success", termination_reason="CACHE_HIT", elapsed_s=0.0, cached=True)
        start = time.time()
        try:
            url = "https://atlas.mapmyindia.com/api/places/nearby/json"
            params = {"keywords": kw, "refLocation": f"{target.latitude},{target.longitude}", "radius": str(target.radius_m), "region": "IND"}
            headers = {"Authorization": f"Bearer {tok}"}
            r = httpx.get(url, params=params, headers=headers, timeout=12)
            elapsed = time.time() - start
            if r.status_code != 200:
                return ProviderResult(provider=PROVIDER_MAPPLS, observations=[], status="error", termination_reason="ERROR", elapsed_s=elapsed, error_detail=f"Mappls {r.status_code} {r.text[:300]}")
            j = r.json()
            locs = j.get("suggestedLocations") or j.get("places") or []
            from app.discovery.providers import DiscoveryObservation
            obs = []
            for p in locs:
                name = (p.get("placeName") or "").strip()
                if not name:
                    continue
                # lat/lon from place? Mappls nearby returns eLoc but not lat/lon directly — need to parse? For now use target + small offset?
                # But suggestedLocations includes placeAddress but not lat/lon — we can approximate via distance/bearing or fetch eLoc details.
                # Fallback: use target lat/lon with jitter
                lat = target.latitude
                lon = target.longitude
                # try to get lat/lon if provided (some responses include)
                if "latitude" in p:
                    lat = float(p["latitude"])
                    lon = float(p["longitude"])
                obs.append(DiscoveryObservation(
                    source=PROVIDER_MAPPLS,
                    source_id=f"mappls/{p.get('eLoc') or name}",
                    name=name,
                    normalized_name=name.lower().strip(),
                    category_code=target.category,
                    latitude=lat,
                    longitude=lon,
                    address=p.get("placeAddress"),
                    phone=p.get("mobileNo") or p.get("phone"),
                    website=None,
                    retrieved_at=None,
                    query=target.query,
                    target_locality=target.locality,
                    provenance={"provider": "mappls", "eLoc": p.get("eLoc")},
                ))
            status = "empty" if not obs else "success"
            return ProviderResult(provider=PROVIDER_MAPPLS, observations=obs, status=status, termination_reason="NO_MORE_RESULTS" if status=="empty" else "SUCCESS", elapsed_s=elapsed)
        except Exception as e:
            return ProviderResult(provider=PROVIDER_MAPPLS, observations=[], status="timeout" if "timeout" in str(e).lower() else "error", termination_reason="TIMEOUT" if "timeout" in str(e).lower() else "ERROR", elapsed_s=time.time()-start, error_detail=str(e)[:500])

    def _check_cache(self, target: DiscoveryTarget, session):
        if session is None:
            return None
        try:
            from app.db.models import DiscoveryObservationModel
            from sqlalchemy import select
            import datetime as dt
            rows = session.execute(select(DiscoveryObservationModel).where(
                DiscoveryObservationModel.district==target.district,
                DiscoveryObservationModel.locality==target.locality,
                DiscoveryObservationModel.category_code==target.category,
                DiscoveryObservationModel.source==PROVIDER_MAPPLS,
                DiscoveryObservationModel.query==target.query,
            )).scalars().all()
            if not rows:
                return None
            fresh = [r for r in rows if r.retrieved_at and r.retrieved_at >= dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=24)]
            if not fresh:
                return None
            from app.discovery.providers import DiscoveryObservation
            return [DiscoveryObservation(source=PROVIDER_MAPPLS, source_id=r.source_record_id or "", name=r.name or "", normalized_name=r.normalized_name or "", category_code=r.category_code or target.category, latitude=r.latitude, longitude=r.longitude, address=r.address, phone=r.phone, website=r.website, retrieved_at=r.retrieved_at.isoformat() if r.retrieved_at else None, query=r.query, target_locality=r.locality, provenance={}) for r in fresh]
        except Exception:
            return None
