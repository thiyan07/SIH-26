"""Automated tests for the P0 competitor-discovery feature (plan §1, §5-§18).

Covers four layers without hitting the live network in CI:

* catalog  — ``category_for_osm_tag`` reverse mapping + relationship matrix
* provider — Overpass query builder (anchored regex, node+way, out center)
* service  — entity dedupe, ring analytics, confidence, cache upsert, and the
             exact-location ``discover_competitors`` orchestration (with the
             Overpass provider monkeypatched so tests are deterministic)
* endpoint — ``POST /businesses/discovery`` contract against the test DB

The provider itself was already smoke-tested live (Erode). Here we assert
stateless behaviour and the honest no-fabrication contract.
"""
from __future__ import annotations

import datetime as dt

import pytest

from app.catalog.business_categories import (
    category_for_osm_tag,
    category_label,
    default_radius_km,
    get_category,
    relationship,
)
from app.providers import overpass as overpass_provider
from app.services import competitors as svc


# ---------------------------------------------------------------------------
# Catalog: OSM tag -> GramBiz reverse mapping + relationship matrix
# ---------------------------------------------------------------------------
def test_osm_tag_to_grambiz_category_maps_supermarket_to_grocery():
    # The P0 regression: raw OSM value is mapped into the unified taxonomy so
    # the relationship matrix classifies a supermarket as a DIRECT grocery rival.
    assert category_for_osm_tag("supermarket") == "grocery"
    assert category_for_osm_tag("convenience") == "grocery"
    assert category_for_osm_tag("restaurant") == "restaurant"
    assert category_for_osm_tag("mobile_phone") in ("mobile_shop", "electronics")


def test_osm_tag_unknown_falls_back_to_other():
    # Unknown tags must never crash or guess a competitor category.
    assert category_for_osm_tag("wizard_fantasy_shop") == "other"
    assert category_for_osm_tag("") == "other"
    assert category_for_osm_tag(None) == "other"


def test_relationship_matrix_is_directional_and_returns_unrelated_by_default():
    # grocery -> supermarket/grocery is DIRECT; bakery is INDIRECT; unknown is UNRELATED.
    assert relationship("grocery", "grocery") == "direct"
    assert relationship("grocery", "bakery") == "indirect"
    assert relationship("grocery", "pharmacy") == "unrelated"
    assert relationship("unknown_code", "grocery") == "unrelated"


def test_catalog_helpers():
    assert get_category("grocery")["code"] == "grocery"
    assert get_category("does-not-exist") is None
    assert category_label("grocery").startswith("Grocery")
    assert category_label("nope", fallback="Business") == "Business"
    # convenience categories search tighter than destination ones
    assert default_radius_km("tea_shop") < default_radius_km("hardware")


# ---------------------------------------------------------------------------
# Provider: query builder (pure, no network)
# ---------------------------------------------------------------------------
def test_build_query_uses_node_and_way_and_out_center():
    q = overpass_provider._build_query(11.32, 77.67, 3000, [{"key": "shop", "values": ["grocery"]}])
    assert "node(around:3000,11.32,77.67)" in q
    assert "way(around:3000,11.32,77.67)" in q
    assert "out center;" in q
    assert "[out:json]" in q
    # node + way are gathered together inside a single (...) union statement
    assert q.startswith("[out:json][timeout:25];(")
    assert ";way(around:" in q
    assert q.rstrip().endswith(";out center;")


def test_build_query_anchors_regex_values():
    # Anchors must prevent a partial string (e.g. "shopper") matching "grocery".
    q = overpass_provider._build_query(0, 0, 1000, [{"key": "shop", "values": ["grocery", "supermarket"]}])
    assert '["shop"~"^(grocery|supermarket)$"]' in q


def test_build_query_preserves_any_value_when_values_none():
    q = overpass_provider._build_query(0, 0, 1000, [{"key": "craft", "values": None}])
    assert '["craft"]' in q
    assert '~"' not in q


def test_normalize_skips_unnamed_pois():
    # No-name POIs carry no competitor info we can attribute -> skipped.
    assert overpass_provider._normalize({"id": 1, "lat": 1, "lon": 1, "tags": {"shop": "grocery"}},
                                        dt.datetime.now(dt.timezone.utc), "node") is None


