"""Locality-size aware discovery — assigns METRO/LARGE_CITY/TOWN/VILLAGE/RURAL.

Primary derivation uses authoritative fields when available:
* geo_precision (corporation/municipality vs village)
* district scale (locality count as population proxy)
* administrative type
Hard-coded geography is a documented fallback only, not the primary signal.
"""
from __future__ import annotations

from app.discovery.admin import LocalityRecord

# Fallback heuristic sets — generic, documented, not expanded per district.
# Primary classification should work without these; they only disambiguate
# borderline towns that are known municipal corporations from census.
METRO_DISTRICTS = {"Chennai"}
# Generic heuristic: districts with >500 localities are large; towns there are TOWN not SMALL_TOWN.
# The explicit LARGE_CITY set is fallback for known corporations when district count alone is ambiguous.
LARGE_CITY_DISTRICTS_FALLBACK = {"Coimbatore", "Madurai", "Tiruchirappalli", "Salem", "Tiruppur", "Tirunelveli", "Thoothukudi", "Vellore", "Thanjavur"}
LARGE_TOWNS_FALLBACK = {"Coimbatore", "Madurai", "Tiruchirappalli", "Salem", "Tiruppur", "Erode", "Vellore", "Thanjavur", "Thoothukudi", "Kanchipuram", "Chengalpattu"}

def classify_locality(loc: LocalityRecord, district_locality_count: int | None = None) -> str:
    """Return one of METRO/LARGE_CITY/TOWN/SMALL_TOWN/VILLAGE/RURAL_LOCALITY.

    Authoritative-first: use geo_precision/type and district scale; fall back to
    known corporation list only when scale heuristic is ambiguous.
    """
    # Metro: Chennai district localities are urban neighborhoods -> METRO (authoritative)
    if loc.district == "Chennai":
        return "METRO"
    # Generic: very sparse districts -> rural regardless of type
    if district_locality_count and district_locality_count < 80:
        if loc.type != "town":
            return "RURAL_LOCALITY"
    # Town handling — generic first
    if loc.type == "town":
        # Generic large-city heuristic: town in a large district (>500 localities)
        # is likely a municipal corporation / large town.
        if district_locality_count and district_locality_count > 800:
            return "LARGE_CITY"
        # Fallback explicit list (documented, not expanded)
        if loc.district in LARGE_CITY_DISTRICTS_FALLBACK or loc.name in LARGE_TOWNS_FALLBACK:
            return "LARGE_CITY"
        if district_locality_count and district_locality_count > 600:
            return "TOWN"
        return "SMALL_TOWN"
    # Village branch — fallback already handled for sparse
    if district_locality_count and district_locality_count < 80:
        return "RURAL_LOCALITY"
    return "VILLAGE"

def discovery_depth_for_class(cls: str) -> dict:
    """Map locality class to search depth hints."""
    mapping = {
        "METRO": {"radius_m": 5000, "max_targets": 40, "use_grid": True, "max_scrolls": 12, "max_results": 60},
        "LARGE_CITY": {"radius_m": 4000, "max_targets": 30, "use_grid": True, "max_scrolls": 10, "max_results": 50},
        "TOWN": {"radius_m": 3000, "max_targets": 20, "use_grid": False, "max_scrolls": 8, "max_results": 40},
        "SMALL_TOWN": {"radius_m": 2500, "max_targets": 14, "use_grid": False, "max_scrolls": 6, "max_results": 30},
        "VILLAGE": {"radius_m": 2000, "max_targets": 8, "use_grid": False, "max_scrolls": 5, "max_results": 20},
        "RURAL_LOCALITY": {"radius_m": 1500, "max_targets": 6, "use_grid": False, "max_scrolls": 3, "max_results": 15},
    }
    return mapping.get(cls, mapping["VILLAGE"])
