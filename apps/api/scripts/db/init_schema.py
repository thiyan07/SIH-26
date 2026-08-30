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
        # Business categories (OSM tag mapping + §14 profiles)
        seed_category_profiles(s)
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