def test_normalize_discards_way_without_center():
    assert overpass_provider._normalize({"id": 2, "tags": {"name": "X", "shop": "bakery"}},
                                        dt.datetime.now(dt.timezone.utc), "way") is None


def test_normalize_extracts_evidence_fields():
    queried_at = dt.datetime.now(dt.timezone.utc)
    p = overpass_provider._normalize({
        "id": 3, "lat": 11.0, "lon": 77.0,
        "tags": {"name": "Sri Krishna Stores", "shop": "supermarket", "brand": "Reliance"},
    }, queried_at, "node")
    assert p is not None
    assert p["name"] == "Sri Krishna Stores"
    assert p["category"] == "supermarket"
    assert p["brand"] == "Reliance"
    assert p["matched_tags"] == ["shop=supermarket"]
    assert p["retrieved_at"] == queried_at.isoformat()


# ---------------------------------------------------------------------------
# Service: entity dedupe + analytics + confidence
# ---------------------------------------------------------------------------
def _poi(name, lat, lon, **kw):
    d = {"name": name, "normalized_name": name.lower(), "latitude": lat,
         "longitude": lon, "category": kw.pop("category", "grocery")}
    d.update(kw)
    return d


def _fake_result(pois, mirror="https://overpass-api.de/api/interpreter", n=0, w=0):
    from types import SimpleNamespace
    return SimpleNamespace(
        pois=pois, mirror=mirror, queried_at=dt.datetime.now(dt.timezone.utc),
        analyzed_nodes=n, analyzed_ways=w,
    )


def test_dedupe_merges_same_name_close_coords_and_flags_ties():
    pois = [
        _poi("Krishna Mart", 11.32, 77.67),
        _poi("krishna mart", 11.32002, 77.67001),   # same name, ~2m apart -> merged
        _poi("Krishna Mart", 11.35, 77.68),          # same name, ~3.5km away -> NOT merged
        _poi("Different Shop", 11.32, 77.67),
    ]
    out = svc.dedupe_competitors(pois)
    names = sorted(p["name"] for p in out)
    assert len(out) == 3
    assert names.count("Krishna Mart") == 2  # the 3.5km twin survives; near twin merged
    merged = next(p for p in out if p["merged_from"] == 2)
    assert merged["possible_duplicate"] is True


def test_dedupe_never_merges_different_names():
    pois = [_poi("A", 11.32, 77.67), _poi("B", 11.320002, 77.670001)]
    assert len(svc.dedupe_competitors(pois)) == 2


def test_ring_counts_and_nearest():
    center = (11.32, 77.67)
    pois = [
        _poi("Near", 11.32001, 77.67001),    # ~1.5m
        _poi("Mid", 11.325, 77.675),          # ~600m
        _poi("Far", 11.36, 77.70),            # ~5.5km
    ]
    analytics = svc.compute_analytics(pois, center[0], center[1], 6000)
    assert analytics["rings"]["500m"] == 1
    assert analytics["rings"]["1000m"] == 2
    assert analytics["rings"]["5000m"] == 2
    assert analytics["rings"]["10000m"] == 3
    assert analytics["nearest_distance_m"] == pytest.approx(analytics["rings"]["500m"] and 2.0, abs=4)
    assert analytics["count"] == 3
    assert analytics["density_per_km2"] > 0


def test_confidence_is_deterministic_and_bounded():
    anal = {"count": 3, "category_saturation": "low"}
    c1 = svc.confidence(anal, dt.datetime.now(dt.timezone.utc))
    c2 = svc.confidence(anal, dt.datetime.now(dt.timezone.utc))
    assert c1 == c2                      # deterministic
    assert 0.0 <= c1["score"] <= 1.0
    assert c1["label"] in ("low", "medium", "high")
    assert set(c1["factors"]) == {"coverage", "source", "freshness"}


def test_existence_status_unknown_when_no_timestamp():
    assert svc._existence_status(None) == "UNKNOWN"
    assert svc._existence_status(dt.datetime.now(dt.timezone.utc)) == "ACTIVE"


