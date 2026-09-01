"""Geoapify optional provider: honest behavior + multi-source guarantees (P0)."""
from __future__ import annotations

import pytest

from app.config import settings
from app.providers import geoapify as gp


def test_api_key_none_when_provider_keys_empty():
    # No key configured -> provider disabled (skipped in the discovery ladder).
    assert gp.api_key(type("S", (), {"data_provider_keys": ""})()) is None
    assert gp.api_key(type("S", (), {"data_provider_keys": "{}"})()) is None
    assert gp.api_key(type("S", (), {"data_provider_keys": '{ "other": "k" }'})()) is None


def test_api_key_reads_geoapify_from_provider_keys():
    s = type("S", (), {"data_provider_keys": '{"geoapify": "  AB12  "}'})()
    assert gp.api_key(s) == "AB12"


def test_query_without_key_raises_unavailable_never_fabricates():
    with pytest.raises(gp.GeoapifyUnavailable):
        gp.query(11.34, 77.71, 2000, "grocery", key=None)


def test_query_uncached_by_category_returns_honest_empty():
    # Categories Geoapify does not cover must be an honest empty read, not a guess.
    r = gp.query(11.34, 77.71, 2000, "handicrafts", key="fake-key")
    assert r.pois == []
    assert r.queried_at is not None


def test_configured_keys_parses_json_object_safely():
    assert gp.configured_keys("not json") == {}
    assert gp.configured_keys('[1,2]') == {}
    assert gp.configured_keys('{"geoapify":"x"}') == {"geoapify": "x"}


def test_normalize_skips_unnamed_and_missing_coords():
    q = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
    assert gp._normalize({"properties": {"name": "   "}}, q) is None
    assert gp._normalize({"properties": {"name": "X"}}, q) is None
    feat = {"properties": {
        "name": "Shri Kirana", "lon": 77.71, "lat": 11.34,
        "categories": ["commercial.supermarket"], "place_id": "abc",
        "address_line1": "Main Road, Erode",
    }}
    p = gp._normalize(feat, q)
    assert p is not None
    assert p["source"] == "geoapify"
    assert p["normalized_name"] == "shri kirana"
    assert p["category"] == "commercial.supermarket"
    assert p["longitude"] == 77.71 and p["latitude"] == 11.34


def test_discovery_skips_geoapify_when_no_key(monkeypatch, session):
    from app.db.models import Business
    from app.providers import overpass as overpass_provider
    from app.services import competitors as svc

    assert gp.api_key(settings) is None  # environment has no key configured

    # Seed one real grocery near the query point.
    s = session
    b = Business(
        name="Test Kirana", source="osm", source_id="t-g-1", category_code="grocery",
        latitude=11.34, longitude=77.71,
    )
    s.add(b)
    s.flush()

    # Patch Overpass to fail; with no Geoapify key the ladder must fall through
    # to the DB-backed tier (never fabricate, never crash).
    def boom(*a, **k):
        raise overpass_provider.OverpassUnavailable("down")
    monkeypatch.setattr(overpass_provider, "query", boom)

    out = svc.discover_competitors(
        s, latitude=11.34, longitude=77.71, category_code="grocery", radius_km=2.0,
    )
    assert out["data_status"] in ("DB_FALLBACK", "FRESH")
    assert out["data"]["source"] in ("db", "osm")
