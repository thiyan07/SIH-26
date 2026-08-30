"""data.gov.in resource normalization (plan §7).

Turns downloaded bytes (JSON / CSV / CSDL-XML) into validated rows for the
provenance-bearing fact tables, keyed by a dataset definition. Each def in
DATAGOV_DEFS documents which data.gov.in dataset it accepts, how columns map,
and the rationale (mirrored in docs/data-sources.md).

Format detection is tolerant on purpose: data.gov.in resources arrive as CSV,
JSON (list or {records:[...]}) or CSDL-XML. Values are coerced defensively so a
single bad cell drops the row instead of the whole dataset.
"""
from __future__ import annotations

import csv
import io
import json
import logging
from datetime import date, datetime, timezone
from typing import Optional

from app.db.models import (
    AgricultureStatistic,
    Location,
    MarketPrice,
    PopulationStatistic,
    WeatherStatistic,
)

log = logging.getLogger("ingest_government.normalize")

_DATE_FORMATS = (
    "%Y-%m-%d",
    "%d-%m-%Y",
    "%d/%m/%Y",
    "%Y/%m/%d",
    "%d.%m.%Y",
    "%Y-%m",
    "%b %Y",
    "%B %Y",
)

_NOTES = {
    "market_arrivals": (
        "Official market arrivals/mandi price records sourced from data.gov.in / "
        "Agmarknet; coverage limited to registered mandis."
    ),
    "population": "Population figures from a data.gov.in census-derived resource (historical).",
    "agriculture": "Crop area/production/yield from a data.gov.in agriculture resource.",
    "imd_rainfall": "Rainfall indices from IMD-published data.gov.in resources (district granularity).",
}


def _clean_header(h: str) -> str:
    return (h or "").strip().lower().replace(" ", "_").replace("-", "_")


def _coerce_number(val, as_int: bool = False):
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return int(val) if as_int else val
    text = str(val).strip().replace(",", "")
    if not text or text in ("-", "--", "na", "n/a"):
        return None
    try:
        num = float(text)
        return int(num) if as_int else num
    except ValueError:
        return None


def _coerce_date(val) -> Optional[date]:
    if val is None:
        return None
    if isinstance(val, (dict, list)):
        return None
    text = str(val).strip()
    if not text or text.lower() in ("na", "n/a", "-", "--"):
        return None
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def detect_format(data: bytes) -> Optional[str]:
    stripped = data.lstrip()
    if stripped.startswith((b"[", b"{")):
        return "json"
    if b"<csdl" in data[:2048] or data.lstrip().startswith(b"<"):
        return "xml"
    try:
        text = data[:4096].decode("utf-8", errors="ignore")
        return "csv" if "," in text or "\t" in text else None
    except Exception:
        return None


def _json_rows(data: bytes) -> list[dict]:
    parsed = json.loads(data)
    if isinstance(parsed, list):
        return [r for r in parsed if isinstance(r, dict)]
    if isinstance(parsed, dict):
        for key in ("records", "data", "rows", "result", "items"):
            value = parsed.get(key)
            if isinstance(value, list):
                return [r for r in value if isinstance(r, dict)]
    return []


def _xml_rows(data: bytes) -> list[dict]:
    import xml.etree.ElementTree as ET

    root = ET.fromstring(data)
    result = []
    for node in root.iter():
        if node.tag.lower() not in ("row", "record", "value"):
            continue
        rec = {}
        for child in node:
            tag = _clean_header(child.tag.rsplit("}", 1)[-1])
            if tag and not tag.startswith("http"):
                rec[tag] = (child.text or "").strip()
        if rec:
            result.append(rec)
    return result


