"""OSM ingestion unit tests (plan §4–6): completeness/confidence heuristics,
region presets, category mapping, and ORM persistence of the new fields."""
from __future__ import annotations

import pytest

from scripts.ingest_osm.ingest import (
    _category_for_tags,
    _completeness_and_confidence,
    _infra_kind,
    _provenance,
)

# ---------- per-record completeness & confidence (§6) ----------

def test_completeness_full_tags_is_high():
    tags = {
        "name": "Aanai Dairy",
        "addr:street": "Bazaar Street",
        "phone": "+91 90000 00000",
        "opening_hours": "Mo-Sa 08:00-20:00",
        "website": "https://example.in",
    }
    completeness, confidence = _completeness_and_confidence(tags)
    assert completeness == 1.0
    assert confidence == "high"


def test_completeness_name_only_is_low():
    completeness, confidence = _completeness_and_confidence({"name": "Shops"})
    assert completeness == pytest.approx(0.35)
    assert confidence == "low"


def test_completeness_name_plus_phone_is_medium():
    completeness, confidence = _completeness_and_confidence({"name": "Kumaran Stores", "phone": "123"})
    assert completeness == pytest.approx(0.55)
    assert confidence == "medium"


def test_completeness_address_variants_count_once():
    with_street = _completeness_and_confidence({"name": "X", "addr:street": "Main Rd", "addr:housenumber": "7"})
    # address counts once (either phone varies), cap at 1.0 applied
    assert with_street[0] == pytest.approx(0.55)


def test_provenance_carries_completeness_and_confidence():
    prov = _provenance({"name": "Grocery", "phone": "1"})
    assert prov["completeness"] == pytest.approx(0.55)
    assert prov["confidence"] == "medium"
    assert prov["source_type"] == "osm"
    assert prov["is_demo"] is False


# ---------- category mapping (§4) ----------

def test_category_mapping_extended():
    assert _category_for_tags({"amenity": "marketplace"}) is None  # infrastructure, not a business
    assert _category_for_tags({"man_made": "works"}) == "manufacturing"
    assert _category_for_tags({"industrial": "factory"}) == "manufacturing"
    assert _category_for_tags({"craft": "handicraft"}) == "handicrafts"
    assert _category_for_tags({"shop": "dairy_farm"}) == "dairy"


def test_infra_kind_road_for_plain_highway():
    assert _infra_kind({"highway": "residential"}) == "road"
    assert _infra_kind({"amenity": "clinic"}) == "hospital"
    assert _infra_kind({"amenity": "bus_station"}) == "transport"


# ---------- region presets (§5) ----------

def test_all_region_presets_are_valid_bboxes():
    from scripts.ingest_osm.ingest import REGION_BBOXES
    assert len(REGION_BBOXES) >= 6
    for name, bbox in REGION_BBOXES.items():
        parts = [float(x) for x in bbox.split(",")]
        assert len(parts) == 4, name
        minlat, minlon, maxlat, maxlon = parts
        assert minlat < maxlat and minlon < maxlon, name
        # Erode District, Tamil Nadu bounds
        assert 11.0 <= minlat <= maxlat <= 12.0, name
        assert 76.5 <= minlon <= maxlon <= 78.0, name


def test_default_region_present():
    from scripts.ingest_osm.ingest import DEFAULT_REGION, REGION_BBOXES
    assert DEFAULT_REGION in REGION_BBOXES
    assert len(REGION_BBOXES[DEFAULT_REGION].split(",")) == 4


# ---------- ORM persistence of §6 fields ----------

def test_business_completeness_column(seeded, session):
    from app.db.models import Business
    b = Business(
        name="Live Dairy", category_code="dairy",
        latitude=11.5056, longitude=77.2390,
        source="osm", source_id="osm-9001",
        source_name="OpenStreetMap contributors", source_type="osm",
        confidence="high", completeness=0.85, is_demo=False,
    )
    session.add(b)
    session.flush()
    fetched = session.query(Business).filter(Business.source_id == "osm-9001").first()
    assert fetched.completeness == 0.85
    assert fetched.confidence == "high"
