"""Tests for the exact-place geocoder proxy (nominatim / photon / google).

The provider HTTP layer is monkeypatched so tests never touch the live
network. Covers response mapping, provider selection, empty queries, upstream
errors and the /geocode/search endpoint contract.
"""
from __future__ import annotations

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import geocoder
from app.services.geocoder import GeocoderError, search_places

_NAMIMATIN_SAMPLE = [
    {
        "name": "Bhavani Bus Stand",
        "display_name": "Bhavani Bus Stand, Bhavani, Erode, Tamil Nadu, India",
        "lat": "11.44723",
        "lon": "77.68298",
        "importance": 0.6,
    }
]

_PHOTON_SAMPLE = {
    "features": [
        {
            "geometry": {"type": "Point", "coordinates": [77.68298, 11.44723]},
            "properties": {
                "name": "Bhavani Bus Stand",
                "street": "Main Road",
                "city": "Bhavani",
                "state": "Tamil Nadu",
                "country": "India",
            },
            "properties_extra": {},
        }
    ]
}


class FakeResponse:
    def __init__(self, payload, status=200, exc=None):
        self._payload = payload
        self._status = status
        self._exc = exc

    def raise_for_status(self):
        if self._exc:
            raise self._exc
        if self._status >= 400:
            raise httpx.HTTPStatusError("upstream error", request=httpx.Request("GET", "x"),
                                        response=httpx.Response(self._status))
        return None

    def json(self):
        return self._payload


@pytest.fixture()
def client(seeded):
    return TestClient(app)


def test_nominatim_maps_places(monkeypatch):
    monkeypatch.setattr(geocoder.settings, "geocoder_provider", "nominatim")

    def fake_get(url, **kwargs):
        assert kwargs["params"]["viewbox"].startswith("77.53,")
        return FakeResponse(_NAMIMATIN_SAMPLE)

    monkeypatch.setattr(geocoder.httpx, "get", fake_get)
    places = search_places("Bhavani Bus Stand", limit=3, bias=(11.44, 77.68))
    assert len(places) == 1
    p = places[0]
    assert p.name == "Bhavani Bus Stand"
    assert p.display_name == "Bhavani Bus Stand, Bhavani, Erode, Tamil Nadu, India"
    assert p.latitude == pytest.approx(11.44723)
    assert p.longitude == pytest.approx(77.68298)
    assert p.provider == "nominatim"
    assert p.confidence == "high"


def test_photon_maps_places(monkeypatch):
    monkeypatch.setattr(geocoder.settings, "geocoder_provider", "photon")

    def fake_get(url, **kwargs):
        return FakeResponse(_PHOTON_SAMPLE)

    monkeypatch.setattr(geocoder.httpx, "get", fake_get)
    places = search_places("Bhavani Bus Stand")
    assert len(places) == 1
    p = places[0]
    assert p.name == "Bhavani Bus Stand"
    assert "Main Road" in p.display_name
    assert p.latitude == pytest.approx(11.44723)
    assert p.longitude == pytest.approx(77.68298)


def test_nominatim_skips_rows_without_coords(monkeypatch):
    monkeypatch.setattr(geocoder.settings, "geocoder_provider", "nominatim")
    monkeypatch.setattr(geocoder.httpx, "get", lambda url, **kw: FakeResponse([{"name": "no coords"}]))
    assert search_places("garbage") == []


def test_empty_query_returns_no_results(monkeypatch):
    called = False

    def fake_get(url, **kw):
        nonlocal called
        called = True
        return FakeResponse([])

    monkeypatch.setattr(geocoder.httpx, "get", fake_get)
    assert search_places("   ") == []
    assert not called


def test_unconfigured_google_raises(monkeypatch):
    monkeypatch.setattr(geocoder.settings, "geocoder_provider", "google")
    monkeypatch.setattr(geocoder.settings, "geocoder_api_key", "")
    with pytest.raises(GeocoderError):
        search_places("Bhavani")


def test_unknown_provider_raises(monkeypatch):
    monkeypatch.setattr(geocoder.settings, "geocoder_provider", "made_up_provider")
    with pytest.raises(GeocoderError):
        search_places("Bhavani")


def test_upstream_http_error_is_surfaced(monkeypatch):
    monkeypatch.setattr(geocoder.settings, "geocoder_provider", "nominatim")
    monkeypatch.setattr(
        geocoder.httpx, "get",
        lambda url, **kw: FakeResponse(None, status=503),
    )
    with pytest.raises(httpx.HTTPStatusError):
        search_places("Bhavani")


def test_geocode_search_endpoint_maps_results(client, monkeypatch):
    monkeypatch.setattr(geocoder.settings, "geocoder_provider", "nominatim")
    monkeypatch.setattr(geocoder.httpx, "get", lambda url, **kw: FakeResponse(_NAMIMATIN_SAMPLE))
    r = client.get("/geocode/search", params={"q": "Bhavani Bus Stand", "limit": 5})
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 1
    assert body[0]["name"] == "Bhavani Bus Stand"
    assert body[0]["latitude"] is not None
    assert body[0]["provider"] == "nominatim"


def test_geocode_search_short_query_returns_empty(client):
    # No upstream call should happen for a <3 char query.
    r = client.get("/geocode/search", params={"q": "ab"})
    assert r.status_code == 200
    assert r.json() == []


def test_geocode_endpoint_upstream_error_is_502(client, monkeypatch):
    monkeypatch.setattr(geocoder.settings, "geocoder_provider", "nominatim")
    monkeypatch.setattr(
        geocoder.httpx, "get",
        lambda url, **kw: FakeResponse(None, status=500),
    )
    r = client.get("/geocode/search", params={"q": "Bhavani Bus Stand"})
    assert r.status_code == 502
