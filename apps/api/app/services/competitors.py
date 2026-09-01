"""Competitor discovery + analytics service (P0 — exact-location discovery).

This is the orchestration layer for the competitor feature. It:

* **Exact location** — all queries key off latitude/longitude + radius, *never*
  a village/district name (plan §5, §6). The map marker is the source of truth.
* **Live discovery** — competitors come from the Overpass provider (real OSM
  data with provenance), NOT a hard-coded list or a static CSV (plan §1).
* **Geographic TTL cache** — results are cached in the DB by
  source + rounded geo bucket + radius + category, so marker movement re-uses
  nearby fresh results and does not hammer Overpass (plan §17).
* **Fallback** — live Overpass -> fresh DB cache -> stale DB cache (flagged) ->
  ``data_status=UNAVAILABLE`` (plan §16). Competitors are **never fabricated**.
* **Analytics** — ring counts, nearest/mean distance, density, saturation,
  cluster count, brand concentration (plan §13) computed from queried data.
* **Direct / indirect / unrelated** classification from the configurable
  relationship matrix (plan §14).
* **Confidence + freshness + existence status** (plan §9, §10), transparent and
  documented below.
* **Audit** — every fetch records a row in ``data_sync_runs`` (plan §18).

Confidence formula (transparent, deterministic 0..1)
-----------------------------------------------------
    raw = mapped_count_adjusted            map coverage vs radius area
    source_conf = 0.85                     single verified source (OSM ODbL)
    freshness_conf = f(age)                decays from 1.0 at fresh to 0.5 at >365d
    confidence = clamp(raw * source_conf * freshness_conf, 0, 1)

Existence status (plan §10)
---------------------------
    ACTIVE     retrieved within the last 90 days
    RECENT     retrieved within the last 365 days
    STALE      retrieved more than 365 days ago
    UNKNOWN    no retrieval timestamp
We report recency honestly and never invent a verification date.
"""
from __future__ import annotations

import datetime as dt
from typing import Optional

from sqlalchemy import select

from app.catalog.business_categories import default_radius_km, relationship
from app.config import settings
from app.db.models import Business, CompetitorCache, DataSyncRun
from app.geo import find_nearby
from app.providers import geoapify as geoapify_provider
from app.providers import overpass as overpass_provider

RADIUS_RINGS_KM = [0.5, 1.0, 2.0, 3.0, 5.0, 10.0]
EXISTENCE_ACTIVE_DAYS = 90
EXISTENCE_RECENT_DAYS = 365
SOURCE_CONFIDENCE = 0.85  # OSM is a single authoritative-by-community source
DB_FALLBACK_CONFIDENCE = 0.8  # previously-ingested real rows (indexed, point-level)


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _bucket(lat: float, lon: float, bucket_km: int) -> tuple[float, float]:
    """Round to a lat/lon bucket so nearby marker positions share a cache key."""
    deg = bucket_km / 111.0
    return round(lat / deg) * deg, round(lon / deg) * deg


def scope_key(source: str, lat: float, lon: float, radius_m: int, category: str,
              bucket_km: int) -> str:
    lat_c, lon_c = _bucket(lat, lon, bucket_km)
    return f"{source}|{lat_c:.4f}|{lon_c:.4f}|{radius_m}|{category}"


def _coverage_label(count: int, radius_m: int) -> str:
    """A data-completeness label based on mapped volume, not reality."""
    area_km2 = 3.14159 * ((radius_m / 1000.0) ** 2)
    if count == 0:
        return "low"
    if count > 40 or count / max(area_km2, 1.0) > 1.5:
        return "high"
    if count >= 5:
        return "medium"
    return "low"


# ---------------------------------------------------------------------------
# Entity resolution (conservative dedupe) — plan §8
# ---------------------------------------------------------------------------
def _norm(s: Optional[str]) -> str:
    return (s or "").lower().strip()


def _distance_m(p1: tuple[float, float], p2: tuple[float, float]) -> float:
    lat1, lon1 = p1
    lat2, lon2 = p2
    from app.geo import haversine_km
    return haversine_km(lat1, lon1, lat2, lon2) * 1000.0


