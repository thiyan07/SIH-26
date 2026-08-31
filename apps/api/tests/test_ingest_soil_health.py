"""Soil Health Card (data.gov.in) ingest fail-fast contract + provider health.

The SHC runner must never fabricate soil values: without the free key and a
confirmed resource id it exits 2, writes nothing, and records availability in
the DataSource ledger. The provider registry must admit soil_health geometry
and surface it as key-gated config_missing when the resource id is absent.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_soil_health_runner_fails_fast_without_key_and_resource(session, monkeypatch):
    from app.db.models import DataSource, SoilHealthStatistic
    from scripts.ingest_government.ingest_soil_health import main

    monkeypatch.setattr("scripts.ingest_government.ingest_soil_health.settings.data_gov_api_key", "")
    monkeypatch.setattr("scripts.ingest_government.ingest_soil_health.settings.soil_health_resource", "")
    assert main(["--dry-run"]) == 2
    assert session.query(SoilHealthStatistic).count() == 0
    ds = session.query(DataSource).filter(DataSource.key == "soil_health_datagov").first()
    assert ds is not None
    assert "SOIL_HEALTH_RESOURCE" in ds.freshness_note


def test_soil_health_dry_run_never_writes(session, monkeypatch):
    """Dry-run with a mock fetch must print intent but persist nothing."""
    import json

    from app.db.models import SoilHealthStatistic
    from scripts.ingest_government import ingest_soil_health

    monkeypatch.setattr(ingest_soil_health.settings, "data_gov_api_key", "key-1")
    monkeypatch.setattr(ingest_soil_health.settings, "soil_health_resource", "res-1")

    def fake_fetch(*args, **kwargs):
        return {"records": json.loads(b'[{"state_name":"Tamil Nadu","district_name":"Erode",'
                                      b'"block_name":"Sathyamangalam","village_name":"Sathyamangalam",'
                                      b'"year":"2022","nutrient_type":"Macro","nutrient_name":"Nitrogen",'
                                      b'"level":"Medium","value":"280.5"}]'.decode())}

    monkeypatch.setattr(ingest_soil_health, "_fetch", fake_fetch)
    assert ingest_soil_health.main(["--dry-run", "--state", "Tamil Nadu", "--district", "Erode"]) == 0
    assert session.query(SoilHealthStatistic).count() == 0


def test_soil_health_provider_is_key_gated_and_visible(session, monkeypatch):
    monkeypatch.setattr("app.api.data_sources.settings.data_gov_api_key", "")
    monkeypatch.setattr("app.api.data_sources.settings.soil_health_resource", "")
    d = client.get("/data-sources/providers").json()
    prov = {p["key"]: p for p in d["providers"]}
    soil = prov["soil_health"]
    assert soil["state"] == "config_missing"
    assert "soil_health_resource" in soil["missing_keys"]
    assert soil["rows_in_db"] == 0


def test_soil_health_provider_counts_rows(session, monkeypatch):
    from app.db.models import SoilHealthStatistic

    monkeypatch.setattr("app.api.data_sources.settings.soil_health_resource", "res-1")
    monkeypatch.setattr("app.api.data_sources.settings.data_gov_api_key", "key-1")
    session.add(SoilHealthStatistic(
        state="Tamil Nadu", district="Erode", block="Sathyamangalam",
        village="Sathyamangalam", nutrient_type="Macro", nutrient_name="Nitrogen",
        nutrient_level="Medium", value=280.5, sample_year=2022, level="village",
        source_name="data.gov.in", source_type="government",
        dataset_name="Soil Health Card - Soil Nutrient Analysis",
        confidence="medium", is_estimate=False, is_demo=False,
    ))
    session.commit()
    d = client.get("/data-sources/providers").json()
    prov = {p["key"]: p for p in d["providers"]}
    assert prov["soil_health"]["rows_in_db"] == 1
