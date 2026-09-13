"""Cross-source deduplication — canonical business from multiple observations.

Merge signals (explicit confidence):
* EXACT: same source_id
* HIGH: normalized_name + <60m + phone/brand corroboration
* MEDIUM: name token Jaccard >=0.6 + <100m
* LOW: weak name/loc similarity — do NOT merge
* UNMATCHED: no match

Preserves source provenance, never overwrites authoritative info silently.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.discovery.providers import DiscoveryObservation
from app.geo import haversine_km

CONF_EXACT = "EXACT"
CONF_HIGH = "HIGH"
CONF_MEDIUM = "MEDIUM"
CONF_LOW = "LOW"
CONF_UNMATCHED = "UNMATCHED"

def _norm(s: str | None) -> str:
    return (s or "").lower().strip()

def _token_set(s: str) -> set[str]:
    toks = re.split(r"[\s\-_/,.()]+", _norm(s))
    return {t for t in toks if len(t) >= 2}

def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b) if (a | b) else 0.0

def _phones_match(a: str | None, b: str | None) -> bool:
    if not a or not b:
        return False
    da = re.sub(r"\D", "", a)
    db = re.sub(r"\D", "", b)
    if len(da) < 7 or len(db) < 7:
        return False
    return da[-10:] == db[-10:] if len(da) >= 10 and len(db) >= 10 else da == db

def _distance_m(o1: DiscoveryObservation, o2: DiscoveryObservation) -> float | None:
    try:
        return haversine_km(o1.latitude, o1.longitude, o2.latitude, o2.longitude) * 1000.0
    except Exception:
        return None

def match_confidence(a: DiscoveryObservation, b: DiscoveryObservation) -> str:
    if a.source_id and b.source_id and a.source == b.source and a.source_id == b.source_id:
        return CONF_EXACT
    if _norm(a.normalized_name) and _norm(a.normalized_name) == _norm(b.normalized_name):
        dist = _distance_m(a, b)
        if dist is not None and dist <= 60:
            # same name close -> high if brand/phone corroborates else medium
            if _phones_match(a.phone, b.phone) or (_norm(a.website) and _norm(a.website) == _norm(b.website)):
                return CONF_HIGH
            return CONF_HIGH
        if dist is not None and dist <= 150:
            # same name but further -> medium (maybe chain)
            return CONF_MEDIUM
        return CONF_LOW
    # token jaccard
    ta, tb = _token_set(a.normalized_name or a.name), _token_set(b.normalized_name or b.name)
    jac = _jaccard(ta, tb)
    dist = _distance_m(a, b)
    if jac >= 0.6 and dist is not None and dist <= 100:
        return CONF_MEDIUM
    if jac >= 0.4 and dist is not None and dist <= 60:
        return CONF_LOW
    return CONF_UNMATCHED

@dataclass
class CanonicalBusiness:
    name: str
    normalized_name: str
    latitude: float
    longitude: float
    category_code: str
    sources: list[str] = field(default_factory=list)
    source_ids: dict = field(default_factory=dict)
    observations: list[DiscoveryObservation] = field(default_factory=list)
    confidence: str = CONF_UNMATCHED
    address: str | None = None
    phone: str | None = None
    website: str | None = None

def deduplicate(observations: list[DiscoveryObservation], merge_threshold: str = CONF_MEDIUM) -> list[CanonicalBusiness]:
    """Cluster observations into canonical businesses.

    Only merges at >= merge_threshold confidence (default MEDIUM). EXACT/HIGH/MEDIUM
    are merged; LOW/UNMATCHED remain separate.
    """
    order = {CONF_EXACT: 4, CONF_HIGH: 3, CONF_MEDIUM: 2, CONF_LOW: 1, CONF_UNMATCHED: 0}
    thresh = order.get(merge_threshold, 2)
    canonicals: list[CanonicalBusiness] = []
    used = [False] * len(observations)
    for i, obs in enumerate(observations):
        if used[i]:
            continue
        cluster = [obs]
        used[i] = True
        for j in range(i + 1, len(observations)):
            if used[j]:
                continue
            other = observations[j]
            conf = match_confidence(obs, other)
            if order.get(conf, 0) >= thresh:
                # Re-check distance for MEDIUM: ensure still close
                cluster.append(other)
                used[j] = True
        # Build canonical from cluster (first obs wins for name/category; enrich phone/website)
        primary = cluster[0]
        sources = sorted({o.source for o in cluster})
        source_ids = {o.source: o.source_id for o in cluster}
        # Merge metadata
        phone = next((o.phone for o in cluster if o.phone), None)
        website = next((o.website for o in cluster if o.website), None)
        address = next((o.address for o in cluster if o.address), None)
        # Determine cluster confidence as max pair confidence inside cluster
        if len(cluster) == 1:
            conf = CONF_UNMATCHED
        else:
            conf = max((match_confidence(primary, o) for o in cluster[1:]), key=lambda c: order[c])
        canonicals.append(CanonicalBusiness(
            name=primary.name,
            normalized_name=primary.normalized_name,
            latitude=primary.latitude,
            longitude=primary.longitude,
            category_code=primary.category_code,
            sources=sources,
            source_ids=source_ids,
            observations=cluster,
            confidence=conf if len(cluster) > 1 else CONF_UNMATCHED,
            address=address,
            phone=phone,
            website=website,
        ))
    return canonicals