def dedupe_competitors(pois: list[dict], max_merge_m: float = 60.0) -> list[dict]:
    """Conservatively merge near-identical POIs (same normalized name + close).

    Merging is **conservative**: we only merge when (a) normalized names are
    identical AND (b) coordinates are within ``max_merge_m``. Different names,
    or the same name at clearly different places, are never merged. Ties are
    flagged client-visible via ``possible_duplicate`` rather than guessed.
    """
    merged: list[dict] = []
    used = [False] * len(pois)
    for i, poi in enumerate(pois):
        if used[i]:
            continue
        base = dict(poi)
        base_coord = (poi["latitude"], poi["longitude"])
        base_norm = _norm(poi.get("normalized_name"))
        merged_dists = []
        for j in range(i + 1, len(pois)):
            if used[j]:
                continue
            other = pois[j]
            if _norm(other.get("normalized_name")) != base_norm or base_norm == "":
                continue
            other_coord = (other["latitude"], other["longitude"])
            d = _distance_m(base_coord, other_coord)
            if d <= max_merge_m:
                used[j] = True
                merged_dists.append(d)
                for field in ("phone", "website", "brand", "opening_hours", "address"):
                    if field not in base or not base[field]:
                        if other.get(field):
                            base[field] = other[field]
        base["merged_from"] = len(merged_dists) + 1
        base["possible_duplicate"] = bool(merged_dists)
        merged.append(base)
    return merged


# ---------------------------------------------------------------------------
# Analytics — plan §13
# ---------------------------------------------------------------------------
def _ring_counts(pois: list[dict], lat: float, lon: float, rings_km: list[float]) -> dict[str, int]:
    counts = {}
    for ring in rings_km:
        counts[f"{int(ring * 1000)}m"] = sum(
            1 for p in pois if _distance_m((lat, lon), (p["latitude"], p["longitude"])) <= ring * 1000.0
        )
    return counts


def _cluster_count(pois: list[dict], max_gap_m: float = 400.0) -> int:
    """Greedy single-link cluster count (POIs within gap of an existing cluster)."""
    if not pois:
        return 0
    clusters: list[list[dict]] = []
    for poi in pois:
        coord = (poi["latitude"], poi["longitude"])
        placed = False
        for cl in clusters:
            if any(_distance_m(coord, (m["latitude"], m["longitude"])) <= max_gap_m for m in cl):
                cl.append(poi)
                placed = True
                break
        if not placed:
            clusters.append([poi])
    return len(clusters)


def _brand_concentration(pois: list[dict]) -> dict:
    branded = [p for p in pois if p.get("brand")]
    unique = {p["brand"] for p in branded}
    return {
        "branded_count": len(branded),
        "branded_ratio": round(len(branded) / len(pois), 3) if pois else 0.0,
        "unique_brands": len(unique),
        "brands": sorted(unique)[:8],
    }


def _density_per_km2(count: int, radius_m: int) -> float:
    area = 3.14159 * ((radius_m / 1000.0) ** 2)
    return round(count / area, 3) if area > 0 else 0.0


def compute_analytics(pois: list[dict], lat: float, lon: float, radius_m: int) -> dict:
    dists = [_distance_m((lat, lon), (p["latitude"], p["longitude"])) for p in pois]
    rings = _ring_counts(pois, lat, lon, RADIUS_RINGS_KM)
    nearest = min(dists) if dists else None
    return {
        "search_radius_m": radius_m,
        "count": len(pois),
        "rings": rings,
        "nearest_distance_m": round(nearest, 1) if nearest is not None else None,
        "mean_distance_m": round(sum(dists) / len(dists), 1) if dists else None,
        "density_per_km2": _density_per_km2(len(pois), radius_m),
        "category_saturation": _coverage_label(len(pois), radius_m),
        "competitor_cluster_count": _cluster_count(pois),
        "brand_concentration": _brand_concentration(pois),
    }