# ---------------------------------------------------------------------------
# Service: cache write is an UPSERT keyed by scope_key (P0 cache bug fix)
# ---------------------------------------------------------------------------
def test_write_cache_upserts_by_scope_key(session):
    from app.db.models import CompetitorCache

    class _R:
        def __init__(self, pois, mirror="m", n=2, w=1):
            self.pois = pois
            self.mirror = mirror
            self.queried_at = dt.datetime.now(dt.timezone.utc)
            self.analyzed_nodes = n
            self.analyzed_ways = w

    sk = "osm|11.3200|77.6700|2000|grocery"
    r1 = _R([_poi("First", 11.32, 77.67)])
    r2 = _R([_poi("First", 11.32, 77.67), _poi("Second", 11.321, 77.671)])

    svc._write_cache(session, sk, "grocery", 11.3200, 77.6700, 2000, r1)
    session.flush()
    svc._write_cache(session, sk, "grocery", 11.3200, 77.6700, 2000, r2)
    session.flush()

    rows = session.query(CompetitorCache).filter(CompetitorCache.scope_key == sk).all()
    # Upsert: still exactly ONE row per scope_key, holding the latest payload.
    assert len(rows) == 1
    assert len(rows[0].payload) == 2


# ---------------------------------------------------------------------------
# Service: discover_competitors orchestration (provider monkeypatched)
# ---------------------------------------------------------------------------
def test_discover_fresh_returns_real_pois_and_classifies_direct(monkeypatch, session):
    pois = [
        _poi("Reliance Super", 11.3201, 77.6701, category="supermarket"),   # -> grocery, DIRECT
        _poi("Fresh Bazaar", 11.3202, 77.6702, category="convenience"),     # -> grocery, DIRECT
        _poi("Anna Bakery", 11.3210, 77.6710, category="bakery"),           # -> bakery, INDIRECT
    ]
    _R = _fake_result(pois, n=3, w=1)

    monkeypatch.setattr(overpass_provider, "query", lambda *a, **k: _R)

    out = svc.discover_competitors(
        session, latitude=11.32, longitude=77.67, category_code="grocery",
        radius_km=3.0,
    )

    assert out["data_status"] == "FRESH"
    assert out["proposed_location"] == {"latitude": 11.32, "longitude": 77.67}
    assert out["competitors"]["total_mapped"] == 3
    assert out["competitors"]["direct"] == 2
    assert out["competitors"]["indirect"] == 1
    # provenance is honest, never fabricated
    assert out["data"]["primary_source"] == "OpenStreetMap (Overpass API)"
    assert out["data"]["source"] == "osm"
    assert out["data"]["mirror"] == "https://overpass-api.de/api/interpreter"
    assert out["data"]["confidence"] == out["confidence"]["score"]
    assert "not that none exist" in out["data"]["note"]
    assert len(out["listings"]["direct"]) == 2
    assert out["listings"]["direct"][0]["relationship"] == "direct"


def test_discover_all_mirrors_down_returns_unavailable_never_fabricates(monkeypatch, session):
    def boom(*a, **k):
        raise overpass_provider.OverpassUnavailable("all mirrors failed")

    monkeypatch.setattr(overpass_provider, "query", boom)

    out = svc.discover_competitors(
        session, latitude=11.32, longitude=77.67, category_code="grocery",
        radius_km=3.0,
    )

    # Honest UNAVAILABLE with zero counts — 0 truly means nothing available.
    assert out["data_status"] == "UNAVAILABLE"
    assert out["competitors"]["total_mapped"] == 0
    assert out["data"]["source"] is None
    assert out["data"]["mirror"] is None
    assert out["listings"]["direct"] == []
    # An audit row is still written so the miss is observable.
    from app.db.models import DataSyncRun
    assert session.query(DataSyncRun).filter(DataSyncRun.status == "unavailable").count() >= 1


def test_discover_external_source_failure_falls_back_to_db(monkeypatch, session):
    """Required Test 6: external-source fallback.

    When every live/external source is down, the pipeline serves REAL
    previously-ingested rows from the businesses table as ``DB_FALLBACK``
    (never fabricated, provenance preserved) instead of failing the request.
    """
    # the seeded fixture places 'Grocery C' at (11.5150, 77.2500) → grocery.
    def boom(*a, **k):
        raise overpass_provider.OverpassUnavailable("all mirrors failed")

    monkeypatch.setattr(overpass_provider, "query", boom)

    out = svc.discover_competitors(
        session, latitude=11.51, longitude=77.25, category_code="grocery",
        radius_km=5.0,
    )

    assert out["data_status"] == "DB_FALLBACK"
    assert out["competitors"]["total_mapped"] == 1
    assert out["listings"]["direct"][0]["name"] == "Grocery C"
    assert out["data"]["source"] == "db"
    assert out["data"]["data_status"] == "DB_FALLBACK"
    # provenance fields are carried through, not invented
    assert out["listings"]["direct"][0]["source_record_id"].startswith("business/")
    # the DB rows are real ('test' source), distinct from a fabricated generic name
    assert out["listings"]["direct"][0]["name"] != "Sample Competitor"


