"""Integration: UDYAM location features + proposed-location movement affect analysis."""
from __future__ import annotations

from app.db.models import IndicatorStatistic, UdyamUnit
from app.schemas import AnalysisRequest
from app.services.analysis import run_analysis


def test_location_features_integrated_into_analysis(session):
    # A UDYAM unit near the admin centroid of Sathyamangalam (11.5056, 77.239).
    session.add(UdyamUnit(
        udyam_number="I-1", enterprise_name="Village Dairy Unit",
        sector="manufacturing", nic_code="10501", state="Tamil Nadu",
        district="Erode", pincode="638401", latitude=11.5056,
        longitude=77.239, source_name="UDYAM", source_type="government",
        geographic_level="pincode", confidence="medium", is_demo=False))
    session.commit()

    req = AnalysisRequest(
        state="Tamil Nadu", district="Erode", block="Sathyamangalam",
        village="Sathyamangalam", capital_available=100000,
        category_code="dairy", language="en",
    )
    evidence, _ = run_analysis(session, req)

    assert "location_features" in evidence
    lf = evidence["location_features"]
    assert lf["nearby_msmes"] == 1
    assert lf["geo_resolution"] == "pincode"
    # UDYAM is surfaced in the data-sources ledger.
    keys = [s["name"] for s in evidence["data_sources"]]
    assert any("UDYAM" in k for k in keys)


def test_proposed_location_moves_msme_and_competitor_evidence(session):
    # Dairy competitors near Sathyamangalam admin centroid (11.5056).
    # A unit placed at the *proposed* point (Perundurai ~11.276,77.58), which is
    # ~40km from the admin centroid (Sathyamangalam 11.5056,77.239). Therefore
    # moving the marker to the proposed point changes nearby_msmes (0 -> 1) and
    # the competitor set (Sathya dairy -> none nearby).
    session.add(UdyamUnit(
        udyam_number="M-2", enterprise_name="Dairy B", sector="services",
        nic_code="47211", state="Tamil Nadu", district="Erode", pincode="638011",
        latitude=11.276, longitude=77.58,
        source_name="UDYAM", source_type="government",
        geographic_level="pincode", confidence="medium", is_demo=False))
    session.commit()

    req_admin = AnalysisRequest(
        state="Tamil Nadu", district="Erode", block="Sathyamangalam",
        village="Sathyamangalam", capital_available=100000,
        category_code="dairy", language="en")
    ev_admin, _ = run_analysis(session, req_admin)

    req_proposed = AnalysisRequest(
        state="Tamil Nadu", district="Erode", block="Sathyamangalam",
        village="Sathyamangalam", capital_available=100000,
        category_code="dairy", language="en",
        proposed_latitude=11.276, proposed_longitude=77.58)
    ev_proposed, _ = run_analysis(session, req_proposed)

    assert ev_proposed["location"]["uses_proposed_location"] is True
    assert ev_admin["location"]["uses_proposed_location"] is False

    # MSME evidence differs between the two geo centres.
    a = ev_admin["location_features"]["nearby_msmes"]
    b = ev_proposed["location_features"]["nearby_msmes"]
    assert a != b

    # Competitor set responds to the moved marker (Perundurai vs Sathya centroid).
    ca = ev_admin["business_competition"]["mapped_competitors_5km"]
    cb = ev_proposed["business_competition"]["mapped_competitors_5km"]
    assert ca != cb  # moving the marker changes the competitor tally
    # Both are real analyses keyed to the admin Location id.
    assert ev_proposed["location"]["id"] == ev_admin["location"]["id"]


def test_industry_context_integrated_into_analysis(session):
    # National (no state) indicator row - should surface as background context.
    session.add(IndicatorStatistic(
        indicator="textiles_apparel_exports", period="2021-22",
        value=44.44, unit="USD billion", state=None,
        source_name="data.gov.in", source_type="government",
        is_estimate=False, is_demo=False))
    session.commit()

    req = AnalysisRequest(
        state="Tamil Nadu", district="Erode", block="Sathyamangalam",
        village="Sathyamangalam", capital_available=100000,
        category_code="dairy", language="en",
    )
    evidence, _ = run_analysis(session, req)

    assert "industry_context" in evidence
    ctx = evidence["industry_context"]
    assert ctx["available"] is True
    indicators = ctx["indicators"]
    assert "textiles_apparel_exports" in indicators
    row = indicators["textiles_apparel_exports"]["rows"][0]
    assert row["unit"] == "USD billion"
    assert row["value"] == 44.44
