"""Geospatial tests (section 40): radius, nearby, distance, duplicates."""
from __future__ import annotations

import pytest

from app.db.models import Business, InfrastructurePoint
from app.geo import find_nearby, haversine_km


def test_haversine_known_distance():
    # Distance New Delhi -> Chennai approx 1765-1768 km
    d = haversine_km(28.6139, 77.2090, 13.0827, 80.2707)
    assert 1700 < d < 1850


def test_haversine_zero():
    assert haversine_km(11.5, 77.2, 11.5, 77.2) == pytest.approx(0.0, abs=1e-6)


def test_nearby_businesses_within_radius(session):
    rows = find_nearby(session, Business, 11.5056, 77.2390, 5.0,
                       {"category_code": "dairy"})
    names = {r.name for r in rows}
    # Dairy A (~0.18km), Dairy B (~0.8km), Dup X/Y (~0.06km) all within 5km
    assert "Dairy A" in names
    assert "Dairy B" in names
    assert "Grocery C" not in names  # ~1.6km but different category filter


def test_nearby_returns_nearest_first(session):
    rows = find_nearby(session, Business, 11.5056, 77.2390, 10.0)
    d0 = haversine_km(11.5056, 77.2390, rows[0].latitude, rows[0].longitude)
    d1 = haversine_km(11.5056, 77.2390, rows[1].latitude, rows[1].longitude)
    assert d0 <= d1 + 1e-6


def test_radius_exclusion_far_away(session):
    # Far location in Perundurai; nearest dairy there is ~ 1.4km away
    rows = find_nearby(session, Business, 11.2760, 77.5800, 1.0)
    assert all(
        haversine_km(11.2760, 77.5800, r.latitude, r.longitude) <= 1.0 + 1e-6
        for r in rows
    )


def test_duplicate_coordinates_present(session):
    # Two demo businesses share identical coordinates (duplicate-list test data)
    rows = find_nearby(session, Business, 11.5060, 77.2395, 0.1)
    assert any(r.name == "Dup X" for r in rows)
    assert any(r.name == "Dup Y" for r in rows)


def test_market_nearby(session):
    markets = find_nearby(session, InfrastructurePoint, 11.5056, 77.2390, 5.0,
                          {"kind": "market"})
    assert len(markets) == 1
    assert markets[0].name == "Sathya Market"


def test_postgis_sql_documented():
    # Ensure a production PostGIS query reference exists
    from pathlib import Path
    p = Path(__file__).resolve().parents[1] / "scripts" / "db" / "postgis_queries.sql"
    assert p.exists(), "Production PostGIS queries doc must be present"
