"""Plan §26: backend GeoJSON map layers."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.db.models import Business, InfrastructurePoint
from app.main import app

client = TestClient(app)


def _send(body):
    return client.post("/geojson/layers", json=body)


def test_all_layers_return_feature_collections(session):
    r = _send({"latitude": 11.5056, "longitude": 77.2390, "radius_km": 10})
    assert r.status_code == 200
    d = r.json()
    assert d["center"] == {"latitude": 11.5056, "longitude": 77.2390}
    assert d["geo_backend"] in ("postgis", "haversine")
    for layer in ("businesses", "infrastructure", "markets"):
        assert d["layers"][layer]["type"] == "FeatureCollection"
    assert d["counts"]["businesses"] == 5
    assert d["counts"]["infrastructure"] == 2
    assert d["counts"]["markets"] == 1


def test_feature_geometry_is_lng_lat_and_carries_provenance(session):
    d = _send({"latitude": 11.5056, "longitude": 77.2390, "radius_km": 10}).json()
    market = d["layers"]["markets"]["features"][0]
    assert market["geometry"]["coordinates"] == [77.2400, 11.5050]
    assert market["properties"]["kind"] == "market"
    assert market["properties"]["name"] == "Sathya Market"
    assert market["properties"]["source_type"] == "demo"
    business = d["layers"]["businesses"]["features"][0]
    assert business["properties"]["category"] == business["properties"].get("category")
    assert "id" in business["properties"]


def test_businesses_layer_optional(session):
    d = _send({"latitude": 11.5056, "longitude": 77.2390, "radius_km": 10,
               "layers": ["infrastructure"]}).json()
    assert "businesses" not in d["layers"]
    assert "markets" not in d["layers"]
    assert d["layers"]["infrastructure"]["features"]


def test_radius_filters_layers(session):
    near = _send({"latitude": 11.5056, "longitude": 77.2390, "radius_km": 0.2}).json()
    assert near["counts"]["businesses"] == 3  # b1, b4, b5 within 200m; b2/b3 further out
    assert near["counts"]["markets"] == 1
    far = _send({"latitude": 11.5056, "longitude": 77.2390, "radius_km": 0.01}).json()
    assert far["counts"]["businesses"] == 0
    assert far["layers"]["infrastructure"]["features"] == []


def test_invalid_layer_name_rejected(session):
    r = _send({"latitude": 11.5056, "longitude": 77.2390, "radius_km": 10,
               "layers": ["schools"]})
    assert r.status_code == 422


def test_empty_db_returns_empty_collections(engine):
    from app.db import session as db_session

    with db_session.session_scope() as s:
        for tbl in [InfrastructurePoint.__table__, Business.__table__]:
            s.execute(tbl.delete())
    d = _send({"latitude": 11.5056, "longitude": 77.2390, "radius_km": 10}).json()
    assert d["counts"] == {"businesses": 0, "infrastructure": 0, "markets": 0}
    for layer in d["layers"].values():
        assert layer["features"] == []
