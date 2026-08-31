"""Soil Health Card evidence engine: availability, nutrient summary, risk delta."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.db.models import SoilHealthStatistic
from app.engines.soil import soil_health_evidence
from app.main import app

client = TestClient(app)

ANALYSIS_BODY = {
    "state": "Tamil Nadu", "district": "Erode", "block": "Sathyamangalam",
    "village": "Sathyamangalam", "capital_available": 100000,
    "category_code": "dairy", "language": "en",
}


def _analysis():
    return client.post("/analysis", json=ANALYSIS_BODY).json()


def _soil_row(session, **kw):
    row = SoilHealthStatistic(
        location_id=kw.pop("location_id", "loc_sathya"),
        level="village",
        state="Tamil Nadu", district="Erode",
        nutrient_type="Macro",
        is_demo=kw.pop("is_demo", False),
        source_name="data.gov.in", source_type="government",
        dataset_name="Soil Health Card - Soil Nutrient Analysis",
        confidence="medium", is_estimate=False,
        **kw,
    )
    session.add(row)
    session.flush()
    return row


def test_soil_unavailable_when_no_rows(session):
    ev = soil_health_evidence(session, district="Erode", location_id="loc_sathya")
    assert ev["available"] is False
    assert ev["risk_delta"] == 0.0
    assert "No real Soil Health Card rows" in ev["note"]


def test_soil_deficient_raises_risk_delta(session):
    _soil_row(session, nutrient_name="Nitrogen", nutrient_level="Low",
              value=180.0, sample_year=2022)
    _soil_row(session, nutrient_name="Phosphorus", nutrient_level="Deficient",
              value=9.0, sample_year=2022)
    _soil_row(session, nutrient_name="Potassium", nutrient_level="Medium",
              value=120.0, sample_year=2022)
    ev = soil_health_evidence(session, state="Tamil Nadu", district="Erode",
                              block="Sathyamangalam", village="Sathyamangalam",
                              location_id="loc_sathya")
    assert ev["available"] is True
    assert ev["sample_year"] == 2022
    assert ev["deficient_share"] == pytest.approx(round(2 / 3, 2))
    assert 0 < ev["risk_delta"] <= 12.0
    names = {n["nutrient"] for n in ev["nutrients"]}
    assert names == {"Nitrogen", "Phosphorus", "Potassium"}
    assert "elevated input" in ev["note"]


def test_soil_healthy_nutrient_set_gives_small_relief(session):
    for name, val in [("Nitrogen", 300.0), ("Phosphorus", 25.0), ("Potassium", 150.0),
                      ("Organic Carbon", 0.7), ("pH", 6.8)]:
        _soil_row(session, nutrient_name=name, nutrient_level="High" if name != "pH" else "Neutral",
                  value=val, sample_year=2023)
    ev = soil_health_evidence(session, district="Erode", location_id="loc_sathya")
    assert ev["available"] is True
    assert ev["deficient_share"] == 0.0
    assert ev["risk_delta"] == -3.0


def test_soil_uses_latest_sample_year_only(session):
    _soil_row(session, nutrient_name="Nitrogen", nutrient_level="Low",
              value=170.0, sample_year=2019)
    _soil_row(session, nutrient_name="Nitrogen", nutrient_level="High",
              value=310.0, sample_year=2024)
    ev = soil_health_evidence(session, district="Erode", location_id="loc_sathya")
    n = next(x for x in ev["nutrients"] if x["nutrient"] == "Nitrogen")
    assert n["level"] == "high"
    assert ev["sample_year"] == 2024


def test_soil_unresolved_village_rows_still_counted_by_district(session):
    # no Location row: district admin path keeps the evidence visible
    row = SoilHealthStatistic(
        location_id=None, level="village", state="Tamil Nadu", district="Erode",
        block="Amodhagiri", village="Amodhagiri",
        nutrient_type="Micro", nutrient_name="Zinc", nutrient_level="Low",
        value=0.4, sample_year=2022, is_demo=False,
        source_name="data.gov.in", source_type="government",
        dataset_name="Soil Health Card - Soil Nutrient Analysis",
        confidence="medium", is_estimate=False,
    )
    session.add(row)
    session.flush()
    ev = soil_health_evidence(session, state="Tamil Nadu", district="Erode",
                              block="Amodhagiri", village="Amodhagiri",
                              location_id="loc_sathya")
    assert ev["available"] is True
    assert ev["risk_delta"] > 0


def test_soil_demo_rows_never_enter_scoring(session):
    _soil_row(session, nutrient_name="Nitrogen", nutrient_level="Low",
              value=100.0, sample_year=2022)
    _soil_row(session, nutrient_name="Nitrogen", nutrient_level="Low",
              value=90.0, sample_year=2022, is_demo=True)
    ev = soil_health_evidence(session, district="Erode", location_id="loc_sathya")
    # only the real row counts -> a single deficient nutrient among 1
    assert ev["deficient_share"] == 1.0
    assert ev["records"] == 1


def test_analysis_exposes_soil_and_absent_rows_score_zero(seeded):
    d = _analysis()
    assert "soil" in d
    assert d["soil"]["available"] is False
    assert d["soil"]["risk_delta"] == 0.0


def test_analysis_uses_soil_rows_in_risk(seeded, session):
    session.add(SoilHealthStatistic(
        location_id="loc_sathya", level="village",
        state="Tamil Nadu", district="Erode", block="Sathyamangalam",
        village="Sathyamangalam", nutrient_type="Macro",
        nutrient_name="Nitrogen", nutrient_level="Low", value=180.0, sample_year=2022,
        is_demo=False, source_name="data.gov.in", source_type="government",
        dataset_name="Soil Health Card - Soil Nutrient Analysis",
        confidence="medium", is_estimate=False,
    ))
    session.commit()
    d = _analysis()
    assert d["soil"]["available"] is True
    assert d["soil"]["risk_delta"] > 0
    # the soil note must reach the data_sources ledger
    names = {s["name"] for s in d["data_sources"]}
    assert any("Soil Health Card" in n for n in names)