def _freshness(queried_at: Optional[dt.datetime]) -> dict:
    if queried_at is None:
        return {"label": "unknown", "age_days": None, "text": "Last verified: Unknown"}
    age_days = max(0.0, (utcnow() - queried_at).total_seconds() / 86400.0)
    if age_days <= 1:
        label, text = "fresh", "Less than a day ago"
    elif age_days <= 7:
        label, text = "recent", f"{int(age_days)} day(s) ago"
    else:
        label, text = "stale", f"{int(age_days)} day(s) ago"
    return {"label": label, "age_days": round(age_days, 1), "text": f"Data updated: {text}"}


def _existence_status(queried_at: Optional[dt.datetime]) -> str:
    if queried_at is None:
        return "UNKNOWN"
    age_days = (utcnow() - queried_at).total_seconds() / 86400.0
    if age_days <= EXISTENCE_ACTIVE_DAYS:
        return "ACTIVE"
    if age_days <= EXISTENCE_RECENT_DAYS:
        return "RECENT"
    return "STALE"


def _freshness_conf(queried_at: Optional[dt.datetime]) -> float:
    if queried_at is None:
        return 0.5
    age_days = max(0.0, (utcnow() - queried_at).total_seconds() / 86400.0)
    return round(max(0.5, min(1.0, 1.0 - age_days / 730.0)), 2)


def confidence(analytics: dict, queried_at: Optional[dt.datetime]) -> dict:
    """Deterministic confidence: coverage * source * freshness (documented above)."""
    coverage_label = analytics["category_saturation"]
    coverage_factor = {"low": 0.45, "medium": 0.72, "high": 0.92}.get(coverage_label, 0.6)
    source_factor = analytics.get("__source_conf_factor", SOURCE_CONFIDENCE)
    score = round(
        min(1.0, max(0.0, coverage_factor * source_factor * _freshness_conf(queried_at))), 3
    )
    if analytics["count"] == 0 and coverage_label == "low":
        score = round(score * 0.6, 3)  # absent data is not evidence of low competition
    return {
        "score": score,
        "label": "low" if score < 0.4 else ("medium" if score < 0.7 else "high"),
        "factors": {
            "coverage": coverage_factor,
            "source": source_factor,
            "freshness": _freshness_conf(queried_at),
        },
    }


def _classify(pois: list[dict], category_code: str) -> tuple[list[dict], list[dict], list[dict]]:
    """Split POIs into direct / indirect / unrelated buckets (plan §14).

    The POI's OSM tag value (e.g. 'supermarket') is first mapped to a GramBiz
    category code (e.g. 'grocery') so the relationship matrix is applied in the
    unified taxonomy, not in raw OSM tag space.
    """
    from app.catalog.business_categories import category_for_osm_tag

    direct, indirect, unrelated = [], [], []
    for p in pois:
        tag_value = (p.get("category") or p.get("subcategory") or "").lower()
        mapped = category_for_osm_tag(tag_value)
        p["grambiz_category"] = mapped
        p["osm_tag_value"] = tag_value
        rel = relationship(category_code, mapped)
        p["relationship"] = rel
        if rel == "direct":
            direct.append(p)
        elif rel == "indirect":
            indirect.append(p)
        else:
            unrelated.append(p)
    return direct, indirect, unrelated


