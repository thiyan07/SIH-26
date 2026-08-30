"""PostGIS radius-query path (plan §5/§6/§26 hardening — Stage J).

The public `find_nearby`/`find_nearby_with_distance` helpers auto-select the
index-backed PostGIS ST_DWithin path when (a) the connected database supports
PostGIS and (b) the target table carries the optional `geom` geography column
(scripts/db/postgis.py). Otherwise the portable haversine SQL expression is
used. These tests pin the routing decision, the query construction, and the
cross-backend equivalence guarantee (identical rows, nearest-first, identical
distance values) so enabling PostGIS never changes application numbers.
"""
from __future__ import annotations

import pytest

from app import geo
from app.db.models import Business, InfrastructurePoint

# ---------- pure query construction (no database needed) ----------

def test_radius_conversion_to_metres():
    assert geo._radius_m(5.0) == 5000.0
    assert geo._radius_m(0.2) == 200.0


def test_table_name_resolution():
    assert geo._table_name(Business) == "businesses"
    assert geo._table_name(InfrastructurePoint) == "infrastructure_points"


def test_postgis_radius_stmt_uses_sdwithin_geography():
    stmt, bound = geo._postgis_radius_stmt(
        Business, 11.5056, 77.2390, 5.0, {"category_code": "dairy"}, limit=300,
    )
    sql = str(stmt.compile(compile_kwargs={"literal_binds": True}))
    assert "ST_DWithin" in sql
    assert "geography" in sql
    assert "ST_MakePoint" in sql
    assert "ST_Distance" in sql
    # radius in metres, not km
    assert bound["radius_m"] == 5000.0
    assert bound["lat"] == pytest.approx(11.5056)


def test_postgis_radius_stmt_builds_for_infrastructure_model():
    stmt, bound = geo._postgis_radius_stmt(
        InfrastructurePoint, 11.5056, 77.2390, 20.0, {"kind": "market"}, limit=50,
    )
    assert "ST_DWithin" in str(stmt)
    # kind filter becomes a WHERE on the ORM column
    assert bound["radius_m"] == 20000.0


# ---------- routing decision (capability probes monkeypatched; no SQL run) ----------

def test_router_picks_postgis_when_geometry_ready(session, monkeypatch):
    monkeypatch.setattr(geo, "_postgis_available", lambda url: True)
    monkeypatch.setattr(geo, "_table_has_geom", lambda url, table: True)
    assert geo.geography_enabled(session, Business) is True
    assert geo.geo_backend_name(session, Business) == "postgis"


def test_router_falls_back_when_geom_column_missing(session, monkeypatch):
    monkeypatch.setattr(geo, "_postgis_available", lambda url: True)
    monkeypatch.setattr(geo, "_table_has_geom", lambda url, table: False)
    assert geo.geography_enabled(session, Business) is False
    assert geo.geo_backend_name(session, Business) == "haversine"


def test_router_falls_back_when_postgis_absent(session, monkeypatch):
    monkeypatch.setattr(geo, "_postgis_available", lambda url: False)
    monkeypatch.setattr(geo, "_table_has_geom", lambda url, table: True)
    assert geo.geo_backend_name(session, Business) == "haversine"


# ---------- DB-backed: automatic backend + cross-backend equivalence ----------

def test_capability_probe_returns_bool_without_error(session):
    url = geo._bind_url(session)
    assert isinstance(geo._postgis_available(url), bool)
    assert isinstance(geo._table_has_geom(url, "businesses"), bool)
    # geography_enabled must be the conjunction of both probes
    assert geo.geography_enabled(session, Business) == (
        geo._postgis_available(url) and geo._table_has_geom(url, "businesses")
    )


def test_auto_route_and_fallback_agree_on_seeded_cluster(session, seeded):
    auto = [r.id for r in geo.find_nearby(session, Business, 11.5056, 77.2390, 10.0, None, 500)]
    fallback = [r.id for r in geo._haversine_nearby(
        session, Business, 11.5056, 77.2390, 10.0, None, 500)]
    assert auto == fallback


def test_distances_sorted_and_match_haversine(session, seeded):
    rows = geo.find_nearby_with_distance(
        session, Business, 11.5056, 77.2390, 10.0, None, 500)
    prev = -1.0
    for row, d in rows:
        expected = geo.haversine_km(11.5056, 77.2390, row.latitude, row.longitude)
        assert d == pytest.approx(expected, rel=1e-9)
        assert d >= prev - 1e-9
        prev = d


def test_filter_still_applied_with_auto_routing(session, seeded):
    near = geo.find_nearby(session, InfrastructurePoint, 11.5056, 77.2390, 5.0,
                           {"kind": "market"}, limit=50)
    assert len(near) == 1
    assert near[0].name == "Sathya Market"