def _csv_rows(data: bytes) -> list[dict]:
    text = data.decode("utf-8", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    rows = []
    for index, raw in enumerate(reader):
        if raw is None:
            continue
        row = {_clean_header(k): (v or "").strip() for k, v in raw.items() if k is not None}
        if row:
            rows.append(row)
    return rows


def parse_rows(data: bytes, fmt: Optional[str] = None) -> list[dict]:
    fmt = fmt or detect_format(data)
    if fmt == "json":
        return _json_rows(data)
    if fmt == "xml":
        try:
            return _xml_rows(data)
        except Exception as exc:
            log.warning("xml parse failed: %s", exc)
            return []
    if fmt == "csv":
        return _csv_rows(data)
    log.warning("unrecognized format; nothing parsed")
    return []


DATAGOV_DEFS: dict[str, dict] = {
    "market_arrivals": {
        "model": "market_price",
        "field_map": {
            "commodity": "item_name",
            "commodity_name": "item_name",
            "item": "item_name",
            "market": "market_name",
            "mandi": "mandi",
            "state": "state",
            "district": "district",
            "min_price": "min_price",
            "max_price": "max_price",
            "modal_price": "modal_price",
            "mod_price": "modal_price",
            "arrival_date": "reference_date",
            "dated": "reference_date",
            "date": "reference_date",
            "unit": "unit",
            "units": "unit",
        },
        "requires": ["item_name"],
        "geo_level": "mandi",
        "dataset_name": "Market arrivals (official Mandi prices)",
        "reference_period": "as reported per arrival date",
        "confidence": "medium",
        "is_estimate": False,
    },
    "population": {
        "model": "population",
        "field_map": {
            "state": "state",
            "district": "district",
            "block": "block",
            "tehsil": "block",
            "sub_district": "block",
            "village": "village",
            "town": "village",
            "population": "population",
            "total_population": "population",
            "households": "households",
            "male_population": "males",
            "female_population": "females",
            "census_year": "census_year",
            "year": "census_year",
        },
        "requires": ["population"],
        "geo_level": "village",
        "dataset_name": "Population (data.gov.in census-derived resource)",
        "reference_period": "census year",
        "confidence": "high",
        "is_estimate": False,
    },
    "agriculture": {
        "model": "agriculture",
        "field_map": {
            "state": "state",
            "district": "district",
            "crop": "crop",
            "crop_name": "crop",
            "commodity": "crop",
            "season": "season",
            "year": "season",
            "area": "area",
            "area_ha": "area",
            "production": "production",
            "production_tonnes": "production",
            "yield": "yield_value",
            "yield_per_ha": "yield_value",
            "yield_value": "yield_value",
        },
        "requires": ["crop"],
        "geo_level": "district",
        "dataset_name": "Crop area/production/yield",
        "reference_period": "crop season",
        "confidence": "medium",
        "is_estimate": False,
    },
    "imd_rainfall": {
        "model": "weather",
        "field_map": {
            "state": "state",
            "district": "district",
            "month": "period",
            "period": "period",
            "year": "period",
            "rainfall": "value",
            "rainfall_mm": "value",
            "value": "value",
            "unit": "unit",
            "units": "unit",
        },
        "requires": ["value"],
        "geo_level": "district",
        "dataset_name": "IMD rainfall",
        "reference_period": "month/period",
        "confidence": "medium",
        "is_estimate": False,
    },
}


def _apply_field_map(rec: dict, defn: dict) -> dict:
    mapped = {}
    for source_col, target in defn["field_map"].items():
        if source_col in rec:
            mapped[target] = rec[source_col]
    mapped["state"] = mapped.get("state") or rec.get("state")
    return mapped


def _coerce_row(mapped: dict, defn: dict) -> Optional[dict]:
    model = defn["model"]
    if model == "market_price":
        mapped["item_name"] = str(mapped.get("item_name") or "").strip()
        for field in ("min_price", "max_price", "modal_price"):
            mapped[field] = _coerce_number(mapped.get(field))
        mapped["reference_date"] = _coerce_date(mapped.get("reference_date"))
        mapped["unit"] = (mapped.get("unit") or None)
        return mapped if mapped["item_name"] else None
    if model == "population":
        for field in ("population", "households", "males", "females"):
            mapped[field] = _coerce_number(mapped.get(field), as_int=True)
        cy = _coerce_number(mapped.get("census_year"), as_int=True)
        mapped["census_year"] = cy or 2011
        return mapped
    if model == "agriculture":
        for field in ("area", "production", "yield_value"):
            mapped[field] = _coerce_number(mapped.get(field))
        mapped["crop"] = str(mapped.get("crop") or "").strip()
        return mapped if mapped["crop"] else None
    if model == "weather":
        mapped["value"] = _coerce_number(mapped.get("value"))
        mapped["period"] = (mapped.get("period") or None)
        if isinstance(mapped.get("period"), (int, float)):
            mapped["period"] = str(int(mapped["period"]))
        return mapped
    return None


def normalize_datagov(data: bytes, defn: dict, fmt: Optional[str] = None) -> list[dict]:
    rows = parse_rows(data, fmt)
    out = []
    for raw in rows:
        mapped = _apply_field_map(raw, defn)
        coerced = _coerce_row(mapped, defn)
        if coerced is None:
            continue
        out.append(coerced)
    seen = set()
    deduped = []
    for rec in out:
        key = tuple(sorted((k, str(v)) for k, v in rec.items() if v is not None))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(rec)
    return deduped


def _base_provenance(defn: dict, url: Optional[str]) -> dict:
    return {
        "source_name": "data.gov.in",
        "source_url": url,
        "dataset_name": defn.get("dataset_name", "data.gov.in resource"),
        "source_type": "government",
        "geographic_level": defn.get("geo_level"),
        "confidence": defn.get("confidence", "medium"),
        "methodology": _NOTES.get(defn.get("model"), ""),
        "is_estimate": defn.get("is_estimate", False),
        "is_demo": False,
        "retrieved_at": datetime.now(timezone.utc),
    }


def _resolve_location(session, state, district, block=None, village=None):
    exact = session.query(Location).filter(
        Location.state == state,
        Location.district == district,
        Location.block == block,
        Location.village == village,
    ).first()
    if exact is not None:
        return exact, "village"
    district_only = session.query(Location).filter(
        Location.state == state,
        Location.district == district,
        Location.block.is_(None),
        Location.village.is_(None),
    ).first()
    if district_only is not None:
        return district_only, "district"
    return None, None


def store_datagov(session, defn: dict, rows: list[dict], url: Optional[str] = None) -> int:
    model = defn["model"]
    base = _base_provenance(defn, url)
    n = 0
    if model == "market_price":
        for rec in rows:
            dupe = session.query(MarketPrice).filter(
                MarketPrice.item_name == rec["item_name"],
                MarketPrice.market_name == rec.get("market_name"),
                MarketPrice.state == rec.get("state"),
                MarketPrice.district == rec.get("district"),
                MarketPrice.reference_date == rec.get("reference_date"),
            ).first()
            if dupe:
                continue
            session.add(MarketPrice(
                item_name=rec["item_name"],
                category="agriculture",
                unit=rec.get("unit"),
                min_price=rec.get("min_price"),
                max_price=rec.get("max_price"),
                modal_price=rec.get("modal_price"),
                market_name=rec.get("market_name"),
                state=rec.get("state"),
                district=rec.get("district"),
                mandi=rec.get("mandi"),
                reference_date=rec.get("reference_date"),
                **base,
            ))
            n += 1
    elif model == "population":
        for rec in rows:
            loc, level = _resolve_location(
                session, rec.get("state"), rec.get("district"), rec.get("block"), rec.get("village")
            )
            if loc is None:
                log.warning("no Location match for %s/%s/%s/%s",
                            rec.get("state"), rec.get("district"), rec.get("block"), rec.get("village"))
                continue
            cy = rec.get("census_year", 2011)
            dupe = session.query(PopulationStatistic).filter(
                PopulationStatistic.location_id == loc.id,
                PopulationStatistic.census_year == cy,
            ).first()
            if dupe:
                continue
            session.add(PopulationStatistic(
                location_id=loc.id,
                level=level,
                census_year=cy,
                population=rec.get("population"),
                households=rec.get("households"),
                males=rec.get("males"),
                females=rec.get("females"),
                reference_year=cy,
                **base,
            ))
            n += 1
    else:
        for rec in rows:
            loc, level = _resolve_location(
                session, rec.get("state"), rec.get("district"), rec.get("block"), rec.get("village")
            )
            if loc is None:
                log.warning("no Location match for %s/%s", rec.get("state"), rec.get("district"))
                continue
            if model == "agriculture":
                session.add(AgricultureStatistic(
                    location_id=loc.id,
                    level=level,
                    crop=rec["crop"],
                    season=rec.get("season"),
                    area=rec.get("area"),
                    production=rec.get("production"),
                    yield_value=rec.get("yield_value"),
                    **base,
                ))
            elif model == "weather":
                session.add(WeatherStatistic(
                    location_id=loc.id,
                    level=level,
                    indicator="rainfall",
                    period=rec.get("period"),
                    value=rec.get("value"),
                    unit=rec.get("unit"),
                    **base,
                ))
            n += 1
    return n
