"""Central source registry — TIER 1-4 hierarchy (Phase 2).

Single source of truth for all data provenance. Do not scatter source priority
rules across engines. Every ingestion adapter must reference this registry.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

TIER1_OFFICIAL = 1
TIER2_GOV_DERIVED = 2
TIER3_GEOSPATIAL = 3
TIER4_SECONDARY = 4

STATUS_REAL = "REAL"
STATUS_OFFICIAL = "OFFICIAL"
STATUS_OPEN_DATA = "OPEN_DATA"
STATUS_HISTORICAL = "HISTORICAL"
STATUS_ESTIMATED = "ESTIMATED"
STATUS_LIMITED = "LIMITED"
STATUS_STALE = "STALE"
STATUS_DEMO = "DEMO"
STATUS_UNAVAILABLE = "UNAVAILABLE"

@dataclass
class SourceDef:
    source_code: str
    name: str
    provider: str
    official_url: str
    data_domain: str
    geographic_scope: str
    geographic_level: str
    temporal_scope: str
    reliability_tier: int
    licensing_notes: str
    refresh_frequency: str
    ingestion_method: str
    provenance_required: list[str] = field(default_factory=list)
    status_default: str = STATUS_REAL
    confidence_default: str = "medium"

# ---------------------------------------------------------------------------
# Source registry — ordered by tier priority
# ---------------------------------------------------------------------------
SOURCES: dict[str, SourceDef] = {}

def _add(s: SourceDef):
    SOURCES[s.source_code] = s

# TIER 1 — Official / authoritative
_add(SourceDef(
    source_code="census_2011",
    name="Census of India 2011 — Primary Census Abstract",
    provider="Office of the Registrar General & Census Commissioner, Govt. of India",
    official_url="https://censusindia.gov.in/census.website/data/census-tables",
    data_domain="population",
    geographic_scope="India → State → District → Taluk → Village",
    geographic_level="village",
    temporal_scope="2011 (HISTORICAL baseline)",
    reliability_tier=TIER1_OFFICIAL,
    licensing_notes="GODL-India; historical — never presented as current",
    refresh_frequency="decennial (static)",
    ingestion_method="DCHB village CSV + ingest_village_census",
    provenance_required=["source_code","source_name","reference_year","retrieved_at","geographic_level","status","confidence"],
    status_default=STATUS_HISTORICAL,
    confidence_default="high",
))
_add(SourceDef(
    source_code="tn_des_statistical_handbook",
    name="Tamil Nadu District Statistical Handbook (DES)",
    provider="Directorate of Economics & Statistics, Govt. of Tamil Nadu",
    official_url="https://www.tn.gov.in/des/hand-book.php",
    data_domain="district_economic_structure",
    geographic_scope="Tamil Nadu → District → Taluk",
    geographic_level="district",
    temporal_scope="2022-24 (annual)",
    reliability_tier=TIER1_OFFICIAL,
    licensing_notes="TN Govt. open publication; district handbook tables",
    refresh_frequency="yearly",
    ingestion_method="PDF table → controlled extraction (future) / API where available",
    provenance_required=["source_url","reference_year","geographic_level","status"],
    status_default=STATUS_HISTORICAL,
))
_add(SourceDef(
    source_code="udyam_official",
    name="UDYAM Registered MSMEs (Ministry of MSME, via data.gov.in)",
    provider="Ministry of Micro, Small & Medium Enterprises, Govt. of India",
    official_url="https://udyamregistration.gov.in / https://data.gov.in/resource/udayam",
    data_domain="registered_msme",
    geographic_scope="India → State → District → Pincode",
    geographic_level="pincode",
    temporal_scope="2020-present (daily updates)",
    reliability_tier=TIER1_OFFICIAL,
    licensing_notes="GODL-India; requires data.gov.in API key; pincode geo (no lat/lng in source)",
    refresh_frequency="daily",
    ingestion_method="data.gov.in Udyam resource → ingest_udyam (pincode centroid geocoding)",
    provenance_required=["source_url","reference_date","geographic_level","status","confidence"],
    status_default=STATUS_REAL,
    confidence_default="medium",
))
_add(SourceDef(
    source_code="soil_health_moafw",
    name="Soil Health Card — Nutrient Analysis (MOAFW)",
    provider="Ministry of Agriculture & Farmers Welfare, Govt. of India",
    official_url="https://data.gov.in/resource/soil-health",
    data_domain="soil_health",
    geographic_scope="India → State → District → Block → Village",
    geographic_level="village",
    temporal_scope="2015-present",
    reliability_tier=TIER1_OFFICIAL,
    licensing_notes="GODL-India; requires data.gov.in key",
    refresh_frequency="yearly (cycle)",
    ingestion_method="data.gov.in Soil Health resource → ingest_soil_health",
    provenance_required=["source_url","reference_year","geographic_level"],
))
_add(SourceDef(
    source_code="market_prices_official",
    name="Agmarknet Mandi Prices (Directorate of Marketing & Inspection, via data.gov.in)",
    provider="Directorate of Marketing & Inspection, Ministry of Agriculture",
    official_url="https://agmarknet.gov.in / https://data.gov.in/resource/agmarknet",
    data_domain="market_prices",
    geographic_scope="India → State → District → Mandi",
    geographic_level="mandi",
    temporal_scope="Daily",
    reliability_tier=TIER1_OFFICIAL,
    licensing_notes="GODL-India; requires data.gov.in key; mandi-level",
    refresh_frequency="daily",
    ingestion_method="data.gov.in Agmarknet resource → ingest_market_datagov / ACROP mirror fallback",
    provenance_required=["source_url","reference_date","geographic_level","confidence"],
    status_default=STATUS_REAL,
))
_add(SourceDef(
    source_code="schemes_official",
    name="Government Schemes (ministry/department official sources)",
    provider="Various — KVIC, MSME, NABARD, TN Industries Dept.",
    official_url="https://myScheme.gov.in / specific GOs",
    data_domain="schemes",
    geographic_scope="India → State → District",
    geographic_level="state",
    temporal_scope="Current (effective date per scheme)",
    reliability_tier=TIER1_OFFICIAL,
    licensing_notes="Official GOs and scheme documents; source_url + effective date required",
    refresh_frequency="as-published",
    ingestion_method="scrape_schemes + manual GO extraction",
    provenance_required=["source_url","source_date","effective_date","status","confidence"],
))
_add(SourceDef(
    source_code="tn_lgd_gis",
    name="Bharat Atlas — Tamil Nadu LGD Villages (official LGD 2024)",
    provider="Bharat Atlas (LGD 2024 centroids, verifiable at bharatlas.com)",
    official_url="https://bharatlas.com / LGD 2024",
    data_domain="administrative",
    geographic_scope="Tamil Nadu → District → Taluk → Village",
    geographic_level="village",
    temporal_scope="2024",
    reliability_tier=TIER1_OFFICIAL,
    licensing_notes="LGD-derived centroids; browser-verifiable; high confidence",
    refresh_frequency="yearly (LGD release)",
    ingestion_method="bharatlas.com/api/v1 → ingest_tn_lgd_villages",
))

# TIER 2 — Government-derived
_add(SourceDef(
    source_code="economic_census",
    name="Economic Census (MoSPI)",
    provider="Ministry of Statistics & Programme Implementation",
    official_url="https://www.mospi.gov.in/economic-census",
    data_domain="establishments_historical",
    geographic_scope="India → State → District",
    geographic_level="district",
    temporal_scope="2013 (6th Census, HISTORICAL)",
    reliability_tier=TIER2_GOV_DERIVED,
    licensing_notes="Historical baseline — not current business count",
    refresh_frequency="~8 years (static)",
    ingestion_method="PDF tables → controlled extraction",
    provenance_required=["reference_year","geographic_level","status"],
    status_default=STATUS_HISTORICAL,
))
_add(SourceDef(
    source_code="industrial_profile_dic",
    name="District Industries Centre (DIC) / MSME Industrial Profile",
    provider="District Industries Centre, Tamil Nadu",
    official_url="https://www.tn.gov.in → DIC district profiles",
    data_domain="industrial_structure",
    geographic_scope="Tamil Nadu → District",
    geographic_level="district",
    temporal_scope="2020-24 (publication year varies)",
    reliability_tier=TIER2_GOV_DERIVED,
    licensing_notes="District industrial profile PDFs; structural context, not current count",
    refresh_frequency="yearly (when published)",
    ingestion_method="PDF → controlled extraction (future)",
    provenance_required=["source_url","reference_year","status"],
    status_default=STATUS_HISTORICAL,
))

# TIER 3 — High-value geospatial discovery
_add(SourceDef(
    source_code="osm_business",
    name="OpenStreetMap — Local Businesses & POIs",
    provider="OpenStreetMap community (Overpass API)",
    official_url="https://www.openstreetmap.org / https://overpass-api.de",
    data_domain="local_businesses",
    geographic_scope="Global → point (lat/lng)",
    geographic_level="point",
    temporal_scope="Near real-time (community edited)",
    reliability_tier=TIER3_GEOSPATIAL,
    licensing_notes="ODbL-1.0; crowd-sourced completeness varies by area; not government data",
    refresh_frequency="weekly (cache TTL 24h)",
    ingestion_method="Overpass API → services/competitors + CompetitorCache",
    provenance_required=["retrieved_at","geographic_level","confidence","status"],
    status_default="REAL",
))
_add(SourceDef(
    source_code="osm_infra",
    name="OpenStreetMap — Infrastructure (markets, transport, health)",
    provider="OpenStreetMap community",
    official_url="https://www.openstreetmap.org",
    data_domain="infrastructure",
    geographic_scope="Global → point",
    geographic_level="point",
    temporal_scope="Near real-time",
    reliability_tier=TIER3_GEOSPATIAL,
    licensing_notes="ODbL-1.0",
    refresh_frequency="weekly",
    ingestion_method="Overpass + ingest_osm + Bharat Atlas for health (GODL-India NIC)",
    provenance_required=["retrieved_at","geographic_level"],
))

# TIER 4 — Carefully validated secondary (only when necessary, never silent)
_add(SourceDef(
    source_code="acrop_mirror",
    name="ACROP — Mandi Price Mirror (public Agmarknet aggregator)",
    provider="ACROP (acrop.app) — Agmarknet mirror",
    official_url="https://acrop.app/prices/<commodity>/tamil-nadu/<district>",
    data_domain="market_prices",
    geographic_scope="Tamil Nadu → District → Mandi",
    geographic_level="mandi",
    temporal_scope="Daily (scraped)",
    reliability_tier=TIER4_SECONDARY,
    licensing_notes="Secondary aggregator of official APMC data; explicitly labelled, never silent override",
    refresh_frequency="daily (scrape)",
    ingestion_method="app/providers/mandi_live.py → live fallback + batch ingest",
    provenance_required=["source_url","reference_date","status","confidence"],
    status_default=STATUS_LIMITED,
    confidence_default="medium",
))

def tier_for(source_code: str) -> int:
    return SOURCES[source_code].reliability_tier if source_code in SOURCES else 99

def is_stronger(new: str, old: str) -> bool:
    """Never overwrite stronger source with weaker tier."""
    return tier_for(new) < tier_for(old)

# Domain → allowed sources in priority order (Phase 3)
DOMAIN_POLICY: dict[str, list[str]] = {
    "local_businesses": ["osm_business", "osm_infra"],
    "registered_msme": ["udyam_official"],
    "district_economic_structure": ["tn_des_statistical_handbook", "industrial_profile_dic", "economic_census"],
    "historical_establishments": ["economic_census"],
    "administrative": ["tn_lgd_gis"],
    "market_prices": ["market_prices_official", "acrop_mirror"],
    "weather": ["weather_imd", "osm_infra"],
    "schemes": ["schemes_official"],
    "soil_health": ["soil_health_moafw"],
    "infrastructure": ["osm_infra", "osm_business"],
}
