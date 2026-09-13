"""Discovery engine configuration — no scattered constants.

All values are environment-overridable via ``app.config.settings`` or
direct env vars with ``DISCOVERY_`` prefix. Defaults are production-safe.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Category tiers (configurable, not hard-coded per locality type)
# ---------------------------------------------------------------------------
TIER_A_COMMON = [
    "grocery", "pharmacy", "restaurant", "bakery", "tea_shop",
    "salon", "mobile_shop", "electronics", "hardware", "mechanic",
    "textile", "furniture", "clothing", "stationery", "printing",
]

TIER_B_AGRI_RURAL = [
    "fertilizer", "seed_shop", "agricultural_equipment", "tractor_dealer",
    "animal_feed", "irrigation_supplies", "dairy",
]

TIER_C_SPECIALIZED = [
    "hotel", "hospital", "clinic", "diagnostic", "finance", "travel_agency",
    "computer_service", "photography", "laundry", "welding", "auto_parts",
    "tyre_shop", "battery_shop", "home_appliances", "internet_centre",
    "meat_shop", "footwear", "tailoring",
]

# ---------------------------------------------------------------------------
# Locality discovery classes
# ---------------------------------------------------------------------------
LOCALITY_CLASSES = ["METRO", "LARGE_CITY", "TOWN", "SMALL_TOWN", "VILLAGE", "RURAL_LOCALITY"]

# ---------------------------------------------------------------------------
# Query / pagination limits
# ---------------------------------------------------------------------------
@dataclass
class DiscoveryConfig:
    # -- Google Maps adaptive discovery --
    max_results_per_query: int = int(os.getenv("DISCOVERY_MAX_RESULTS", "60"))
    max_scrolls: int = int(os.getenv("DISCOVERY_MAX_SCROLLS", "12"))
    min_scrolls: int = int(os.getenv("DISCOVERY_MIN_SCROLLS", "3"))
    plateau_threshold: int = int(os.getenv("DISCOVERY_PLATEAU_THRESHOLD", "2"))
    plateau_min_new: int = int(os.getenv("DISCOVERY_PLATEAU_MIN_NEW", "3"))
    # -- Rate / concurrency (ToS-respecting) --
    concurrency: int = int(os.getenv("DISCOVERY_CONCURRENCY", "3"))
    delay_s: float = float(os.getenv("DISCOVERY_DELAY_S", "1.5"))
    retry_count: int = int(os.getenv("DISCOVERY_RETRY_COUNT", "2"))
    retry_backoff_s: float = float(os.getenv("DISCOVERY_RETRY_BACKOFF_S", "2.0"))
    timeout_s: int = int(os.getenv("DISCOVERY_TIMEOUT_S", "30"))
    # -- Geographic --
    default_radius_m: int = int(os.getenv("DISCOVERY_RADIUS_M", "3000"))
    metro_radius_m: int = int(os.getenv("DISCOVERY_METRO_RADIUS_M", "5000"))
    village_radius_m: int = int(os.getenv("DISCOVERY_VILLAGE_RADIUS_M", "2000"))
    # -- Freshness thresholds (days) --
    fresh_days: int = int(os.getenv("DISCOVERY_FRESH_DAYS", "30"))
    aging_days: int = int(os.getenv("DISCOVERY_AGING_DAYS", "90"))
    stale_days: int = int(os.getenv("DISCOVERY_STALE_DAYS", "180"))
    # -- Coverage --
    coverage_good_threshold: float = float(os.getenv("DISCOVERY_COVERAGE_GOOD", "0.7"))
    coverage_partial_threshold: float = float(os.getenv("DISCOVERY_COVERAGE_PARTIAL", "0.4"))
    # -- Discovery depth per locality class --
    max_targets_per_village: int = int(os.getenv("DISCOVERY_MAX_TARGETS_VILLAGE", "8"))
    max_targets_per_town: int = int(os.getenv("DISCOVERY_MAX_TARGETS_TOWN", "20"))
    max_targets_per_metro: int = int(os.getenv("DISCOVERY_MAX_TARGETS_METRO", "40"))
    # -- Category strategy --
    village_categories: list[str] = field(default_factory=lambda: list(TIER_A_COMMON[:6] + TIER_B_AGRI_RURAL[:3]))
    town_categories: list[str] = field(default_factory=lambda: list(TIER_A_COMMON + TIER_B_AGRI_RURAL[:4]))
    metro_categories: list[str] = field(default_factory=lambda: list(TIER_A_COMMON + TIER_B_AGRI_RURAL + TIER_C_SPECIALIZED[:6]))
    # -- Grid / cell discovery --
    grid_enabled_for: list[str] = field(default_factory=lambda: ["METRO", "LARGE_CITY"])
    grid_cell_km: float = float(os.getenv("DISCOVERY_GRID_CELL_KM", "2.0"))
    max_grid_cells: int = int(os.getenv("DISCOVERY_MAX_GRID_CELLS", "9"))

CONFIG = DiscoveryConfig()

# Backwards-compatible env alias for legacy scraper callers
def get_config() -> DiscoveryConfig:
    return CONFIG
