"""Location-scoped MSME/industrial evidence (UDYAM pincode-level)."""
from __future__ import annotations

from app.db.models import IndustrialUnit, UdyamUnit
from app.engines.location_features import (
    _category_nic_signals,
    location_features,
)


def _add_udyam(session, rows):
    for r in rows:
        session.add(UdyamUnit(
            udyam_number=r["num"], enterprise_name=r["name"],
            sector=r.get("sector"), nic_code=r.get("nic"),
            state="Tamil Nadu", district=r.get("district", "Erode"),
            pincode=r["pin"], latitude=r.get("lat"),
            longitude=r.get("lng"),
            source_name="UDYAM", source_type="government",
            geographic_level="pincode", confidence="medium",
            is_demo=False))
    session.commit()


def test_category_nic_signals_extract_nic_prefixes():
    assert _category_nic_signals({"demand_signals": ["nic:10", "nic:47"]}) == ["10", "47"]
    assert _category_nic_signals({"demand_signals": ["some_tag", 3]}) == []


def test_nearby_msmes_count_by_pincode_centroid(session):
    # Units near Perundurai (11.276, 77.58): pincode centroids within ~5km.
    _add_udyam(session, [
        {"num": "U1", "name": "Florist A", "sector": "services", "nic": "47110",
         "pin": "638052", "lat": 11.28, "lng": 77.58},
        {"num": "U2", "name": "Bakery B", "sector": "manufacturing", "nic": "10711",
         "pin": "638011", "lat": 11.26, "lng": 77.57},
        {"num": "U3", "name": "Far unit", "sector": "manufacturing", "nic": "10711",
         "pin": "638001", "lat": 11.51, "lng": 77.23},  # ~40km away (Sathyamangalam)
    ])
    feats = location_features(
        session, state="Tamil Nadu", district="Erode",
        latitude=11.276, longitude=77.58, radius_km=10.0, profile={})
    assert feats["geo_resolution"] == "pincode"
    assert feats["nearby_msmes"] == 2  # U3 is far away, excluded
    assert "pincode centroid" in feats["geo_resolution_note"].lower()
    assert feats["sector_composition"].get("services") == 1
    assert feats["sector_composition"].get("manufacturing") == 1


def test_relevant_msmes_filter_by_district_and_nic(session):
    _add_udyam(session, [
        {"num": "R1", "name": "Bakery Erode", "sector": "manufacturing",
         "nic": "10711", "pin": "638011", "lat": 11.26, "lng": 77.57,
         "district": "Erode"},
        {"num": "R2", "name": "Bakery Salem", "sector": "manufacturing",
         "nic": "10711", "pin": "636001", "lat": 11.65, "lng": 78.16,
         "district": "Salem"},  # different district - excluded
        {"num": "R3", "name": "Garment", "sector": "manufacturing",
         "nic": "14110", "pin": "638011", "lat": 11.26, "lng": 77.57,
         "district": "Erode"},  # different NIC - excluded
    ])
    profile = {"demand_signals": ["nic:10"]}  # NIC division 10 (food products)
    feats = location_features(
        session, state="Tamil Nadu", district="Erode",
        latitude=11.276, longitude=77.58, radius_km=20.0, profile=profile)
    assert feats["relevant_msmes"] == 1  # only R1 (Erode + NIC 10)
    assert feats["available"] is True
    assert feats["source_name"].startswith("UDYAM")


def test_no_udyam_data_returns_available_false_not_fabricated(session):
    feats = location_features(
        session, state="Tamil Nadu", district="Erode",
        latitude=11.276, longitude=77.58, radius_km=10.0, profile={})
    assert feats["nearby_msmes"] == 0
    assert feats["relevant_msmes"] == 0
    assert feats["available"] is False
    assert isinstance(feats["industrial_units"]["available"], bool)


def test_industrial_units_block_is_district_scoped_not_fabricated(session):
    feats = location_features(
        session, state="Tamil Nadu", district="Erode",
        latitude=11.276, longitude=77.58, radius_km=10.0, profile={})
    assert feats["industrial_units"]["district_level"] is True
    assert feats["industrial_units"]["available"] is False


def test_industrial_units_aggregate_surfaced_when_present(session):
    session.add(IndustrialUnit(
        state="Tamil Nadu", district="Erode", unit_type="small_scale_industry",
        count=6430, reference_year=2019,
        source_name="Erode district SSI profile", source_type="government",
        geographic_level="district", confidence="medium", is_demo=False))
    session.commit()

    feats = location_features(
        session, state="Tamil Nadu", district="Erode",
        latitude=11.276, longitude=77.58, radius_km=10.0, profile={})
    ind = feats["industrial_units"]
    assert ind["available"] is True
    assert ind["district_level"] is True
    assert ind["total_units"] == 6430
    assert ind["by_type"][0]["unit_type"] == "small_scale_industry"
    assert ind["by_type"][0]["count"] == 6430
