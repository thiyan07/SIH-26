"""Adaptive category strategy — tiered, configurable, not hardcoded per village.

Rules:
* Village ≠ only grocery+pharmacy. Tier A common + Tier B agri where relevant.
* Town / metro get broader tiers.
* Specialized tier C only where locality size or context justifies it.
"""
from __future__ import annotations

from app.discovery.admin import LocalityRecord
from app.discovery.config import CONFIG, TIER_C_SPECIALIZED
from app.discovery.locality_classifier import classify_locality


def categories_for_locality(loc: LocalityRecord, district_count: int | None = None) -> list[str]:
    """Return category codes tailored to locality size."""
    cls = classify_locality(loc, district_count)
    if cls in ("METRO", "LARGE_CITY"):
        # All common + agri + selected specialized
        return list(CONFIG.metro_categories)
    if cls in ("TOWN", "SMALL_TOWN"):
        return list(CONFIG.town_categories)
    # Village / rural
    # Include agri tier only if block/district suggests agricultural context.
    # Heuristic: districts with >400 villages are likely agrarian plains.
    base = list(CONFIG.village_categories)
    # Ensure at least the TIER_A subset plus a couple agri
    if district_count and district_count > 300:
        # agrarian district -> include fertilizer, seed
        for c in ["fertilizer", "seed_shop"]:
            if c not in base:
                base.append(c)
    return base

def is_category_relevant(category: str, locality_class: str) -> bool:
    """Guard specialized categories from tiny villages."""
    if category in TIER_C_SPECIALIZED and locality_class in ("VILLAGE", "RURAL_LOCALITY"):
        # Only allow specialized in villages if explicitly requested via override;
        # default is to skip to avoid combinatorial explosion.
        return False
    return True
