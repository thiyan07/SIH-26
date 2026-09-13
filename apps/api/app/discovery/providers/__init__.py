"""Provider abstraction — Google Maps + OSM are interchangeable discovery sources."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class DiscoveryObservation:
    source: str
    source_id: str
    name: str
    normalized_name: str
    category_code: str
    latitude: float
    longitude: float
    address: str | None = None
    phone: str | None = None
    website: str | None = None
    rating: float | None = None
    review_count: int | None = None
    source_url: str | None = None
    retrieved_at: str | None = None
    query: str | None = None
    target_locality: str | None = None
    target_category: str | None = None
    provenance: dict = field(default_factory=dict)

@dataclass
class DiscoveryResult:
    query: str
    category: str
    target: dict
    observations: list[DiscoveryObservation]
    results_observed: int
    unique_results: int
    scrolls_attempted: int
    queries_attempted: int
    termination_reason: str
    elapsed_s: float
    mirror: str | None = None
