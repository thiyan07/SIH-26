"""GramBiz AI database models.

Schema follows the spec (section 9). Coordinates are stored as numeric
lat/lng columns for portability PLUS a PostGIS geometry column where available.
Geospatial queries live in geo.py and use PostGIS with a haversine fallback.

Provenance is embedded via a shared set of columns on every sourced fact table.
"""
from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase

# PostgreSQL JSONB for structured/nested payload columns.
JSONB = JSONB  # type: ignore[assignment,misc]


def gen_uuid() -> str:
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    pass


class PG:
    """Reusable PK/timestamp columns (mixin)."""

    id = Column(String(36), primary_key=True, default=gen_uuid)
    created_at = Column(DateTime(timezone=True), default=dt.datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=dt.datetime.utcnow, onupdate=dt.datetime.utcnow)


class ProvenanceMixin:
    """Shared provenance fields (spec section 3/9)."""

    source_name = Column(String(200), nullable=True)
    # source_url is TEXT (not VARCHAR) because provider place URLs (e.g. Google
    # Maps) routinely exceed a few hundred characters.
    source_url = Column(Text, nullable=True)
    dataset_name = Column(String(200), nullable=True)
    source_type = Column(String(50), nullable=True)  # government|osm|vendor|proxy|demo
    reference_date = Column(Date, nullable=True)
    reference_year = Column(Integer, nullable=True)
    retrieved_at = Column(DateTime(timezone=True), nullable=True)
    geographic_level = Column(String(50), nullable=True)
    confidence = Column(String(20), nullable=True)  # low|medium|high
    completeness = Column(Float, nullable=True)  # 0.0..1.0 record richness (plan §6)
    methodology = Column(Text, nullable=True)
    is_estimate = Column(Boolean, default=False)
    is_demo = Column(Boolean, default=False)


