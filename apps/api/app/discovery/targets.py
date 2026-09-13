"""Search target generator — the replacement for KEY_VILLAGES/TOWNS.

Produces typed DiscoveryTarget records from the administrative hierarchy +
category strategy. Every target flows to Google Maps + OSM.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.discovery.admin import canonical_district, get_localities_for_district
from app.discovery.category_strategy import categories_for_locality
from app.discovery.locality_classifier import classify_locality, discovery_depth_for_class
from app.discovery.query_variants import generate_query_variants


@dataclass
class DiscoveryTarget:
    district: str
    administrative_area: str  # block/taluk
    locality: str
    locality_type: str
    locality_class: str
    latitude: float
    longitude: float
    category: str
    query_variant: str
    query: str
    source: str  # google_maps | osm | both
    priority: str  # high|medium|low
    radius_m: int
    provenance: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "district": self.district,
            "administrative_area": self.administrative_area,
            "locality": self.locality,
            "locality_type": self.locality_type,
            "locality_class": self.locality_class,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "category": self.category,
            "query_variant": self.query_variant,
            "query": self.query,
            "source": self.source,
            "priority": self.priority,
            "radius_m": self.radius_m,
        }

def _priority_for(loc_cls: str, category: str) -> str:
    if loc_cls in ("METRO", "LARGE_CITY"):
        return "high" if category in ("grocery", "pharmacy", "restaurant") else "medium"
    if loc_cls in ("TOWN", "SMALL_TOWN"):
        return "high" if category in ("grocery", "pharmacy") else "medium"
    # village
    return "high" if category in ("grocery", "pharmacy", "fertilizer") else "low"

def generate_targets(
    session: Session,
    state: str = "Tamil Nadu",
    district: str | None = None,
    locality: str | None = None,
    category: str | None = None,
    source: str = "both",
    max_localities: int | None = None,
    dry_run: bool = False,
) -> list[DiscoveryTarget]:
    """Generate discovery targets data-driven from Location hierarchy.

    * district=None or "all" -> all 38 districts
    * locality filter narrows to matching villages
    * category filter narrows to one category
    * source = google_maps|osm|both
    """
    from app.discovery.admin import TN_DISTRICTS_CANONICAL
    targets: list[DiscoveryTarget] = []
    seen_keys: set[tuple[str, str, str]] = set()  # (locality_norm, category, query)

    if district is None or district.lower() == "all":
        districts = list(TN_DISTRICTS_CANONICAL)
    else:
        districts = [canonical_district(district)]

    for dist in districts:
        localities = get_localities_for_district(session, dist)
        # Apply locality filter
        if locality:
            loc_norm = locality.strip().lower()
            localities = [l for l in localities if loc_norm in l.name.lower() or loc_norm in (l.block or "").lower()]
        if max_localities:
            # Prioritize: towns first, then villages (so small sample still covers towns)
            localities = sorted(localities, key=lambda l: 0 if l.type == "town" else 1)[:max_localities]
        dist_count = len(localities)  # approximate for classifier

        for loc in localities:
            if loc.latitude is None or loc.longitude is None:
                continue
            loc_cls = classify_locality(loc, dist_count)
            depth = discovery_depth_for_class(loc_cls)
            cats = categories_for_locality(loc, dist_count)
            if category:
                # filter to requested category (exact match)
                cats = [c for c in cats if c == category]
                if not cats:
                    # allow specialized categories via explicit filter even if village
                    cats = [category]
            # Cap per locality class
            max_targets = depth["max_targets"]
            # Each category yields 1-2 query variants
            loc_targets: list[DiscoveryTarget] = []
            for cat in cats:
                variants = generate_query_variants(loc, cat, max_variants=2)
                for q in variants:
                    key = (loc.normalized_name, cat, q)
                    if key in seen_keys:
                        continue
                    seen_keys.add(key)
                    loc_targets.append(DiscoveryTarget(
                        district=dist,
                        administrative_area=loc.block or dist,
                        locality=loc.name,
                        locality_type=loc.type,
                        locality_class=loc_cls,
                        latitude=loc.latitude,
                        longitude=loc.longitude,
                        category=cat,
                        query_variant=q,
                        query=q,
                        source=source,
                        priority=_priority_for(loc_cls, cat),
                        radius_m=depth["radius_m"],
                        provenance={"geo_precision": loc.geo_precision, "locality_class": loc_cls},
                    ))
                    if len(loc_targets) >= max_targets:
                        break
                if len(loc_targets) >= max_targets:
                    break
            targets.extend(loc_targets)

    # De-duplicate by (query, category) globally if multiple localities share query text rarely
    return targets

def target_identity(target: DiscoveryTarget, provider: str) -> str:
    """Stable identity for a target+provider — used for checkpoint/resume dedup."""
    import hashlib
    key = f"{target.district}|{target.locality}|{target.category}|{target.query}|{provider}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def generate_targets_stream(
    session: Session,
    state: str = "Tamil Nadu",
    district: str | None = None,
    locality: str | None = None,
    category: str | None = None,
    source: str = "both",
    max_localities: int | None = None,
):
    """Yield targets incrementally — district → locality → target — without holding full statewide list."""
    from app.discovery.admin import TN_DISTRICTS_CANONICAL
    seen_keys: set[tuple[str, str, str]] = set()
    districts = [canonical_district(district)] if district and district.lower() != "all" else list(TN_DISTRICTS_CANONICAL)
    for dist in districts:
        localities = get_localities_for_district(session, dist)
        if locality:
            loc_norm = locality.strip().lower()
            localities = [l for l in localities if loc_norm in l.name.lower() or loc_norm in (l.block or "").lower()]
        if max_localities:
            localities = sorted(localities, key=lambda l: 0 if l.type == "town" else 1)[:max_localities]
        dist_count = len(localities)
        for loc in localities:
            if loc.latitude is None or loc.longitude is None:
                continue
            loc_cls = classify_locality(loc, dist_count)
            depth = discovery_depth_for_class(loc_cls)
            cats = categories_for_locality(loc, dist_count)
            if category:
                cats = [c for c in cats if c == category]
                if not cats:
                    cats = [category]
            max_targets = depth["max_targets"]
            loc_targets: list[DiscoveryTarget] = []
            for cat in cats:
                variants = generate_query_variants(loc, cat, max_variants=2)
                for q in variants:
                    key = (loc.normalized_name, cat, q)
                    if key in seen_keys:
                        continue
                    seen_keys.add(key)
                    tgt = DiscoveryTarget(
                        district=dist,
                        administrative_area=loc.block or dist,
                        locality=loc.name,
                        locality_type=loc.type,
                        locality_class=loc_cls,
                        latitude=loc.latitude,
                        longitude=loc.longitude,
                        category=cat,
                        query_variant=q,
                        query=q,
                        source=source,
                        priority=_priority_for(loc_cls, cat),
                        radius_m=depth["radius_m"],
                        provenance={"geo_precision": loc.geo_precision, "locality_class": loc_cls},
                    )
                    loc_targets.append(tgt)
                    if len(loc_targets) >= max_targets:
                        break
                if len(loc_targets) >= max_targets:
                    break
            for t in loc_targets:
                yield t


def schedule_targets(
    targets: list[DiscoveryTarget],
    priority_filter: str | None = None,
    max_targets: int | None = None,
    session=None,
) -> list[DiscoveryTarget]:
    """Deterministic priority scheduler: NOT_SEARCHED > LOW > STALE > HIGH category value, then high>medium>low."""
    # Filter by priority if requested
    if priority_filter and priority_filter != "all":
        targets = [t for t in targets if t.priority == priority_filter]
    # Coverage-aware ordering when session available
    if session is not None:
        try:
            from app.db.models import CoverageAudit
            from sqlalchemy import select
            # Build lookup for coverage status per (district, locality, category, source)
            cov_map: dict[tuple, str] = {}
            rows = session.execute(select(CoverageAudit)).scalars().all()
            for r in rows:
                cov_map[(r.district, r.locality, r.category_code, r.source)] = r.coverage_status
            def _cov_rank(t: DiscoveryTarget) -> int:
                # NOT_SEARCHED (0) highest, then STALE, LOW, PARTIAL, GOOD, ERROR
                status = cov_map.get((t.district, t.locality, t.category, t.source), "NOT_SEARCHED")
                order = {"NOT_SEARCHED": 0, "LOW": 1, "STALE": 2, "PARTIAL": 3, "GOOD": 4, "ERROR": 5}
                return order.get(status, 0)
            # Sort by coverage rank then priority
            pri_order = {"high": 0, "medium": 1, "low": 2}
            targets = sorted(targets, key=lambda t: (_cov_rank(t), pri_order.get(t.priority, 1)))
        except Exception:
            # Fallback to simple priority sort
            pri_order = {"high": 0, "medium": 1, "low": 2}
            targets = sorted(targets, key=lambda t: pri_order.get(t.priority, 2))
    else:
        pri_order = {"high": 0, "medium": 1, "low": 2}
        targets = sorted(targets, key=lambda t: pri_order.get(t.priority, 2))
    if max_targets:
        targets = targets[:max_targets]
    return targets


def estimate_targets(session: Session, district: str | None = None) -> dict:
    """Quick count without materializing all targets — for dry-run headers."""
    from app.discovery.admin import get_all_districts
    if district and district.lower() not in ("all", ""):
        locs = get_localities_for_district(session, district)
        tgts = generate_targets(session, district=district)
        pri = {"high": 0, "medium": 0, "low": 0}
        for t in tgts:
            pri[t.priority] = pri.get(t.priority, 0) + 1
        return {"district": canonical_district(district), "localities": len(locs), "targets": len(tgts), "by_priority": pri}
    # statewide
    all_dists = get_all_districts(session)
    total_loc = sum(d.locality_count for d in all_dists)
    # Don't materialize all statewide targets if huge — estimate via sampling
    sample_targets = generate_targets(session, district="Erode")
    avg_per_locality = len(sample_targets) / max(1, get_all_districts(session)[7].locality_count) if all_dists[7].locality_count else 6  # Erode index 7
    est_targets = int(total_loc * avg_per_locality)
    return {"districts": len(all_dists), "total_localities": total_loc, "estimated_targets": est_targets, "sample_per_locality": round(avg_per_locality, 2)}
