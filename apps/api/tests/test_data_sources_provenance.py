"""Plan §27: data-source why_used / known_limitations plumbing."""
from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app.db.models import DataSource
from app.main import app

client = TestClient(app)


def _seed_source(session, **extra):
    row = DataSource(
        key="market_prices_demo", display_name="Market Prices (demo)", category="market_prices",
        dataset_name="market_prices", source_type="demo", is_demo=True,
        why_used=extra.pop("why_used", "Only referenced going prices exist; used to score price potential."),
        known_limitations=extra.pop("known_limitations", ["Prices vary by season and market day.", "Only a few items mapped."]),
        **extra,
    )
    session.add(row)
    session.flush()
    return row


def test_data_sources_returns_why_used_and_limitations(session):
    _seed_source(session)
    session.commit()
    d = client.get("/data-sources").json()
    row = next(s for s in d["sources"] if s["key"] == "market_prices_demo")
    assert row["why_used"].startswith("Only referenced going prices")
    assert len(row["known_limitations"]) == 2


def test_known_limitations_stored_as_jsonb_array(session):
    _seed_source(session)
    stored = session.query(DataSource).filter(DataSource.key == "market_prices_demo").first()
    assert isinstance(stored.known_limitations, list)
    assert json.dumps(stored.known_limitations)


def test_missing_limitations_default_to_empty_list(session):
    _seed_source(session, why_used="no caveats here", known_limitations=None)
    session.commit()
    d = client.get("/data-sources").json()
    row = next(s for s in d["sources"] if s["key"] == "market_prices_demo")
    assert row["known_limitations"] == []


def test_seed_defaults_persist_why_used(engine):
    from app.db import session as db_session
    from scripts.db.init_schema import init_schema

    with db_session.session_scope() as s:
        for tbl in [DataSource.__table__]:
            s.execute(tbl.delete())
    init_schema()
    with db_session.session_scope() as s:
        rows = s.query(DataSource).all()
        assert {r.key for r in rows} == {"population_census", "osm_business", "osm_infrastructure", "schemes"}
        for r in rows:
            assert r.why_used
            assert r.known_limitations
