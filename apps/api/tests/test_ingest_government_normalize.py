"""Offline tests for the data.gov.in normalizer (plan §7)."""
from __future__ import annotations

from datetime import date

import pytest

from app.db.models import MarketPrice, PopulationStatistic
from scripts.ingest_government.normalize import (
    DATAGOV_DEFS,
    detect_format,
    normalize_datagov,
    store_datagov,
)

MARKET_JSON = b"""
[{"commodity": "Onion", "market": "Erode", "district": "Erode", "state": "Tamil Nadu",
  "min_price": "1000", "max_price": "1200", "modal_price": 1100, "unit": "Quintal",
  "arrival_date": "12-08-2023"},
 {"commodity": "Tomato", "market": "Erode", "district": "Erode", "state": "Tamil Nadu",
  "min_price": "800", "max_price": "900", "modal_price": "850", "arrival_date": "2023-08-12"},
 {"commodity": "", "market": "Erode"}]"""

MARKET_CSV = b"""commodity,market,district,state,min_price,max_price,modal_price,arrival_date
Potato,Erode,Erode,Tamil Nadu,900,1100,1000,12-08-2023
Onion,Erode,Erode,Tamil Nadu,1000,1200,1100,13-08-2023"""

POP_JSON = b"""
{"records": [
  {"state": "Tamil Nadu", "district": "Erode", "block": "Sathyamangalam", "village": "Sathyamangalam",
   "population": "12400", "households": "3400", "census_year": "2011"},
  {"state": "Tamil Nadu", "district": "Erode", "block": "Perundurai", "village": "Perundurai",
   "total_population": "9500", "census_year": "2011"}
]}"""

AGR_CSV = b"""state,district,crop,season,area,production,yield_value
Tamil Nadu,Erode,Rice,Kharif,12000,24000,2.0
Tamil Nadu,Erode,Cotton,Rabi,5000,2500,0.5"""

RAIN_JSON = b"""
[{"state": "Tamil Nadu", "district": "Erode", "month": "2023-08", "rainfall_mm": "312.4", "unit": "mm"}]"""


def _def(name):
    return DATAGOV_DEFS[name]


def test_detect_format():
    assert detect_format(MARKET_JSON) == "json"
    assert detect_format(MARKET_CSV) == "csv"
    assert detect_format(b"<csdl:csdl><foo>1</foo></csdl:csdl>") == "xml"


def test_market_json_normalize_coerces_and_drops_bad_row():
    rows = normalize_datagov(MARKET_JSON, _def("market_arrivals"))
    assert len(rows) == 2
    one = rows[0]
    assert one["item_name"] == "Onion"
    assert one["min_price"] == 1000.0
    assert one["modal_price"] == 1100.0
    assert one["reference_date"] == date(2023, 8, 12)
    assert one["market_name"] == "Erode"
    assert one["unit"] == "Quintal"


def test_market_csv_normalize_and_dedupe():
    rows = normalize_datagov(MARKET_CSV, _def("market_arrivals"))
    assert len(rows) == 2
    assert rows[0]["item_name"] == "Potato"
    dup = b"""[
      {"commodity": "Onion", "market": "Erode", "state": "Tamil Nadu", "modal_price": "1100", "arrival_date": "12-08-2023"},
      {"commodity": "Onion", "market": "Erode", "state": "Tamil Nadu", "modal_price": "1100", "arrival_date": "12-08-2023"}]"""
    dupes = normalize_datagov(dup, _def("market_arrivals"))
    assert len(dupes) == 1


def test_population_normalize():
    rows = normalize_datagov(POP_JSON, _def("population"))
    assert len(rows) == 2
    assert rows[0]["population"] == 12400
    assert rows[0]["census_year"] == 2011
    assert rows[1]["population"] == 9500


def test_agriculture_normalize():
    rows = normalize_datagov(AGR_CSV, _def("agriculture"))
    assert len(rows) == 2
    assert rows[0]["production"] == 24000.0
    assert rows[1]["crop"] == "Cotton"


def test_weather_normalize():
    rows = normalize_datagov(RAIN_JSON, _def("imd_rainfall"))
    assert len(rows) == 1
    assert rows[0]["value"] == 312.4
    assert rows[0]["period"] == "2023-08"


@pytest.mark.parametrize("bad", [b"not really data", b'{"x": true}', b'[1,2,3]'])
def test_unparseable_returns_empty(bad):
    assert normalize_datagov(bad, _def("market_arrivals")) == []


def test_store_market_prices(session):
    rows = normalize_datagov(MARKET_CSV, DATAGOV_DEFS["market_arrivals"])
    n = store_datagov(session, DATAGOV_DEFS["market_arrivals"], rows, url="https://data.gov.in/resource/x")
    session.flush()
    stored = session.query(MarketPrice).all()
    assert n == 2
    assert len(stored) == 2
    first = stored[0]
    assert first.source_type == "government"
    assert first.source_url == "https://data.gov.in/resource/x"
    assert first.confidence == "medium"
    assert first.is_estimate is False
    assert store_datagov(session, DATAGOV_DEFS["market_arrivals"], rows) == 0


def test_store_population_matches_location(session):
    rows = normalize_datagov(POP_JSON, DATAGOV_DEFS["population"])
    n = store_datagov(session, DATAGOV_DEFS["population"], rows)
    session.flush()
    stored = session.query(PopulationStatistic).all()
    assert n == 1
    assert len(stored) == 2
    peru = [p for p in stored if p.population == 9500]
    assert peru and peru[0].location_id == "loc_peru"
    assert peru[0].level == "village"
    assert peru[0].source_type == "government"
    assert store_datagov(session, DATAGOV_DEFS["population"], rows) == 0


def test_store_unmatched_location_skips(session):
    rows = normalize_datagov(b'[{"state": "Kerala", "district": "X", "population": "100", "census_year": "2011"}]',
                             DATAGOV_DEFS["population"])
    assert store_datagov(session, DATAGOV_DEFS["population"], rows) == 0