def test_discover_db_fallback_zero_rows_is_never_fabricated(monkeypatch, session):
    """Required Test 7: zero-result no-fabrication.

    With all sources down and no previously-ingested rows near the point, the
    response is an honest UNAVAILABLE (0), and never a parroted/synthetic
    competitor list.
    """
    def boom(*a, **k):
        raise overpass_provider.OverpassUnavailable("all mirrors failed")

    monkeypatch.setattr(overpass_provider, "query", boom)

    # Far from every seeded business row: nothing ingested nearby.
    out = svc.discover_competitors(
        session, latitude=11.00, longitude=77.00, category_code="pharmacy",
        radius_km=1.0,
    )

    assert out["data_status"] == "UNAVAILABLE"
    assert out["competitors"]["total_mapped"] == 0
    assert out["listings"]["direct"] == []
    assert out["listings"]["indirect"] == []
    assert "0 competitors were FOUND IN THE AVAILABLE DATA" in out["data"]["note"]


def test_db_fallback_pois_carry_confidence_and_verification_fields(session):
    """The businesses-table fallback tier surfaces per-record confidence and
    verification metadata (mission absolute requirements) when present."""
    from app.db.models import Business

    s = session
    b = s.query(Business).filter(Business.source_id == "3").first()
    b.confidence_score = 0.75
    b.verification_status = "PARTIALLY_VERIFIED"
    b.first_seen_at = dt.datetime.now(dt.timezone.utc)
    s.flush()

    from app.services import competitors as _svc
    pois = _svc._db_business_pois(
        s, latitude=11.5150, longitude=77.2500, radius_m=3000, category_code="grocery")
    assert pois
    assert pois[0]["name"] == "Grocery C"
    assert pois[0]["confidence_score"] == 0.75
    assert pois[0]["verification_status"] == "PARTIALLY_VERIFIED"
    assert pois[0]["first_seen_at"] is not None


# ---------------------------------------------------------------------------
# Endpoint: POST /businesses/discovery contract (provider monkeypatched)
# ---------------------------------------------------------------------------
def test_discovery_endpoint_contract(monkeypatch, session):
    from fastapi.testclient import TestClient

    from app.main import app

    pois = [_poi("Reliance Super", 11.3201, 77.6701, category="supermarket")]
    _R = _fake_result(pois, n=1, w=0)

    monkeypatch.setattr(overpass_provider, "query", lambda *a, **k: _R)

    client = TestClient(app)
    r = client.post("/businesses/discovery", json={
        "latitude": 11.32, "longitude": 77.67, "category_code": "grocery", "radius_km": 3.0,
    })
    assert r.status_code == 200, r.text
    body = r.json()

    # every key the frontend preview + AI evidence depends on is present
    assert body["data_status"] == "FRESH"
    assert body["proposed_location"]["latitude"] == 11.32
    assert body["business_type"] == "grocery"
    assert body["search_radius_m"] == 3000
    assert body["competitors"]["direct"] == 1
    assert body["competitors"]["total_mapped"] == 1
    assert "rings" in body["competitors"]
    assert "nearest_distance_m" in body["competitors"]
    assert "confidence" in body and "score" in body["confidence"]
    assert "data" in body and body["data"]["source"] == "osm"
    assert "listings" in body


def test_discovery_endpoint_unknown_category_fails_closed(monkeypatch, session):
    # A category the catalog cannot express must not guess or fabricate.
    from fastapi.testclient import TestClient

    from app.main import app

    real_query = overpass_provider.query
    monkeypatch.setattr(overpass_provider, "query", lambda *a, **k: None)  # should never be called

    client = TestClient(app)
    r = client.post("/businesses/discovery", json={
        "latitude": 11.32, "longitude": 77.67, "category_code": "does_not_exist",
    })
    # fail-closed empty read (unknown category -> no filters) still returns 200 contract
    assert r.status_code == 200
    assert r.json()["competitors"]["total_mapped"] == 0
    monkeypatch.setattr(overpass_provider, "query", real_query)