class Location(PG, ProvenanceMixin, Base):
    __tablename__ = "locations"
    state = Column(String(100), nullable=False)
    district = Column(String(100), nullable=False, index=True)
    block = Column(String(100), nullable=True, index=True)
    village = Column(String(120), nullable=True, index=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    geo_precision = Column(String(20), default="point")  # point|centroid|village
    metadata_json = Column(JSONB, nullable=True)

    __table_args__ = (UniqueConstraint("state", "district", "block", "village", name="uq_location_admin"),)


class AdministrativeBoundary(PG, ProvenanceMixin, Base):
    __tablename__ = "administrative_boundaries"
    level = Column(String(30), nullable=False)  # state|district|block|village
    name = Column(String(120), nullable=False, index=True)
    parent_code = Column(String(60), nullable=True)
    code = Column(String(60), nullable=True, index=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    bbox = Column(JSONB, nullable=True)
    metadata_json = Column(JSONB, nullable=True)


class BusinessCategory(PG, Base):
    __tablename__ = "business_categories"
    code = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(120), nullable=False)
    description = Column(Text, nullable=True)
    osm_tags = Column(JSONB, nullable=True)  # mapping for ingestion
    required_inputs = Column(JSONB, nullable=True)  # plan §14: operating-model input fields
    demand_signals = Column(JSONB, nullable=True)   # plan §14: category codes / infra kinds proxying demand
    competition_categories = Column(JSONB, nullable=True)  # plan §14: direct competitor categories
    cost_components = Column(JSONB, nullable=True)  # plan §14: cost item keys
    revenue_components = Column(JSONB, nullable=True)  # plan §14: revenue item keys
    risk_factors = Column(JSONB, nullable=True)     # plan §14: [{factor, level, note}]
    seasonality = Column(JSONB, nullable=True)      # plan §14: {note, considerations}
    is_active = Column(Boolean, default=True)


class Business(PG, ProvenanceMixin, Base):
    """Real business/POI (competitor) records (P0 competitor pipeline).

    Extends the original minimal row with the competitor mission's absolute
    requirement fields (see docs/data/COMPETITOR_DATA_*.md): normalized name,
    contact detail (phone/website/opening_hours/brand), provenance timestamps
    (source_updated_at / first_seen_at / last_seen_at), a transparent
    per-record confidence score, and a verification status. ``geometry`` is an
    optional PostGIS geography point bootstrapped additively when available
    (geo.py falls back to portable haversine otherwise).
    """

    __tablename__ = "businesses"
    name = Column(String(200), nullable=False)
    normalized_name = Column(String(200), nullable=True, index=True)
    category_code = Column(String(50), ForeignKey("business_categories.code"), index=True)
    subcategory = Column(String(120), nullable=True)
    latitude = Column(Float, nullable=False, index=True)
    longitude = Column(Float, nullable=False, index=True)
    address = Column(Text, nullable=True)
    phone = Column(String(80), nullable=True)
    website = Column(String(300), nullable=True)
    opening_hours = Column(String(200), nullable=True)
    brand = Column(String(120), nullable=True)
    source = Column(String(100), nullable=True, index=True)  # provider key, e.g. "osm"
    source_id = Column(String(200), nullable=True, index=True)
    source_updated_at = Column(DateTime(timezone=True), nullable=True)  # source's own freshness
    first_seen_at = Column(DateTime(timezone=True), nullable=True)      # first time we stored it
    last_seen_at = Column(DateTime(timezone=True), nullable=True)       # most recent confirmation
    confidence_score = Column(Float, nullable=True)                      # 0..1 per-record confidence
    verification_status = Column(String(30), nullable=True)  # VERIFIED|PARTIALLY_VERIFIED|UNVERIFIED|BUSINESS_REGISTRATION_SIGNAL
    tags = Column(JSONB, nullable=True)
    metadata_json = Column(JSONB, nullable=True)
    # geospatial lookup done via optional geometry/geography in geo.py (bootstrap scripts/db/postgis.py)

    __table_args__ = (Index("ix_businesses_source_source_id", "source", "source_id"),
                      UniqueConstraint("source", "source_id", name="uq_business_source_id"))


class PopulationStatistic(PG, ProvenanceMixin, Base):
    __tablename__ = "population_statistics"
    location_id = Column(String(36), ForeignKey("locations.id"), nullable=True, index=True)
    level = Column(String(30), nullable=False)  # village|block|district
    census_year = Column(Integer, nullable=False, default=2011)  # always 2011 baseline
    population = Column(Integer, nullable=True)
    households = Column(Integer, nullable=True)
    males = Column(Integer, nullable=True)
    females = Column(Integer, nullable=True)
    sex_ratio = Column(Float, nullable=True)
    literacy = Column(Float, nullable=True)
    workers = Column(Integer, nullable=True)
    non_workers = Column(Integer, nullable=True)
    metadata_json = Column(JSONB, nullable=True)


class MarketPrice(PG, ProvenanceMixin, Base):
    __tablename__ = "market_prices"
    item_name = Column(String(120), nullable=False, index=True)
    category = Column(String(60), nullable=True, index=True)
    unit = Column(String(40), nullable=True)
    min_price = Column(Numeric(12, 2), nullable=True)
    max_price = Column(Numeric(12, 2), nullable=True)
    modal_price = Column(Numeric(12, 2), nullable=True)
    market_name = Column(String(120), nullable=True)
    state = Column(String(100), nullable=True)
    district = Column(String(100), nullable=True)
    mandi = Column(String(120), nullable=True)
    # Variety-wise daily price dataset also publishes the commodity variety and
    # grade per market row; retained so commodity-level granularity is preserved.
    variety = Column(String(120), nullable=True, index=True)
    grade = Column(String(80), nullable=True)

    # Phase 4: idempotency is a DB guarantee. Real rows (is_demo NULL or False)
    # must be unique per item/variety/market/district/date so official re-runs
    # cannot duplicate history; the variety-wise dataset reports one row per
    # commodity & variety, so variety is part of the identity. Demo/proxy rows
    # are deliberately excluded from the guard and never collide with real
    # prices. Existing clusters get the same index additively via
    # scripts/db/init_schema.py.
    __table_args__ = (
        Index(
            "uq_market_prices_real_dedupe",
            "item_name",
            text("COALESCE(variety, '')"),
            "market_name", "district", "reference_date",
            unique=True,
            postgresql_where=text("is_demo IS NOT TRUE"),
        ),
        Index(
            "ix_market_prices_district_real",
            "district", "reference_date",
            postgresql_where=text("is_demo IS NOT TRUE"),
        ),
    )


class AgricultureStatistic(PG, ProvenanceMixin, Base):
    __tablename__ = "agriculture_statistics"
    location_id = Column(String(36), ForeignKey("locations.id"), nullable=True, index=True)
    level = Column(String(30), nullable=True)
    crop = Column(String(120), nullable=True)
    season = Column(String(60), nullable=True)
    area = Column(Float, nullable=True)
    production = Column(Float, nullable=True)
    yield_value = Column(Float, nullable=True)
    metadata_json = Column(JSONB, nullable=True)


class WeatherStatistic(PG, ProvenanceMixin, Base):
    __tablename__ = "weather_statistics"
    location_id = Column(String(36), ForeignKey("locations.id"), nullable=True, index=True)
    level = Column(String(30), nullable=True)
    indicator = Column(String(60), nullable=False)  # rainfall|temperature|etc
    period = Column(String(40), nullable=True)
    value = Column(Float, nullable=True)
    unit = Column(String(20), nullable=True)
    metadata_json = Column(JSONB, nullable=True)


class IndicatorStatistic(PG, ProvenanceMixin, Base):
    """Generic national/state-level indicator time-series.

    Holds official datasets that are NOT pinned to a single Erode locality,
    e.g. national annual pesticide consumption, national textile exports, or
    state-wise retail-outlet class counts. ``state``/``district`` are stored as
    plain text (never fabricated); only the scope the source actually provides
    is recorded. ``period`` is the time bucketing (e.g. "2018-19", "2021-22",
    a year, or a slice). Values are authoritative and never estimated; unit and
    indicator describe what the number means. Real rows are unique per
    (indicator, period, state, dimension) so re-runs are idempotent.
    """

    __tablename__ = "indicator_statistics"
    indicator = Column(String(120), nullable=False, index=True)
    period = Column(String(80), nullable=True, index=True)
    value = Column(Float, nullable=True)
    unit = Column(String(40), nullable=True)
    state = Column(String(100), nullable=True, index=True)
    district = Column(String(100), nullable=True)
    dimension = Column(String(120), nullable=True)  # e.g. outlet class, commodity sub-category
    dimension_type = Column(String(40), nullable=True)  # e.g. class|variety|category
    metadata_json = Column(JSONB, nullable=True)

    __table_args__ = (
        Index(
            "uq_indicator_statistics_real_dedupe",
            "indicator", "period", "state", "dimension",
            unique=True,
            postgresql_where=text("is_demo IS NOT TRUE"),
        ),
    )


class MarketName(PG, ProvenanceMixin, Base):
    """APMC / mandi market-name reference (from the AGMARKNET market directory).

    A dictionary of official market (mandi) names as published by Agmarknet,
    grouped by state and district. Used to normalize/validate ``market_name``
    values on price rows and to expand coverage where a market is known but has
    no price row yet. Real rows are unique per (state, district, name).
    """

    __tablename__ = "market_names"
    state = Column(String(100), nullable=True, index=True)
    district = Column(String(100), nullable=True, index=True)
    name = Column(String(160), nullable=False, index=True)
    metadata_json = Column(JSONB, nullable=True)

    __table_args__ = (
        Index(
            "uq_market_names_real_dedupe",
            "state", "district", "name",
            unique=True,
            postgresql_where=text("is_demo IS NOT TRUE"),
        ),
    )


class SoilHealthStatistic(PG, ProvenanceMixin, Base):
    """Soil Health Card nutrient analysis (Ministry of Agriculture & Farmers Welfare).

    Formatted after the official MOAFW "Soil Nutrient Analysis" data.gov.in
    resource (state/district/block/village + nutrient type/name/level + value).
    Rows are provenance-bearing government data; kept separate from crop
    agriculture statistics so nutrient levels never mix with area/production.
    Location is resolved best-effort by admin path; district text is retained
    so district-scoped queries work even before a village is geo-resolved.
    """

    __tablename__ = "soil_health_statistics"
    location_id = Column(String(36), ForeignKey("locations.id"), nullable=True, index=True)
    level = Column(String(30), nullable=True)  # village|block|district
    state = Column(String(100), nullable=True)
    district = Column(String(100), nullable=True, index=True)
    block = Column(String(100), nullable=True)
    village = Column(String(120), nullable=True)
    nutrient_type = Column(String(60), nullable=True)   # macro/micro/physical
    nutrient_name = Column(String(120), nullable=True)  # e.g. Nitrogen, pH, Organic Carbon
    nutrient_level = Column(String(40), nullable=True)  # low|medium|high|deficient
    value = Column(Float, nullable=True)
    sample_year = Column(Integer, nullable=True)
    metadata_json = Column(JSONB, nullable=True)

    __table_args__ = (
        Index(
            "uq_soil_health_real_dedupe",
            "state", "district", "block", "village",
            "nutrient_type", "nutrient_name", "sample_year",
            unique=True,
            postgresql_where=text("is_demo IS NOT TRUE"),
        ),
        Index(
            "ix_soil_health_district_real",
            "district", "sample_year",
            postgresql_where=text("is_demo IS NOT TRUE"),
        ),
    )


class InfrastructurePoint(PG, ProvenanceMixin, Base):
    __tablename__ = "infrastructure_points"
    kind = Column(String(60), nullable=False, index=True)  # market|school|hospital|bank|transport|road
    name = Column(String(200), nullable=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    source_id = Column(String(200), nullable=True)
    metadata_json = Column(JSONB, nullable=True)

    # DB-level idempotency guard: real rows (is_demo NULL or False) must be
    # unique per (source, source_id) so official re-runs (OSM, GODL-India health
    # facilities via Bharat Atlas) can never duplicate a facility; demo/proxy
    # rows are excluded and never collide. Applied additively to existing
    # clusters via scripts/db/init_schema.py.
    __table_args__ = (
        Index(
            "uq_infrastructure_real_dedupe",
            "source_name", "source_id",
            unique=True,
            postgresql_where=text("is_demo IS NOT TRUE AND source_id IS NOT NULL"),
        ),
    )


class GovernmentScheme(PG, ProvenanceMixin, Base):
    __tablename__ = "government_schemes"
    code = Column(String(50), unique=True, nullable=False)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    implementing_agency = Column(String(200), nullable=True)
    scheme_url = Column(Text, nullable=True)
    scheme_type = Column(String(40), nullable=True)  # subsidy|loan|grant|insurance
    document_id = Column(String(36), nullable=True)
    is_active = Column(Boolean, default=True)
    # Financial parameters
    min_project_cost = Column(Numeric(16, 2), nullable=True)
    max_project_cost = Column(Numeric(16, 2), nullable=True)
    max_loan_amount = Column(Numeric(16, 2), nullable=True)
    interest_rate = Column(Float, nullable=True)
    interest_subsidy_pct = Column(Float, nullable=True)
    tenure_years = Column(Float, nullable=True)
    moratorium_months = Column(Integer, nullable=True)
    margin_pct = Column(Float, nullable=True)
    beneficiary_contribution_pct = Column(Float, nullable=True)
    subsidy_pct = Column(Float, nullable=True)
    moratorium_mode = Column(String(40), default="interest_only_during_moratorium")
    # Eligibility fields
    target_beneficiary_categories = Column(JSONB, nullable=True)  # ["sc_st", "obc", "general", "women", "minority", "ews", "all"]
    eligible_business_types = Column(JSONB, nullable=True)  # ["dairy", "poultry", "grocery", ...] or null for all
    eligible_states = Column(JSONB, nullable=True)  # ["Tamil Nadu", ...] or null for all India
    eligible_districts = Column(JSONB, nullable=True)  # ["Erode", ...] or null for all
    min_age = Column(Integer, nullable=True)
    max_age = Column(Integer, nullable=True)
    min_annual_income = Column(Numeric(16, 2), nullable=True)
    max_annual_income = Column(Numeric(16, 2), nullable=True)
    requires_existing_business = Column(Boolean, nullable=True)  # True = must have existing business
    requires_domicile = Column(Boolean, nullable=True)
    category_eligibility_rules = Column(JSONB, nullable=True)  # freeform eligibility conditions
    required_documents = Column(JSONB, nullable=True)  # list of document names
    application_authority = Column(String(200), nullable=True)  # KVIC / District Industries Centre / Bank
    application_process = Column(Text, nullable=True)
    validity_start_date = Column(Date, nullable=True)
    validity_end_date = Column(Date, nullable=True)
    source_url = Column(Text, nullable=True)
    source_date = Column(Date, nullable=True)
    confidence_level = Column(String(20), nullable=True)  # verified|approximate|demo


class SchemeDocument(PG, ProvenanceMixin, Base):
    __tablename__ = "scheme_documents"
    title = Column(String(300), nullable=False)
    doc_type = Column(String(60), nullable=True)
    url = Column(String(500), nullable=True)
    content_text = Column(Text, nullable=True)
    file_path = Column(String(500), nullable=True)
    embedding_ready = Column(Boolean, default=False)
    metadata_json = Column(JSONB, nullable=True)


class DocumentChunk(PG, Base):
    __tablename__ = "document_chunks"
    document_id = Column(String(36), ForeignKey("scheme_documents.id"), index=True)
    chunk_index = Column(Integer, nullable=True)
    content = Column(Text, nullable=False)
    token_count = Column(Integer, nullable=True)
    embedding_source = Column(String(50), nullable=True)
    embedding_json = Column(JSONB, nullable=True)  # plan §21: portable vector (pgvector column added additively when available)
    metadata_json = Column(JSONB, nullable=True)


class BusinessModel(PG, Base):
    __tablename__ = "business_models"
    category_code = Column(String(50), ForeignKey("business_categories.code"), index=True)
    model_name = Column(String(120), nullable=True)
    inputs_schema = Column(JSONB, nullable=True)
    default_inputs = Column(JSONB, nullable=True)
    formulas = Column(JSONB, nullable=True)
    is_active = Column(Boolean, default=True)


class BusinessCostModel(PG, ProvenanceMixin, Base):
    __tablename__ = "business_cost_models"
    category_code = Column(String(50), nullable=False, index=True)
    cost_item = Column(String(120), nullable=False)
    cost_type = Column(String(40), default="capital")  # capital|equipment|inventory|operating|working|buffer
    amount = Column(Numeric(16, 2), nullable=True)
    metadata_json = Column(JSONB, nullable=True)


class OpportunityScore(PG, Base):
    __tablename__ = "opportunity_scores"
    analysis_id = Column(String(36), index=True)
    location_id = Column(String(36), index=True)
    category_code = Column(String(50), index=True)
    overall_score = Column(Float)
    demand_score = Column(Float)
    competition_score = Column(Float)
    accessibility_score = Column(Float)
    price_score = Column(Float)
    financial_fit_score = Column(Float)
    risk_score = Column(Float)
    confidence_score = Column(Float)
    confidence_label = Column(String(20))
    confidence_factors = Column(JSONB)
    component_breakdown = Column(JSONB)
    recommendation = Column(String(20))  # GO|MODIFY|AVOID
    metadata_json = Column(JSONB)


class RiskScore(PG, Base):
    __tablename__ = "risk_scores"
    analysis_id = Column(String(36), index=True)
    risk_factors = Column(JSONB)
    overall_risk = Column(Float)
    metadata_json = Column(JSONB)


class DataSource(PG, ProvenanceMixin, Base):
    __tablename__ = "data_sources"
    key = Column(String(80), unique=True, nullable=False)
    display_name = Column(String(200), nullable=False)
    category = Column(String(60), nullable=True)
    last_updated = Column(DateTime(timezone=True), nullable=True)
    freshness_note = Column(Text, nullable=True)
    record_count = Column(Integer, nullable=True)
    why_used = Column(Text, nullable=True)             # plan §27: why this data is used
    known_limitations = Column(JSONB, nullable=True)   # plan §27: known caveats per source
    is_active = Column(Boolean, default=True)


class DataSnapshot(PG, Base):
    __tablename__ = "data_snapshots"
    job_name = Column(String(120), nullable=False)
    status = Column(String(20), nullable=False)
    records_ingested = Column(Integer, default=0)
    errors = Column(Integer, default=0)
    log = Column(JSONB, nullable=True)
    started_at = Column(DateTime(timezone=True))
    finished_at = Column(DateTime(timezone=True))


class DataSyncRun(PG, Base):
    """Audit trail for competitor-discovery sync runs (P0).

    One row per Overpass (or other provider) fetch so the competitor pipeline
    is auditable: what was queried, when, how many records were fetched/linked,
    and any errors. Mirrors the DataSnapshot pattern but is scoped to the live
    competitor-discovery path rather than bulk estate ingests.
    """
    __tablename__ = "data_sync_runs"

    source = Column(String(80), nullable=False)        # e.g. "osm"
    scope_key = Column(String(120), nullable=False, index=True)  # source|latbucket|lonbucket|radius|category
    status = Column(String(20), nullable=False)        # running|ok|partial|unavailable
    started_at = Column(DateTime(timezone=True), nullable=False, default=dt.datetime.utcnow)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    records_fetched = Column(Integer, default=0)
    records_inserted = Column(Integer, default=0)
    records_updated = Column(Integer, default=0)
    records_rejected = Column(Integer, default=0)
    errors = Column(Integer, default=0)
    error_detail = Column(Text, nullable=True)
    metadata_json = Column(JSONB, nullable=True)


class CompetitorCache(PG, Base):
    """Geographic TTL cache of competitor-discovery results (P0, §17).

    Keyed by the query scope (source + rounded lat/lon bucket + radius +
    category) so marker movement re-uses nearby in-DB results instead of hitting
    Overpass on every pixel move. ``payload`` holds the normalized competitor
    list; ``queried_at`` is the Overpass retrieval time and drives freshness.
    """
    __tablename__ = "competitor_cache"

    scope_key = Column(String(160), nullable=False, unique=True, index=True)
    source = Column(String(80), nullable=False)
    category_code = Column(String(50), nullable=False, index=True)
    lat_center = Column(Float, nullable=False)
    lon_center = Column(Float, nullable=False)
    radius_m = Column(Integer, nullable=False)
    payload = Column(JSONB, nullable=True)            # normalized competitor POIs
    queried_at = Column(DateTime(timezone=True), nullable=False)
    mirror = Column(String(200), nullable=True)
    analyzed_nodes = Column(Integer, default=0)
    analyzed_ways = Column(Integer, default=0)
    response_ok = Column(Boolean, default=True)


class DataSourceQuality(PG, Base):
    """Source-level quality ledger (plan §10 extension).

    One row per (source key) capturing the Quality of Service dimensions that
    are scored *per source* rather than per analysis run:

      - ``source_quality_score``  0-100 structural soundness (documented,
        licensed, maintained, stable schema)
      - ``freshness_score``       0-100 recency vs today (source cadence aware)
      - ``completeness_score``    0-100 record richness / column coverage
      - ``verification_score``    0-100 how thoroughly we cross-checked the
        source against the authoritative origin
      - ``overall_confidence_score``  weighted blend of the above (0-100)
      - ``confidence_label``      low|medium|high mapped from the overall score
      - ``verification_status``   VERIFIED|PARTIALLY_VERIFIED|UNVERIFIED|CONFLICTING

    These are audit/diagnostic records for the data-sources UI and report, and
    are complementary to (never a replacement for) the per-analysis
    ``data_confidence_score`` computed by ``app.provenance.compute_data_quality``.
    ``score_meta`` carries the transparent per-factor reasons.
    """

    __tablename__ = "data_source_quality"
    source_key = Column(String(80), unique=True, nullable=False, index=True)
    source_name = Column(String(200), nullable=True)
    source_type = Column(String(50), nullable=True)  # government|osm|vendor|proxy|derived
    license_id = Column(String(120), nullable=True)  # e.g. ODbL / GODL-India
    source_quality_score = Column(Float, nullable=True)
    freshness_score = Column(Float, nullable=True)
    completeness_score = Column(Float, nullable=True)
    verification_score = Column(Float, nullable=True)
    overall_confidence_score = Column(Float, nullable=True)
    confidence_label = Column(String(20), nullable=True)  # low|medium|high
    verification_status = Column(String(30), nullable=True)  # VERIFIED|PARTIALLY_VERIFIED|UNVERIFIED|CONFLICTING
    freshness_status = Column(String(20), nullable=True)  # FRESH|RECENT|STALE|VERY_STALE|UNKNOWN
    last_successful_sync = Column(DateTime(timezone=True), nullable=True)
    last_source_update = Column(DateTime(timezone=True), nullable=True)
    record_age_days = Column(Integer, nullable=True)
    geo_resolution = Column(String(30), nullable=True)  # point|pincode|district|state
    cadence = Column(String(40), nullable=True)  # REAL_TIME|NEAR_REAL_TIME|DAILY|WEEKLY|MONTHLY|HISTORICAL|STATIC
    score_meta = Column(JSONB, nullable=True)
    limitations = Column(JSONB, nullable=True)


class UdyamUnit(PG, ProvenanceMixin, Base):
    """MSME units registered under UDYAM (Ministry of MSME, via data.gov.in).

    The official "List of MSME Registered Units under UDYAM" resource ships
    unit-level records with **pincode** (not exact lat/lng) granularity. Per
    the geo-resolution policy, a unit is located at its pincode centroid
    (``pincode_latitude``/``pincode_longitude``) and flagged
    ``geographic_level="pincode"`` with a reduced ``confidence``. Pincode-level
    rows support district/pincode-scoped ``nearby_msmes`` / ``relevant_msmes``
    aggregation and are never counted as point-radius competitors (OSM covers
    that role).

    Unit-level list carries **no turnover / investment / MSME-class** fields,
    so those are kept null and never fabricated. NIC (2008) activity codes are
    retained for category matching; ``udyam_number`` is the natural key.

    Rows that ship with a registration number are unique per ``udyam_number``.
    Some data.gov.in exports of this resource omit ``udyam_number``; for those
    rows a deterministic ``source_key`` derived from (state, district,
    enterprise_name, pincode, registration_date) is used, so official re-runs
    cannot duplicate units.
    """

    __tablename__ = "udyam_units"
    udyam_number = Column(String(120), nullable=True, index=True)
    source_key = Column(String(160), nullable=True, index=True)
    enterprise_name = Column(String(300), nullable=True)
    category = Column(String(40), nullable=True)  # micro|small|medium (when provided)
    sector = Column(String(40), nullable=True)  # manufacturing|services|trading
    nic_code = Column(String(20), nullable=True, index=True)  # NIC-2008 activity code
    state = Column(String(100), nullable=True, index=True)
    district = Column(String(100), nullable=True, index=True)
    pincode = Column(String(20), nullable=True, index=True)
    address = Column(Text, nullable=True)
    registration_date = Column(Date, nullable=True, index=True)
    latitude = Column(Float, nullable=True)  # pincode-centroid latitude (approx)
    longitude = Column(Float, nullable=True)  # pincode-centroid longitude (approx)
    metadata_json = Column(JSONB, nullable=True)

    __table_args__ = (
        Index(
            "uq_udyam_real_dedupe",
            "source_key",
            unique=True,
            postgresql_where=text("is_demo IS NOT TRUE AND source_key IS NOT NULL"),
        ),
        Index(
            "ix_udyam_district_real",
            "district", "registration_date",
            postgresql_where=text("is_demo IS NOT TRUE"),
        ),
    )


class IndustrialUnit(PG, ProvenanceMixin, Base):
    """Registered factories/industrial units (district-scoped aggregates).

    Official factory data (Registered Factories / Annual Survey of Industries)
    is published at **district** granularity - it is deliberately kept as a
    district-level aggregate and is never used in point-radius math because the
    source does not carry exact coordinates. ``count``/``employment`` capacity
    facts (where published by the source, e.g. ASI) are stored when present and
    left null otherwise.

    Real rows are unique per (state, district, unit_type, reference_year) so
    official re-runs are idempotent.
    """

    __tablename__ = "industrial_units"
    state = Column(String(100), nullable=False, index=True)
    district = Column(String(100), nullable=False, index=True)
    unit_type = Column(String(40), nullable=True)  # registered_factory|asi_factory
    count = Column(Integer, nullable=True)
    employment = Column(Integer, nullable=True)
    reference_year = Column(Integer, nullable=True, index=True)
    metadata_json = Column(JSONB, nullable=True)

    __table_args__ = (
        Index(
            "uq_industrial_units_real_dedupe",
            "state", "district", "unit_type", "reference_year",
            unique=True,
            postgresql_where=text("is_demo IS NOT NULL AND is_demo IS NOT TRUE"),
        ),
    )


class AnalysisRun(PG, Base):
    __tablename__ = "analysis_runs"
    state = Column(String(100))
    district = Column(String(100))
    block = Column(String(100), nullable=True)
    village = Column(String(120), nullable=True)
    location_id = Column(String(36), index=True)
    category_code = Column(String(50))
    capital_available = Column(Numeric(16, 2))
    inputs = Column(JSONB)
    result = Column(JSONB)  # full structured evidence + scores + financials
    report_text = Column(Text, nullable=True)
    language = Column(String(10), default="en")


class Report(PG, Base):
    __tablename__ = "reports"
    analysis_id = Column(String(36), index=True)
    language = Column(String(10), default="en")
    content = Column(JSONB)
    markdown = Column(Text, nullable=True)
    html = Column(Text, nullable=True)


class User(PG, Base):
    __tablename__ = "users"
    email = Column(String(200), unique=True, nullable=True)
    display_name = Column(String(200), nullable=True)
    language = Column(String(10), default="en")
    metadata_json = Column(JSONB, nullable=True)

__all__ = [
    "Base",
    "Location",
    "AdministrativeBoundary",
    "BusinessCategory",
    "Business",
    "PopulationStatistic",
    "MarketPrice",
    "AgricultureStatistic",
    "WeatherStatistic",
    "IndicatorStatistic",
    "MarketName",
    "InfrastructurePoint",
    "GovernmentScheme",
    "SchemeDocument",
    "DocumentChunk",
    "BusinessModel",
    "BusinessCostModel",
    "OpportunityScore",
    "RiskScore",
    "DataSource",
    "DataSnapshot",
    "DataSourceQuality",
    "UdyamUnit",
    "IndustrialUnit",
    "DataSyncRun",
    "CompetitorCache",
    "AnalysisRun",
    "Report",
    "User",
    "ProvenanceMixin",
]
