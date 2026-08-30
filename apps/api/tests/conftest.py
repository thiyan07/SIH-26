"""Shared pytest fixtures using a dedicated local PostgreSQL test database."""
from __future__ import annotations

import os
import socket

import pytest

_TEST_URL = "postgresql+psycopg://grambiz@/grambiz_test?host=/tmp&port=5433"
os.environ["DATABASE_URL"] = _TEST_URL
os.environ["LLM_PROVIDER"] = "mock"

from app.db import session as db_session  # noqa: E402
from app.db.models import (  # noqa: E402
    Base,
    Business,
    BusinessCategory,
    InfrastructurePoint,
    Location,
    PopulationStatistic,
)


def _socket_available():
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        s.connect("/tmp/.s.PGSQL.5433")
        return True
    except Exception:
        return False
    finally:
        s.close()


@pytest.fixture(scope="session")
def engine():
    if not _socket_available():
        pytest.skip("Local PostgreSQL test DB (port 5433) not available")
    db_session.init_db(_TEST_URL)
    _apply_additive_schema(db_session)
    return db_session.get_engine()


def _apply_additive_schema(mod):
    """Idempotent additive columns for a test DB created before a model change.

    Mirrors `scripts/db/init_schema.py` so pre-existing local clusters pick up
    the plan §6 `completeness` and plan §14 category-profile columns without a
    destructive drop. Scans ORM metadata so every provenance-bearing table
    stays in sync.
    """
    from sqlalchemy import text

    try:
        with mod.session_scope() as s:
            for tbl in Base.metadata.sorted_tables:
                if "completeness" in tbl.c:
                    s.execute(text(f"ALTER TABLE {tbl.name} ADD COLUMN IF NOT EXISTS completeness FLOAT"))
            for col in ["osm_tags", "required_inputs", "demand_signals", "competition_categories",
                        "cost_components", "revenue_components", "risk_factors", "seasonality"]:
                s.execute(text(f"ALTER TABLE business_categories ADD COLUMN IF NOT EXISTS {col} JSONB"))
            s.execute(text("ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS embedding_json JSONB"))
            s.execute(text("ALTER TABLE data_sources ADD COLUMN IF NOT EXISTS why_used TEXT"))
            s.execute(text("ALTER TABLE data_sources ADD COLUMN IF NOT EXISTS known_limitations JSONB"))
    except Exception:  # noqa: BLE001 - a fresh DB already has the columns
        pass


@pytest.fixture()
def seeded(engine):
    with db_session.session_scope() as s:
        for tbl in reversed(Base.metadata.sorted_tables):
            s.execute(tbl.delete())
        loc1 = Location(id="loc_sathya", state="Tamil Nadu", district="Erode",
                        block="Sathyamangalam", village="Sathyamangalam",
                        latitude=11.5056, longitude=77.2390, geo_precision="centroid",
                        source_name="demo", source_type="demo", is_demo=True)
        loc2 = Location(id="loc_peru", state="Tamil Nadu", district="Erode",
                        block="Perundurai", village="Perundurai",
                        latitude=11.2760, longitude=77.5800, geo_precision="centroid",
                        source_name="demo", source_type="demo", is_demo=True)
        s.add_all([loc1, loc2])
        s.flush()
        s.add_all([
            BusinessCategory(id="cat_dairy", code="dairy", name="Dairy"),
            BusinessCategory(id="cat_grocery", code="grocery", name="Grocery/Retail"),
        ])
        s.flush()
        s.add_all([
            Business(id="b1", name="Dairy A", category_code="dairy",
                     latitude=11.5040, longitude=77.2390, source="demo", source_id="1",
                     source_name="demo", source_type="demo", is_demo=True),
            Business(id="b2", name="Dairy B", category_code="dairy",
                     latitude=11.5100, longitude=77.2450, source="demo", source_id="2",
                     source_name="demo", source_type="demo", is_demo=True),
            Business(id="b3", name="Grocery C", category_code="grocery",
                     latitude=11.5150, longitude=77.2500, source="demo", source_id="3",
                     source_name="demo", source_type="demo", is_demo=True),
            Business(id="b4", name="Dup X", category_code="dairy",
                     latitude=11.5060, longitude=77.2395, source="demo", source_id="4",
                     source_name="demo", source_type="demo", is_demo=True),
            Business(id="b5", name="Dup Y", category_code="dairy",
                     latitude=11.5060, longitude=77.2395, source="demo", source_id="5",
                     source_name="demo", source_type="demo", is_demo=True),
        ])
        s.add_all([
            InfrastructurePoint(id="i1", kind="market", name="Sathya Market",
                                latitude=11.5050, longitude=77.2400,
                                source_name="demo", source_type="demo", is_demo=True),
            InfrastructurePoint(id="i2", kind="transport", name="Sathya Bus Stop",
                                latitude=11.5070, longitude=77.2410,
                                source_name="demo", source_type="demo", is_demo=True),
        ])
        s.add(PopulationStatistic(id="p1", location_id="loc_sathya", level="village",
                                  census_year=2011, population=12400, households=3400,
                                  source_name="Census India", source_type="government",
                                  is_estimate=False, is_demo=True))
    return True


@pytest.fixture()
def session(seeded):
    with db_session.session_scope() as s:
        yield s