def _data_status(result, fresh_cache, stale_cache, db_pois, allow_stale,
                 geoapify_result=None) -> tuple[str, dict]:
    """Classify data_status and pick the best available payload source.

    Ladder (mission §9 multi-source): live Overpass -> live Geoapify -> fresh
    cache -> DB-backed previously-ingested rows -> stale cache -> UNAVAILABLE.
    Geoapify is an optional secondary live source (only queried when configured
    and Overpass is unavailable). DB rows are real ingests, so ``DB_FALLBACK``
    is an honest fallback, never fabricated data.
    """
    if result is not None and result.pois:
        return "FRESH", {"source": "osm", "mirror": result.mirror, "queried_at": result.queried_at}
    if geoapify_result is not None and geoapify_result.pois:
        return "FRESH", {
            "source": "geoapify", "mirror": "api.geoapify.com",
            "queried_at": geoapify_result.queried_at,
        }
    if fresh_cache is not None:
        return "CACHED", {"source": "cache", "mirror": fresh_cache.mirror, "queried_at": fresh_cache.queried_at}
    if db_pois:
        return "DB_FALLBACK", {"source": "db", "mirror": None, "queried_at": None}
    if result is not None and allow_stale:
        return "FRESH_EMPTY", {"source": "osm", "mirror": result.mirror, "queried_at": result.queried_at}
    if geoapify_result is not None and geoapify_result.pois is not None and allow_stale:
        return "FRESH_EMPTY", {"source": "geoapify", "mirror": "api.geoapify.com", "queried_at": geoapify_result.queried_at}
    if stale_cache is not None and allow_stale:
        return "STALE_CACHE", {"source": "cache", "mirror": stale_cache.mirror, "queried_at": stale_cache.queried_at}
    return "UNAVAILABLE", {"source": None, "mirror": None, "queried_at": None}


def _cache_rows(db, sk: str) -> tuple[Optional[CompetitorCache], Optional[CompetitorCache]]:
    rows = db.execute(
        select(CompetitorCache).where(CompetitorCache.scope_key == sk).order_by(CompetitorCache.queried_at.desc())
    ).scalars().all()
    fresh = stale = None
    ttl = dt.timedelta(hours=settings.competitor_cache_ttl_hours)
    for r in rows:
        if r.queried_at and (utcnow() - r.queried_at) <= ttl:
            fresh = r
            break
    for r in rows:
        if r is not fresh and r.queried_at and (utcnow() - r.queried_at) > ttl:
            stale = r
            break
    return fresh, stale


def _db_business_pois(db, *, latitude, longitude, radius_m, category_code,
                      limit: int = 300) -> list[dict]:
    """DB-backed competitor tier: real previously-ingested Business rows.

    Mirrors the shape emitted by the live Overpass provider so the analytics /
    dedupe / classification pipeline is provider-agnostic. Only REAL rows are
    used (never demo/proxy). This is the graceful fallback when every external
    source is unavailable, and it guarantees no fabrication: a 0 here means
    "nothing previously ingested around this point", never "none exist".
    """
    radius_km = max(0.2, min(float(radius_m) / 1000.0, 20.0))
    rows = find_nearby(
        db, Business, latitude, longitude, radius_km,
        filters={"category_code": category_code},
        limit=limit, real_only=True,
    )
    queried_at = utcnow()
    pois: list[dict] = []
    for b in rows:
        matched = []
        tags = b.tags or {}
        for tag_key in ("shop", "amenity", "office", "healthcare", "craft"):
            if tags.get(tag_key):
                matched.append(f"{tag_key}={tags[tag_key]}")
        pois.append({
            "source": b.source or "osm",
            "source_record_id": f"business/{b.source_id}",
            "element_type": "node",
            "name": b.name,
            "normalized_name": (b.normalized_name or b.name or "").lower().strip(),
            "category": b.subcategory or b.category_code,
            "subcategory": b.subcategory,
            "latitude": b.latitude,
            "longitude": b.longitude,
            "address": b.address,
            "phone": b.phone,
            "website": b.website,
            "brand": b.brand,
            "opening_hours": b.opening_hours,
            "matched_tags": matched,
            "retrieved_at": queried_at.isoformat(),
            "confidence_score": b.confidence_score,
            "verification_status": b.verification_status,
            "first_seen_at": b.first_seen_at.isoformat() if b.first_seen_at else None,
            "last_seen_at": b.last_seen_at.isoformat() if b.last_seen_at else None,
        })
    return pois


def _write_cache(db, sk: str, category: str, lat: float, lon: float, radius_m: int, result) -> CompetitorCache:
    row = db.execute(
        select(CompetitorCache).where(CompetitorCache.scope_key == sk)
    ).scalars().first()
    if row is None:
        row = CompetitorCache(scope_key=sk, source="osm", category_code=category,
                              lat_center=lat, lon_center=lon, radius_m=radius_m,
                              response_ok=True)
        db.add(row)
    row.payload = result.pois
    row.queried_at = result.queried_at
    row.mirror = result.mirror
    row.analyzed_nodes = result.analyzed_nodes
    row.analyzed_ways = result.analyzed_ways
    row.response_ok = True
    return row


