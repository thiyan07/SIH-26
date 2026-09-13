"""Administrative hierarchy — Tamil Nadu 38 districts, data-driven.

No hardcoded Erode lists. The hierarchy is materialized from the ``locations``
table (LGD 2024 via Bharat Atlas) which is the authoritative district→village
source already ingested statewide. This module normalizes, validates, and
exposes it as typed records.

Design:
* Flexible: not every locality has every field; parent relationships are
  inferred from Location.district / block / village plus metadata_json.
* Authoritative-first: LGD/Bharat Atlas + TNDES handbooks are Tier 1; OSM is
  cross-check only. No fabricated villages.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

# Canonical 38 districts (Revenue Dept, 2024). Order is alphabetical.
TN_DISTRICTS_CANONICAL: list[str] = [
    "Ariyalur", "Chengalpattu", "Chennai", "Coimbatore", "Cuddalore",
    "Dharmapuri", "Dindigul", "Erode", "Kallakurichi", "Kanchipuram",
    "Kanniyakumari", "Karur", "Krishnagiri", "Madurai", "Mayiladuthurai",
    "Nagapattinam", "Namakkal", "Perambalur", "Pudukkottai", "Ramanathapuram",
    "Ranipet", "Salem", "Sivaganga", "Tenkasi", "Thanjavur", "The Nilgiris",
    "Theni", "Thiruvallur", "Thiruvarur", "Thoothukudi", "Tiruchirappalli",
    "Tirunelveli", "Tirupathur", "Tiruppur", "Tiruvannamalai", "Vellore",
    "Villupuram", "Virudhunagar",
]

# LGD / legacy aliases: old name -> canonical
DISTRICT_ALIASES: dict[str, str] = {
    "Tuticorin": "Thoothukudi",
    "Viluppuram": "Villupuram",
    "Tiruvarur": "Thiruvarur",
    "Thiruvallore": "Thiruvallur",
    "Nilgiris": "The Nilgiris",
}

# Reverse map for queries
ALIASES_REVERSE: dict[str, list[str]] = {}
for old, canon in DISTRICT_ALIASES.items():
    ALIASES_REVERSE.setdefault(canon, []).append(old)

def canonical_district(name: str) -> str:
    """Normalize any district spelling to canonical form."""
    n = (name or "").strip()
    if n in TN_DISTRICTS_CANONICAL:
        return n
    if n in DISTRICT_ALIASES:
        return DISTRICT_ALIASES[n]
    # case-insensitive fallback
    low = n.lower()
    for c in TN_DISTRICTS_CANONICAL:
        if c.lower() == low:
            return c
    for old, canon in DISTRICT_ALIASES.items():
        if old.lower() == low:
            return canon
    return n

def district_variants(name: str) -> list[str]:
    canon = canonical_district(name)
    return [canon] + ALIASES_REVERSE.get(canon, [])

def normalize_name(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"\s+", " ", s)
    return s

@dataclass
class DistrictRecord:
    name: str
    normalized_name: str
    code: str | None = None
    locality_count: int = 0

@dataclass
class LocalityRecord:
    name: str
    normalized_name: str
    type: str  # village|town|municipality|corporation|panchayat
    district: str
    taluk: str | None = None
    block: str | None = None
    parent_locality: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    pincode: str | None = None
    source: str | None = None
    source_id: str | None = None
    provenance: dict | None = None
    geo_precision: str | None = None

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "normalized_name": self.normalized_name,
            "type": self.type,
            "district": self.district,
            "taluk": self.taluk,
            "block": self.block,
            "parent_locality": self.parent_locality,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "pincode": self.pincode,
            "source": self.source,
            "source_id": self.source_id,
        }

def _locality_type(row) -> str:
    """Infer locality type from Location fields and metadata."""
    meta = row.metadata_json or {}
    # Bharat Atlas villages are villages; but we classify block HQ as town-ish
    # if it matches common town suffixes or is distinct from village name pattern.
    # For now: village = default, town detection via heuristics.
    # A location that shares name with its block may be the block HQ town.
    block = (row.block or "").strip()
    village = (row.village or "").strip()
    # If village name equals block name, likely the town/panchayat HQ
    if block and village and normalize_name(block) == normalize_name(village):
        return "town"
    # Metadata hint
    if meta.get("sdtname") and meta.get("gp_name") and normalize_name(meta.get("gp_name")) == normalize_name(village):
        # GPs are village panchayats
        return "village"
    return "village"

def get_all_districts(session: Session, include_counts: bool = True) -> list[DistrictRecord]:
    """Return 38 canonical districts with DB counts."""
    from app.db.models import Location
    # Aggregate counts per normalized district from DB — use district_normalized index when available
    counts: dict[str, int] = {}
    if include_counts:
        # Try district_normalized first (indexed, efficient)
        try:
            rows = session.execute(
                select(Location.district_normalized, func.count(Location.id)).where(
                    (Location.is_demo.is_(False) | Location.is_demo.is_(None)),
                    Location.district_normalized.is_not(None),
                ).group_by(Location.district_normalized)
            ).all()
            if rows and any(r[0] for r in rows):
                raw_counts: dict[str, int] = {r[0]: r[1] for r in rows if r[0]}
                for canon in TN_DISTRICTS_CANONICAL:
                    key = normalize_name(canon)
                    counts[canon] = raw_counts.get(key, 0)
            else:
                raise ValueError("no district_normalized data")
        except Exception:
            # Fallback: legacy district column with canonical folding
            rows = session.execute(
                select(Location.district, func.count(Location.id)).where(Location.is_demo.is_(False) | Location.is_demo.is_(None)).group_by(Location.district)
            ).all()
            raw_counts: dict[str, int] = {r[0]: r[1] for r in rows if r[0]}
            for canon in TN_DISTRICTS_CANONICAL:
                c = sum(cnt for k, cnt in raw_counts.items() if canonical_district(k) == canon)
                counts[canon] = c
    result: list[DistrictRecord] = []
    for d in TN_DISTRICTS_CANONICAL:
        result.append(DistrictRecord(
            name=d,
            normalized_name=normalize_name(d),
            code=normalize_name(d).replace(" ", "_"),
            locality_count=counts.get(d, 0),
        ))
    return result


def backfill_district_normalized(session: Session, batch_size: int = 1000) -> int:
    """Backfill district_normalized for existing rows; returns count updated."""
    from app.db.models import Location
    updated = 0
    # Find rows where district_normalized is null but district present
    rows = session.execute(
        select(Location).where(Location.district_normalized.is_(None), Location.district.is_not(None)).limit(batch_size)
    ).scalars().all()
    for r in rows:
        canon = canonical_district(r.district)
        r.district_normalized = normalize_name(canon)
        updated += 1
    if updated:
        session.commit()
    return updated

def get_localities_for_district(
    session: Session,
    district: str,
    limit: int | None = None,
    offset: int = 0,
) -> list[LocalityRecord]:
    """Load localities for a district from Location table — DB-level filtered."""
    from app.db.models import Location
    canon = canonical_district(district)
    norm = normalize_name(canon)
    # Prefer indexed district_normalized when populated; fallback to SQL ILIKE
    try:
        q = select(Location).where(
            (Location.is_demo.is_(False) | Location.is_demo.is_(None)),
            Location.district_normalized == norm,
        )
        rows = session.execute(q).scalars().all()
        if not rows:
            # Fallback if backfill not yet done
            raise ValueError("empty normalized query")
        matched = rows
    except Exception:
        # Legacy path: filter in SQL where possible
        q2 = select(Location).where(
            (Location.is_demo.is_(False) | Location.is_demo.is_(None)),
            Location.district.ilike(f"%{canon}%") if len(canon) > 3 else Location.district.is_not(None),
        )
        all_rows = session.execute(q2).scalars().all()
        matched = [r for r in all_rows if canonical_district(r.district or "") == canon]
        # If alias, also try alias variants in SQL
        if not matched:
            q3 = select(Location).where(
                (Location.is_demo.is_(False) | Location.is_demo.is_(None)),
            )
            all_rows = session.execute(q3).scalars().all()
            matched = [r for r in all_rows if canonical_district(r.district or "") == canon]
    # Pagination
    if offset:
        matched = matched[offset:]
    if limit:
        matched = matched[:limit]
    out: list[LocalityRecord] = []
    for r in matched:
        out.append(LocalityRecord(
            name=r.village or r.block or r.district,
            normalized_name=normalize_name(r.village or r.block or r.district),
            type=_locality_type(r),
            district=canon,
            taluk=r.block,  # block roughly maps to taluk/subdistrict
            block=r.block,
            parent_locality=r.block if (r.village and r.block and r.village != r.block) else None,
            latitude=r.latitude,
            longitude=r.longitude,
            pincode=(r.metadata_json or {}).get("pincode") if isinstance(r.metadata_json, dict) else None,
            source=r.source_name,
            source_id=(r.metadata_json or {}).get("vilcode11") if isinstance(r.metadata_json, dict) else None,
            provenance={
                "source_name": r.source_name,
                "dataset_name": r.dataset_name,
                "source_url": r.source_url,
                "reference_year": r.reference_year,
                "confidence": r.confidence,
            },
            geo_precision=r.geo_precision,
        ))
    return out

def validate_hierarchy(session: Session) -> dict:
    """Return hierarchy health: districts, dupes, orphans."""
    districts = get_all_districts(session, include_counts=True)
    total = sum(d.locality_count for d in districts)
    missing = [d.name for d in districts if d.locality_count == 0]
    # True duplicate: same district, block, village (administrative duplication)
    true_dupes = session.execute(text("""
        SELECT district, block, village, count(*) c FROM locations
        WHERE is_demo IS NOT TRUE
        GROUP BY district, block, village HAVING count(*) > 1
        ORDER BY c DESC LIMIT 5
    """)).fetchall()
    # Diagnostic: same village name in different blocks (legit but useful to know)
    same_name_diff_block = session.execute(text("""
        SELECT district, village, count(DISTINCT block) blk_cnt, count(*) total FROM locations
        WHERE is_demo IS NOT TRUE
        GROUP BY district, village HAVING count(DISTINCT block) > 1
        ORDER BY total DESC LIMIT 5
    """)).fetchall()
    return {
        "total_districts": len(TN_DISTRICTS_CANONICAL),
        "districts_with_data": sum(1 for d in districts if d.locality_count > 0),
        "total_localities": total,
        "districts_missing": missing,
        "true_duplicate_admin_rows": [{"district": r[0], "block": r[1], "village": r[2], "count": r[3]} for r in true_dupes],
        "same_name_different_block": [{"district": r[0], "village": r[1], "block_count": r[2], "total": r[3]} for r in same_name_diff_block],
        # Keep legacy key for backwards compat
        "sample_dupes": [{"district": r[0], "village": r[1], "count": r[2]} for r in session.execute(text("""
            SELECT district, village, count(*) c FROM locations WHERE is_demo IS NOT TRUE GROUP BY district, village HAVING count(*) > 1 ORDER BY c DESC LIMIT 5
        """)).fetchall()],
        "all_38_covered": len(missing) == 0,
    }
