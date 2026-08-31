"""Health-access evidence engine: proximity to the nearest public health facility.

Real rows only (kind=hospital); absence never scores as a fabricated distance.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.db.models import InfrastructurePoint
from app.engines.health import health_access_evidence
from app.main import app
from app.services.analysis import _accessibility_score, _risk_score

client = TestClient(app)

ANALYSIS_BODY = {
    "state": "Tamil Nadu", "district": "Erode", "block": "Sathyamangalam",
    "village": "Sathyamangalam", "capital_available": 100000,
    "category_code": "dairy", "language": "en",
}

NIC_SOURCE = "NIC health facilities (GODL-India) via Bharat Atlas"


def _analysis():
    return client.post("/analysis", json=ANALYSIS_BODY).json()


def _hospital(session, **kw):
    row = InfrastructurePoint(
        kind="hospital",
        name=kw.pop("name", "PHC Sathyamangalam"),
        latitude=kw.pop("latitude", 11.5060),
        longitude=kw.pop("longitude", 77.2405),
        source_name=kw.pop("source_name", NIC_SOURCE),
        source_type=kw.pop("source_type", "government"),
        dataset_name=kw.pop("dataset_name", "nic_health"),
        confidence=kw.pop("confidence", "high"),
        is_demo=kw.pop("is_demo", False),
        **kw,
    )
    session.add(row)
    session.flush()
    return row


def test_health_unavailable_when_no_hospital_rows(session):
    ev = health_access_evidence(session, 11.5056, 77.2390)
    assert ev["available"] is False
    assert ev["nearest_health_km"] is None
    assert ev["health_facilities_nearby"] == 0
    assert ev["nearest_health"] is None


def test_health_finds_nearest_facility_with_provenance(session):
    _hospital(session)
    ev = health_access_evidence(session, 11.5056, 77.2390)
    assert ev["available"] is True
    assert ev["nearest_health_km"] is not None and ev["nearest_health_km"] < 1.0
    assert ev["health_facilities_nearby"] == 1
    assert ev["nearest_health"]["name"] == "PHC Sathyamangalam"
    assert ev["nearest_health"]["source_name"] == NIC_SOURCE
    assert ev["nearest_health"]["confidence"] == "high"


def test_health_never_uses_demo_rows(session):
    _hospital(session, is_demo=True)
    ev = health_access_evidence(session, 11.5056, 77.2390)
    assert ev["available"] is False
    assert ev["nearest_health_km"] is None


def test_accessibility_rewards_near_health_without_penalising_absence():
    assert _accessibility_score({"nearest_market_km": 2.0, "nearest_transport_km": 1.0}) == 85.0
    near = _accessibility_score({"nearest_market_km": 2.0, "nearest_transport_km": 1.0,
                                 "nearest_health_km": 3.0})
    assert near == 93.0  # +8 within 5km
    mid = _accessibility_score({"nearest_market_km": 2.0, "nearest_transport_km": 1.0,
                                "nearest_health_km": 8.0})
    assert mid == 89.0  # +4 within 10km
    far = _accessibility_score({"nearest_market_km": 2.0, "nearest_transport_km": 1.0,
                                "nearest_health_km": 18.0})
    assert far == 79.0  # -6 when only distant facilities exist


def test_risk_penalises_isolated_health_but_not_absence_or_proximity():
    base = {"mapped_competitors_5km": 0, "mapped_competitors_10km": 0}
    no_health_weather = {"available": False}
    no_health = _risk_score(base, no_health_weather, {"nearest_market_km": 3.0})
    close = _risk_score(base, no_health_weather,
                        {"nearest_market_km": 3.0, "nearest_health_km": 4.0})
    far = _risk_score(base, no_health_weather,
                      {"nearest_market_km": 3.0, "nearest_health_km": 16.0})
    assert close == no_health            # proximity is not a penalty
    assert far == no_health + 12         # >15km to a facility raises risk


def test_analysis_exposes_health_evidence_and_provenance(seeded, session):
    d = _analysis()
    assert d["infrastructure"]["nearest_health_km"] is None
    assert d["infrastructure"]["health_available"] is False
    # no facilities -> no fabricated "Health facilities" provenance entry
    assert not any("Health facilities" in s["name"] for s in d["data_sources"])


def test_analysis_uses_real_health_rows_in_scoring(seeded, session):
    _hospital(session)
    session.commit()
    d = _analysis()
    assert d["infrastructure"]["nearest_health_km"] is not None
    assert d["infrastructure"]["nearest_health_km"] < 1.0
    assert d["infrastructure"]["health_available"] is True
    assert d["infrastructure"]["health_facilities_nearby"] == 1
    assert d["infrastructure"]["nearest_health"]["source_name"] == NIC_SOURCE
    names = {s["name"] for s in d["data_sources"]}
    assert "Health facilities" in names
