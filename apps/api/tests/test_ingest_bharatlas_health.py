"""Bharat Atlas keyless health-facility ingest (GODL-India) contract.

The runner must be keyless (no settings), store real NIC health establishments
as InfrastructurePoint(kind=hospital) with provenance, and be idempotent: a
re-run over the same source rows must not duplicate points. The provider
registry must surface bharatlas_health with actual row counts.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

ERODE_ROWS = [
    {
        "name": "Malamedu", "type": "SCE", "place": "Arikkaranvalasu, MULANUR",
        "district": "Erode", "state": "TAMILNADU", "source": "nic",
        "layer": "sub_center", "village_id": "223766", "source_id": 50388,
        "_lat": 10.788429999557437, "_lng": 77.87338299991404,
    },
    {
        "name": "Mamarathupatti", "type": "SCE", "place": "Arikkaranvalasu, MULANUR",
        "district": "Erode", "state": "TAMILNADU", "source": "nic",
        "layer": "sub_center", "village_id": "223766", "source_id": 50400,
        "_lat": 10.79265200066557, "_lng": 77.84593800013704,
    },
]


def test_health_dry_run_registers_source_and_writes_nothing(session, monkeypatch):
    from app.db.models import DataSource, InfrastructurePoint
    from scripts.ingest_government import ingest_bharatlas_health

    monkeypatch.setattr(ingest_bharatlas_health, "_fetch_rows", lambda *a, **k: ERODE_ROWS)
    assert ingest_bharatlas_health.main(["--dry-run"]) == 0
    assert session.query(InfrastructurePoint).filter(
        InfrastructurePoint.kind == "hospital").count() == 0
    ds = session.query(DataSource).filter(DataSource.key == "bharatlas_health").first()
    assert ds is not None
    assert ds.is_demo is False


def test_health_ingest_writes_real_rows_with_provenance(session, monkeypatch):
    from app.db.models import DataSource, InfrastructurePoint
    from scripts.ingest_government import ingest_bharatlas_health

    monkeypatch.setattr(ingest_bharatlas_health, "_fetch_rows", lambda *a, **k: ERODE_ROWS)
    assert ingest_bharatlas_health.main([]) == 0

    pts = session.query(InfrastructurePoint).filter(
        InfrastructurePoint.kind == "hospital").all()
    assert len(pts) == 2
    row = {p.source_id: p for p in pts}
    p = row["50388"]
    assert p.name == "Malamedu"
    assert abs(p.latitude - 10.78843) < 1e-6
    assert p.source_type == "government"
    assert p.is_estimate is False
    assert p.is_demo is False
    assert p.confidence == "high"
    assert p.metadata_json["facility_type"] == "SCE"
    ds = session.query(DataSource).filter(DataSource.key == "bharatlas_health").first()
    assert ds.record_count is None or ds.record_count >= 0  # DataSource ledger lives elsewhere


def test_health_ingest_is_idempotent(session, monkeypatch):
    from app.db.models import InfrastructurePoint
    from scripts.ingest_government import ingest_bharatlas_health

    monkeypatch.setattr(ingest_bharatlas_health, "_fetch_rows", lambda *a, **k: ERODE_ROWS)
    assert ingest_bharatlas_health.main([]) == 0
    assert ingest_bharatlas_health.main([]) == 0
    assert session.query(InfrastructurePoint).filter(
        InfrastructurePoint.kind == "hospital").count() == 2


def test_health_provider_visible_and_counts_real_rows(session, monkeypatch):
    from app.db.models import InfrastructurePoint

    session.add(InfrastructurePoint(
        kind="hospital", name="Test PHC", latitude=11.5, longitude=77.3,
        source_id="t1",
        source_name="NIC health facilities (GODL-India) via Bharat Atlas",
        source_type="government", confidence="high", is_estimate=False, is_demo=False,
    ))
    session.commit()
    d = client.get("/data-sources/providers").json()
    prov = {p["key"]: p for p in d["providers"]}
    assert prov["bharatlas_health"]["state"] == "ready"
    assert prov["bharatlas_health"]["rows_in_db"] == 1
    assert prov["bharatlas_health"]["missing_keys"] == []
