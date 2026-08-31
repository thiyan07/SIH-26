"""UDYAM MSME ingest: fast-fail contract + pincode-level honest handling.

The runner must never fabricate MSME units: no key/resource => exit 2,
nothing written, availability recorded in the DataSource ledger. Normalization
must keep pincode granularity, never invent turnover/investment, and only
locate units when a centroid is known.
"""
from __future__ import annotations

import pytest

from app.db.models import DataSource
from app.db.models import UdyamUnit as DU
from scripts.ingest_government import ingest_udyam
from scripts.ingest_government.ingest_udyam import (
    PincodeResolver,
    _normalized_rows,
)


def test_missing_key_fails_fast_without_writing(session, monkeypatch):
    monkeypatch.setattr(
        "scripts.ingest_government.ingest_udyam.settings.data_gov_api_key", "")
    monkeypatch.setattr(
        "scripts.ingest_government.ingest_udyam.settings.udyam_resource", "")
    rc = ingest_udyam.main(["--dry-run"])
    assert rc == 2
    assert session.query(DU).count() == 0
    ds = session.query(DataSource).filter(DataSource.key == "udyam").first()
    assert ds is not None
    assert "DATA_GOV_API_KEY" in ds.freshness_note
    # The runner records that no MSME facts are approximated when unconfigured.
    assert "ever approximated" in ds.freshness_note.lower()


def test_missing_pincode_keeps_null_coords_not_fabricated():
    raw = [{
        "udyam_registration_number": "UDYAM-TN-00-0000001",
        "enterprise_name": "Acme Trading",
        "sector": "Trading",
        "nic_2008": "47110",
        "state": "Tamil Nadu",
        "district": "Erode",
        "pincode": "",
    }]
    rows = _normalized_rows(raw)
    assert len(rows) == 1
    r = rows[0]
    assert r["udyam_number"] == "UDYAM-TN-00-0000001"
    assert r["latitude"] is None
    assert r["longitude"] is None
    assert r["located"] is False
    # No turnover/investment ever introduced.
    assert "turnover" not in r and "investment" not in r


def test_field_aliases_accept_multiple_spellings():
    rec = {
        "udyam_reg_no": "X-1",
        "unit_name": "Bakery",
        "nic_code": "10711",
        "pincode": "638001",
        "dated": "15/06/2026",
    }
    rows = _normalized_rows([rec])
    assert len(rows) == 1
    r = rows[0]
    assert r["udyam_number"] == "X-1"
    assert r["enterprise_name"] == "Bakery"
    assert r["nic_code"] == "10711"
    assert r["pincode"] == "638001"
    assert r["registration_date"].isoformat() == "2026-06-15"


def test_pincode_resolver_located_flag(tmp_path, monkeypatch):
    csvp = tmp_path / "pins.csv"
    csvp.write_text("pincode,latitude,longitude\n638001,11.3400,77.7170\n")
    monkeypatch.setattr(ingest_udyam.settings, "udyam_pincode_directory", str(csvp))
    PincodeResolver._lazy = None
    rec = {"udyam_number": "U-1", "pincode": "638001"}
    rows = _normalized_rows([rec])
    assert rows[0]["located"] is True
    assert rows[0]["latitude"] == pytest.approx(11.34)
    assert rows[0]["longitude"] == pytest.approx(77.717)


def test_clean_and_coerce_date_robustness():
    from scripts.ingest_government.ingest_udyam import _clean, _coerce_date
    assert _clean("  ") is None
    assert _clean(None) is None
    assert _clean(" x ") == "x"
    assert _coerce_date("2026-01-02").isoformat() == "2026-01-02"
    assert _coerce_date("02/01/2026").isoformat() == "2026-01-02"
    assert _coerce_date("garbage") is None


def test_junk_record_skipped_when_no_natural_key():
    rows = _normalized_rows([{"pincode": "638001"}])  # no udyam_number
    assert rows == []
