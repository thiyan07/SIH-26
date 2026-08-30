"""Phase 4: official data.gov.in market-price ingest fast-fail contract.

The official runner must never fabricate prices: no key => exit 2, nothing
written, availability recorded in the DataSource ledger. Field tolerance and
dedupe live with the shared datagov normalizer (test_ingest_government_normalize)
and the DB-level partial unique index (init_schema), covered below.
"""
from __future__ import annotations

import pytest

from app.db.models import DataSource, MarketPrice
from scripts.ingest_government.ingest_market_datagov import main


def test_missing_key_fails_fast_without_writing(session, monkeypatch):
    monkeypatch.setattr("scripts.ingest_government.ingest_market_datagov.settings.data_gov_api_key", "")
    rc = main(["--dry-run"])
    assert rc == 2
    assert session.query(MarketPrice).count() == 0
    ds = session.query(DataSource).filter(DataSource.key == "market_prices_datagov").first()
    assert ds is not None
    assert "API key" in ds.freshness_note


def test_database_index_guard_survives_demo_and_null_is_demo(session):
    from sqlalchemy import text

    idx = session.execute(text(
        "SELECT indexname FROM pg_indexes WHERE indexname = 'uq_market_prices_real_dedupe'"
    )).first() is not None
    assert idx


def test_imd_rainfall_fails_fast_without_key_and_resource(session, monkeypatch):
    from app.db.models import WeatherStatistic
    from scripts.ingest_government.ingest_imd_rainfall import main as imd_main

    monkeypatch.setattr("scripts.ingest_government.ingest_imd_rainfall.settings.data_gov_api_key", "")
    monkeypatch.setattr("scripts.ingest_government.ingest_imd_rainfall.settings.imd_rainfall_resource", "")
    assert imd_main(["--dry-run"]) == 2
    assert session.query(WeatherStatistic).count() == 0
    ds = session.query(DataSource).filter(DataSource.key == "imd_rainfall").first()
    assert ds is not None and "Unavailable" in ds.freshness_note


@pytest.mark.parametrize("is_demo", [False, None])
def test_real_rows_cannot_duplicate_by_key(session, is_demo):
    from datetime import date

    def add(is_demo_v):
        session.add(MarketPrice(
            item_name="milk", category="agriculture", unit="kg",
            modal_price=50.0, min_price=45.0, max_price=55.0,
            market_name="Erode Market", state="Tamil Nadu", district="Erode",
            mandi="Erode Market", reference_date=date(2026, 6, 15),
            source_name="data.gov.in", source_type="government",
            dataset_name="market_prices", confidence="high",
            is_estimate=False, is_demo=is_demo_v,
        ))
        session.commit()

    add(is_demo)
    with pytest.raises(Exception):
        add(is_demo)  # partial unique index (is_demo IS NOT TRUE) rejects the second
    session.rollback()
    assert session.query(MarketPrice).count() == 1
