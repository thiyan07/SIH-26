"""Initialize schema and seed baseline/categories/schemes.

Usage: python -m scripts.db.init_schema
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from sqlalchemy import select, text

from app.db.models import (
    Base,
    BusinessCategory,
    DataSource,
    GovernmentScheme,
)
from app.db.session import init_db, session_scope
from app.engines.category_profiles import PROFILE_FIELDS, seed_category_profiles
from app.engines.finance import DEFAULT_SCHEMES

_PROFILE_COLUMNS = ["osm_tags"] + list(PROFILE_FIELDS)


def init_schema():
    init_db()
    with session_scope() as s:
        # Additive columns for pre-existing databases (plan §6 completeness).
        # create_all already includes it on fresh DBs; the ALTERs are no-ops
        # there and only backfill older clusters, for every provenance table.
        for tbl in Base.metadata.sorted_tables:
            if "completeness" in tbl.c:
                s.execute(text(f"ALTER TABLE {tbl.name} ADD COLUMN IF NOT EXISTS completeness FLOAT"))
        # P0 competitor pipeline tables on older clusters (fresh DBs get these
        # via create_all automatically). Kept as raw CREATE TABLE IF NOT EXISTS
        # so a pre-existing DB without the ORM tables picks them up additively.
        s.execute(text(
            "CREATE TABLE IF NOT EXISTS data_sync_runs ("
            " id VARCHAR(36) PRIMARY KEY, created_at TIMESTAMPTZ, updated_at TIMESTAMPTZ,"
            " source VARCHAR(80), scope_key VARCHAR(120), status VARCHAR(20),"
            " started_at TIMESTAMPTZ, completed_at TIMESTAMPTZ,"
            " records_fetched INTEGER, records_inserted INTEGER, records_updated INTEGER,"
            " records_rejected INTEGER, errors INTEGER, error_detail TEXT, metadata_json JSONB"
            ")"
        ))
        s.execute(text("CREATE INDEX IF NOT EXISTS ix_dsr_scope ON data_sync_runs (scope_key, started_at)"))
        s.execute(text(
            "CREATE TABLE IF NOT EXISTS competitor_cache ("
            " id VARCHAR(36) PRIMARY KEY, created_at TIMESTAMPTZ, updated_at TIMESTAMPTZ,"
            " scope_key VARCHAR(160), source VARCHAR(80), category_code VARCHAR(50),"
            " lat_center FLOAT, lon_center FLOAT, radius_m INTEGER,"
            " payload JSONB, queried_at TIMESTAMPTZ, mirror VARCHAR(200),"
            " analyzed_nodes INTEGER, analyzed_ways INTEGER, response_ok BOOLEAN"
            ")"
        ))
        s.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_cc_scope ON competitor_cache (scope_key)"))
        # P0 competitor pipeline: absolute-requirement columns on `businesses`
        # (mission §10). Additive so fresh DBs get them via create_all and older
        # clusters pick them up without a destructive drop.
        for col in (
            "normalized_name", "phone", "website", "opening_hours", "brand",
            "source_updated_at", "first_seen_at", "last_seen_at",
            "confidence_score", "verification_status",
        ):
            if col in ("phone",):
                s.execute(text(f"ALTER TABLE businesses ADD COLUMN IF NOT EXISTS {col} VARCHAR(80)"))
            elif col in ("website",):
                s.execute(text(f"ALTER TABLE businesses ADD COLUMN IF NOT EXISTS {col} VARCHAR(300)"))
            elif col in ("opening_hours",):
                s.execute(text(f"ALTER TABLE businesses ADD COLUMN IF NOT EXISTS {col} VARCHAR(200)"))
            elif col in ("confidence_score",):
                s.execute(text(f"ALTER TABLE businesses ADD COLUMN IF NOT EXISTS {col} DOUBLE PRECISION"))
            elif col in ("normalized_name", "brand", "verification_status"):
                s.execute(text(f"ALTER TABLE businesses ADD COLUMN IF NOT EXISTS {col} VARCHAR(200)"))
            else:
                s.execute(text(f"ALTER TABLE businesses ADD COLUMN IF NOT EXISTS {col} TIMESTAMPTZ"))
        s.execute(text("CREATE INDEX IF NOT EXISTS ix_businesses_normalized_name "
                       "ON businesses (normalized_name)"))
        # Business category profile columns (plan §14) on older clusters
        for col in _PROFILE_COLUMNS:
            s.execute(text(f"ALTER TABLE business_categories ADD COLUMN IF NOT EXISTS {col} JSONB"))
        # Data source why/limitations (plan §27) on older clusters
        s.execute(text("ALTER TABLE data_sources ADD COLUMN IF NOT EXISTS why_used TEXT"))
        s.execute(text("ALTER TABLE data_sources ADD COLUMN IF NOT EXISTS known_limitations JSONB"))
        # RAG chunk portability column (plan §21) + optional pgvector support.
        # The pgvector attempt runs in a nested transaction (savepoint) so an
        # unavailable extension cannot abort the surrounding migration.
        s.execute(text("ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS embedding_json JSONB"))
        try:
            with s.begin_nested():
                s.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                s.execute(text("ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS embedding vector(1024)"))
                s.execute(text("CREATE INDEX IF NOT EXISTS ix_document_chunks_embedding "
                               "ON document_chunks USING hnsw (embedding vector_cosine_ops)"))
        except Exception as exc:  # noqa: BLE001 - pgvector absent in sandbox; embedding_json fallback
            print(f"  (pgvector unavailable; using portable embedding_json: {exc})")
        # Market price history (Phase 4/5): idempotency + history queries are
        # guaranteed at the DB level, not just in ingest scripts. The partial
        # index guards ONLY real rows (NULL/False is_demo), so demo/proxy price
        # rows can never collide with real ones, and demo rows stay ingestable.
        # The variety-wise dataset reports one row per commodity & variety, so
        # variety is part of a row's identity; old clusters get the columns and
        # an upgraded index additively.
        s.execute(text("ALTER TABLE market_prices ADD COLUMN IF NOT EXISTS variety VARCHAR(120)"))
        s.execute(text("ALTER TABLE market_prices ADD COLUMN IF NOT EXISTS grade VARCHAR(80)"))
        s.execute(text("DROP INDEX IF EXISTS uq_market_prices_real_dedupe"))
        s.execute(text(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_market_prices_real_dedupe "
            "ON market_prices (item_name, COALESCE(variety, ''), "
            "market_name, district, reference_date)"
            " WHERE (is_demo IS NOT TRUE)"
        ))
        s.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_market_prices_district_real "
            "ON market_prices (district, reference_date DESC)"
            " WHERE (is_demo IS NOT TRUE)"
        ))
        s.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_market_prices_variety_real "
            "ON market_prices (variety)"
            " WHERE (is_demo IS NOT TRUE)"
        ))
        # National/state indicator time-series (plan: generic fact table for
        # datasets not pinned to one Erode locality) + APMC market-name
        # reference directory. Both are created idempotently so existing
        # clusters pick them up without a destructive drop. The provenance
        # columns mirror the shared ProvenanceMixin.
        s.execute(text(
            "CREATE TABLE IF NOT EXISTS indicator_statistics ("
            "  id VARCHAR(36) PRIMARY KEY,"
            "  created_at TIMESTAMPTZ, updated_at TIMESTAMPTZ,"
            "  indicator VARCHAR(120) NOT NULL, period VARCHAR(80),"
            "  value DOUBLE PRECISION, unit VARCHAR(40),"
            "  state VARCHAR(100), district VARCHAR(100),"
            "  dimension VARCHAR(120), dimension_type VARCHAR(40),"
            "  metadata_json JSONB,"
            "  source_name VARCHAR(200), source_url VARCHAR(500),"
            "  dataset_name VARCHAR(200), source_type VARCHAR(50),"
            "  reference_date DATE, reference_year INTEGER,"
            "  retrieved_at TIMESTAMPTZ, geographic_level VARCHAR(50),"
            "  confidence VARCHAR(20), completeness DOUBLE PRECISION,"
            "  methodology TEXT, is_estimate BOOLEAN, is_demo BOOLEAN"
            ")"
        ))
        s.execute(text(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_indicator_statistics_real_dedupe "
            "ON indicator_statistics (indicator, period, state, dimension)"
            " WHERE (is_demo IS NOT TRUE)"
        ))
        s.execute(text(
            "CREATE TABLE IF NOT EXISTS market_names ("
            "  id VARCHAR(36) PRIMARY KEY,"
            "  created_at TIMESTAMPTZ, updated_at TIMESTAMPTZ,"
            "  state VARCHAR(100), district VARCHAR(100),"
            "  name VARCHAR(160) NOT NULL, metadata_json JSONB,"
            "  source_name VARCHAR(200), source_url VARCHAR(500),"
            "  dataset_name VARCHAR(200), source_type VARCHAR(50),"
            "  reference_date DATE, reference_year INTEGER,"
            "  retrieved_at TIMESTAMPTZ, geographic_level VARCHAR(50),"
            "  confidence VARCHAR(20), completeness DOUBLE PRECISION,"
            "  methodology TEXT, is_estimate BOOLEAN, is_demo BOOLEAN"
            ")"
        ))
        s.execute(text(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_market_names_real_dedupe "
            "ON market_names (state, district, name)"
            " WHERE (is_demo IS NOT TRUE)"
        ))
        # Infrastructure idempotency (Phase 18b): one real facility per
        # (source, source_id). Demo/proxy infra rows are excluded from the
        # guard so they never collide with official ODI/GODL rows.
        s.execute(text(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_infrastructure_real_dedupe "
            "ON infrastructure_points (source_name, source_id)"
            " WHERE (is_demo IS NOT TRUE AND source_id IS NOT NULL)"
        ))
        # UDYAM MSME idempotency (Phase 19 / CSV export): real rows unique per
        # source_key, which is `udyam_number` when present else a deterministic
        # composite-derived key for exports that omit the registration number.
        s.execute(text(
            "ALTER TABLE udyam_units ALTER COLUMN udyam_number DROP NOT NULL"
        ))
        s.execute(text(
            "ALTER TABLE udyam_units ADD COLUMN IF NOT EXISTS "
            "source_key VARCHAR(160)"
        ))
        s.execute(text("DROP INDEX IF EXISTS uq_udyam_real_dedupe"))
        s.execute(text(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_udyam_real_dedupe "
            "ON udyam_units (source_key)"
            " WHERE (is_demo IS NOT TRUE AND source_key IS NOT NULL)"
        ))
        s.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_udyam_district_real "
            "ON udyam_units (district, registration_date DESC)"
            " WHERE (is_demo IS NOT TRUE)"
        ))
        # Industrial aggregates idempotency (Phase 19): one row per
        # (state, district, unit_type, reference_year) for real rows.
        s.execute(text(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_industrial_units_real_dedupe "
            "ON industrial_units (state, district, unit_type, reference_year)"
            " WHERE (is_demo IS NOT NULL AND is_demo IS NOT TRUE)"
        ))
        # Business categories (OSM tag mapping + §14 profiles)
        seed_category_profiles(s)
        # Make the legacy rows visible to the catalog-seeding checks below
        # (this session has autoflush=False).
        s.flush()
        # Fine-grained competitor categories from the configurable catalog
        # (P0): ensure every code the discovery/ingest path can store in
        # `businesses.category_code` exists in `business_categories` (FK
        # target). e.g. pharmacy, bakery, hardware, salon, mobile_shop, ...
        from app.catalog.business_categories import catalog as business_catalog

        for code, entry in business_catalog().items():
            if not s.execute(select(BusinessCategory).where(BusinessCategory.code == code)).scalars().first():
                s.add(BusinessCategory(
                    code=code, name=entry["label"], description=entry["label"],
                    osm_tags={
                        f"{f['key']}={v}": True
                        for f in entry.get("osm", []) if f.get("key") and f.get("values")
                        for v in f["values"]
                    },
                ))
        # Schemes
        for sc in DEFAULT_SCHEMES:
            if not s.execute(select(GovernmentScheme).where(GovernmentScheme.code == sc.code)).scalars().first():
                s.add(GovernmentScheme(
                    code=sc.code, name=sc.name,
                    min_project_cost=sc.min_project_cost, max_project_cost=sc.max_project_cost,
                    max_loan_amount=sc.max_loan_amount, interest_rate=sc.interest_rate,
                    tenure_years=sc.tenure_years, moratorium_months=sc.moratorium_months,
                    margin_pct=sc.margin_pct, moratorium_mode=sc.moratorium_mode,
                    source_url=sc.source_document, scheme_type=sc.code,
                    description=sc.note,
                ))
        # Data sources (plan §27: each includes why_used + known_limitations)
        defaults = [
            ("population_census", "Population (Census 2011)", "demographics", "population_statistics",
             "2011", False, "Census 2011 baseline - historical, not current population",
             "Only reliable village-level population figures available; needed as a baseline demand signal.",
             ["Census data is from 2011 and does not reflect current population growth.",
              "Village-level figures are sometimes village/block centroids rather than exact points."]),
            ("osm_business", "Mapped businesses (OpenStreetMap)", "business", "businesses",
             None, False, "OSM mapped data may be incomplete - © OpenStreetMap contributors",
             "OpenStreetMap is the only freely available place-level business map; used to estimate competition and reach.",
             ["Not all businesses are mapped; absence of a business does not prove it does not exist.",
              "Locations are approximate (building-level) and tag completeness varies by region.",
              "We never treat 'no competitors' as certainty."]),
            ("osm_infrastructure", "Markets & transport (OpenStreetMap)", "infrastructure", "infrastructure_points",
             None, False, "OSM mapped infrastructure may be incomplete - © OpenStreetMap contributors",
             "Mapped markets and transport stops are used to score market accessibility and demand proximity.",
             ["Only markets and transport stops are mapped today; schools/hospitals are not yet ingested.",
              "Points reflect OSM coverage, which can lag real-world openings/closures."]),
            ("hdx_poi", "POI / places of interest (HDX, OSM HOT export)", "business", "businesses",
             None, False, "OpenStreetMap-derived POIs via HOTOSM on HDX - © OpenStreetMap contributors (ODbL)",
             "HDX India POI enriches place-level competitor/infrastructure coverage beyond the base OSM extract, "
             "seeding real businesses (shops, restaurants, services) and amenities (hospitals, schools, fuel, banks).",
             ["POI density reflects OSM coverage which can lag real-world openings/closures.",
              "No 'no competitor' certainty; absence of a POI does not prove a business does not exist."]),
            ("schemes", "Scheme parameters (problem statement)", "finance", "government_schemes",
             None, True, "Demo assumptions based on supplied problem statement",
             "The applied parameters come from the supplied problem statement and drive the financial-plan rules.",
             ["These are assumed demo values, not official scheme documents.",
              "An official document must be ingested (see §21) before real use."]),
        ]
        for key, name, cat, ds, ref_year, is_demo, note, why_used, limits in defaults:
            row = s.execute(select(DataSource).where(DataSource.key == key)).scalars().first()
            if row is None:
                s.add(DataSource(key=key, display_name=name, category=cat, dataset_name=ds,
                                 reference_year=ref_year, is_demo=is_demo, freshness_note=note,
                                 source_type="demo" if is_demo else "government",
                                 why_used=why_used, known_limitations=limits))
            else:
                if not row.why_used:
                    row.why_used = why_used
                if not row.known_limitations:
                    row.known_limitations = limits
    print("Schema initialized.")


if __name__ == "__main__":
    init_schema()
