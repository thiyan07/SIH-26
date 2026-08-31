"""Bharat Atlas keyless admin-boundary ingest (LGD) contract.

The runner must be keyless, store real LGD district/block names+codes into
administrative_boundaries with provenance, never write coordinates it does not
have (the API exposes no centroids for these layers), and be idempotent.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

DISTRICT_ROWS = [
    {"dtname": "Erode", "stname": "TAMIL NADU", "stcode11": "33", "dtcode11": "610",
     "year_stat": "2011_c", "dist_lgd": 573, "state_lgd": 33},
]
BLOCK_ROWS = [
    {"state": "TAMIL NADU", "district": "Erode", "stcode11": "33", "dtcode11": "610",
     "blkcode11": "0125", "block_name": "KODUMUDI", "code2011": "336100125",
     "block_lgd": 6164, "dist_lgd": 573, "b_pan_code": 6469, "state_lgd": 33},
    {"state": "TAMIL NADU", "district": "Erode", "stcode11": "33", "dtcode11": "610",
     "blkcode11": "0124", "block_name": "MODAKURICHI", "code2011": "336100124",
     "block_lgd": 6166, "dist_lgd": 573, "b_pan_code": 6471, "state_lgd": 33},
]


def test_boundaries_dry_run_registers_source_and_writes_nothing(session, monkeypatch):
    from app.db.models import AdministrativeBoundary, DataSource
    from scripts.ingest_government import ingest_bharatlas_boundaries as mod

    monkeypatch.setattr(mod, "_district_rows", lambda: DISTRICT_ROWS)
    monkeypatch.setattr(mod, "_block_rows", lambda: BLOCK_ROWS)
    assert mod.main(["--dry-run"]) == 0
    assert session.query(AdministrativeBoundary).count() == 0
    ds = session.query(DataSource).filter(DataSource.key == "bharatlas_boundaries").first()
    assert ds is not None and ds.is_demo is False


def test_boundaries_ingest_writes_district_and_blocks(session, monkeypatch):
    from app.db.models import AdministrativeBoundary
    from scripts.ingest_government import ingest_bharatlas_boundaries as mod

    monkeypatch.setattr(mod, "_district_rows", lambda: DISTRICT_ROWS)
    monkeypatch.setattr(mod, "_block_rows", lambda: BLOCK_ROWS)
    assert mod.main([]) == 0

    rows = session.query(AdministrativeBoundary).all()
    assert len(rows) == 3
    dist = {r.level: r for r in rows}["district"]
    assert dist.name == "Erode"
    assert dist.code == "610"
    assert dist.parent_code == "33"
    assert dist.latitude is None  # API exposes no centroid; never approximated
    blocks = [r for r in rows if r.level == "block"]
    assert {b.name for b in blocks} == {"Kodumudi", "Modakurichi"}
    assert blocks[0].parent_code == "610"
    assert all(b.source_type == "government" and b.is_estimate is False
               and b.is_demo is False for b in blocks)


def test_boundaries_ingest_is_idempotent(session, monkeypatch):
    from app.db.models import AdministrativeBoundary
    from scripts.ingest_government import ingest_bharatlas_boundaries as mod

    monkeypatch.setattr(mod, "_district_rows", lambda: DISTRICT_ROWS)
    monkeypatch.setattr(mod, "_block_rows", lambda: BLOCK_ROWS)
    assert mod.main([]) == 0
    assert mod.main([]) == 0
    assert session.query(AdministrativeBoundary).count() == 3


def test_boundaries_provider_visible(session):
    from app.db.models import AdministrativeBoundary

    session.add(AdministrativeBoundary(
        level="block", name="Sathyamangalam", code="6100120", parent_code="610",
        source_name="LGD administrative boundaries via Bharat Atlas",
        source_type="government", confidence="high", is_estimate=False, is_demo=False,
    ))
    session.commit()
    d = client.get("/data-sources/providers").json()
    prov = {p["key"]: p for p in d["providers"]}
    assert prov["bharatlas_boundaries"]["state"] == "ready"
    assert prov["bharatlas_boundaries"]["rows_in_db"] == 1