def _start_sync(db, sk: str, source: str) -> DataSyncRun:
    run = DataSyncRun(source=source, scope_key=sk, status="running",
                      started_at=utcnow())
    db.add(run)
    db.flush()
    return run


def _finish_sync(db, run: DataSyncRun, *, status: str, fetched: int = 0, inserted: int = 0,
                 updated: int = 0, rejected: int = 0, errors: int = 0, detail: Optional[str] = None):
    run.status = status
    run.completed_at = utcnow()
    run.records_fetched = fetched
    run.records_inserted = inserted
    run.records_updated = updated
    run.records_rejected = rejected
    run.errors = errors
    run.error_detail = detail
    db.flush()


# ---------------------------------------------------------------------------
# Public entrypoint
# ---------------------------------------------------------------------------
def discover_competitors(
    db,
    *,
    latitude: float,
    longitude: float,
    category_code: str,
    radius_m: Optional[int] = None,
    radius_km: Optional[float] = None,
) -> dict:
    """Discover + analyze competitors around an exact location.

    Returns a structured, provenance-bearing result (see response builder below)
    suitable for both the API map layer and the AI evidence context.
    """
    lat, lon = float(latitude), float(longitude)
    r_km = radius_km if radius_km is not None else default_radius_km(category_code)
    if radius_m is not None:
        r_km = radius_m / 1000.0
    r_km = max(0.2, min(float(r_km), 20.0))
    radius_m_int = int(round(r_km * 1000.0))

    bucket_km = settings.competitor_cache_bucket_km
    sk = scope_key("osm", lat, lon, radius_m_int, category_code, bucket_km)

    fresh_cache, stale_cache = _cache_rows(db, sk)
    mirrors = [m.strip() for m in settings.overpass_mirrors.split(",") if m.strip()]
    allow_stale = settings.competitor_allow_stale_on_failure
    # Geoapify is optional; only attempt it when a key is actually configured.
    geoapify_key_disabled = geoapify_provider.api_key(settings) is None

    result = None
    error = None
    geoapify_result = None
    try:
        result = overpass_provider.query(
            lat, lon, radius_m_int, category_code, mirrors=mirrors,
            timeout_s=settings.overpass_timeout_s,
        )
    except overpass_provider.OverpassUnavailable as e:
        error = str(e)

    # Optional secondary live source: Geoapify, only when a key is configured
    # AND Overpass returned nothing usable. Falls through silently otherwise
    # (this is a graceful, honest no-op when no key / not covered by provider).
    if (result is None or not result.pois) and not geoapify_key_disabled:
        try:
            geoapify_result = geoapify_provider.query(
                lat, lon, radius_m_int, category_code,
                key=geoapify_provider.api_key(settings),
                provider_keys=settings.data_provider_keys,
            )
        except geoapify_provider.GeoapifyUnavailable as ge:
            geoapify_error = str(ge)
            if error is None:
                error = geoapify_error

    # DB-backed tier: real previously-ingested competitors (graceful fallback
    # when every external source is unavailable). Never fabricates a result.
    db_pois = _db_business_pois(
        db, latitude=lat, longitude=lon, radius_m=radius_m_int, category_code=category_code,
    )

    status, src_meta = _data_status(
        result, fresh_cache, stale_cache, db_pois, allow_stale, geoapify_result=geoapify_result,
    )

    # Build the final POI list from the best available source.
    pois: list[dict] = []
    queried_at = None
    if status in ("FRESH", "FRESH_EMPTY") and src_meta["source"] == "geoapify":
        pois = geoapify_result.pois
        queried_at = geoapify_result.queried_at
    elif status == "FRESH" or status == "FRESH_EMPTY":
        pois = result.pois
        queried_at = result.queried_at
    elif status == "CACHED":
        pois = fresh_cache.payload or []
        queried_at = fresh_cache.queried_at
    elif status == "DB_FALLBACK":
        pois = db_pois
        queried_at = None
    elif status == "STALE_CACHE":
        pois = stale_cache.payload or []
        queried_at = stale_cache.queried_at

    audit_run = _start_sync(db, sk, src_meta["source"] or "osm")
    if status in ("FRESH", "FRESH_EMPTY") and src_meta["source"] == "geoapify":
        _finish_sync(db, audit_run, status="ok" if status == "FRESH" else "empty",
                     fetched=len(pois), inserted=1 if status == "FRESH" else 0,
                     detail="served from live Geoapify (secondary provider)")
    elif status in ("FRESH", "FRESH_EMPTY") and result:
        _write_cache(db, sk, category_code, lat, lon, radius_m_int, result)
        fetch_success = status == "FRESH" or result.pois
        _finish_sync(db, audit_run, status="ok" if fetch_success else "empty",
                     fetched=len(result.pois), inserted=1 if result.pois else 0,
                     errors=0 if fetch_success else 0)
    elif status == "CACHED":
        _finish_sync(db, audit_run, status="ok", fetched=len(pois), errors=0,
                     detail="served from fresh cache (live fetch skipped)")
    elif status == "DB_FALLBACK":
        _finish_sync(db, audit_run, status="ok", fetched=len(pois), errors=0,
                     detail="served from DB-backed businesses table (external source unavailable)")
    elif status == "STALE_CACHE" or (status == "FRESH_EMPTY" and error and not fresh_cache):
        _finish_sync(db, audit_run, status="stale", fetched=len(pois), errors=1,
                     detail=error or "no fresh result; served stale cache")
    else:
        _finish_sync(db, audit_run, status="unavailable", fetched=0, errors=1,
                     detail=error or "no data source available")

    deduped = dedupe_competitors(pois)
    analytics = compute_analytics(deduped, lat, lon, radius_m_int)
    direct, indirect, unrelated = _classify(deduped, category_code)
    if status == "DB_FALLBACK":
        # Previously-ingested real rows: transparent lower source-confidence.
        _analytics_conf = dict(analytics)
        _analytics_conf["__source_conf_factor"] = DB_FALLBACK_CONFIDENCE
        conf = confidence(_analytics_conf, None)
    else:
        conf = confidence(analytics, queried_at)
    freshness = _freshness(queried_at)

    return {
        "proposed_location": {"latitude": round(lat, 6), "longitude": round(lon, 6)},
        "business_type": category_code,
        "search_radius_m": radius_m_int,
        "data_status": status,
        "competitors": {
            "direct": len(direct),
            "indirect": len(indirect),
            "total_mapped": len(deduped),
            "nearest_distance_m": analytics["nearest_distance_m"],
            "density_per_km2": analytics["density_per_km2"],
            "rings": analytics["rings"],
            "mean_distance_m": analytics["mean_distance_m"],
            "category_saturation": analytics["category_saturation"],
            "competitor_cluster_count": analytics["competitor_cluster_count"],
            "brand_concentration": analytics["brand_concentration"],
        },
        "analytics": analytics,
        "confidence": conf,
        "freshness": freshness,
        "existence_status": _existence_status(queried_at),
        "data": {
            "primary_source": (
                "Geoapify Places API" if src_meta["source"] == "geoapify"
                else "OpenStreetMap (Overpass API)"
            ),
            "source": src_meta["source"],
            "mirror": src_meta["mirror"],
            "retrieved_at": queried_at.isoformat() if queried_at else None,
            "freshness": freshness["label"],
            "confidence": conf["score"],
            "coverage": analytics["category_saturation"],
            "data_status": status,
            "note": (
                "Mapped business data may be incomplete. 0 competitors found means "
                "0 competitors were FOUND IN THE AVAILABLE DATA, not that none exist."
            ),
        },
        "listings": {
            "direct": direct,
            "indirect": indirect,
            "unrelated": unrelated,
        },
    }
