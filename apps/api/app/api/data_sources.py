"""Data provenance endpoints (Phase 17: freshness/status observability)."""
from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import (
    Business,
    DataSnapshot,
    DataSource,
    Location,
    MarketPrice,
    WeatherStatistic,
)
from app.db.session import get_db
from app.provenance import freshness_for

router = APIRouter(prefix="/data-sources", tags=["data-sources"])

# Live-data providers (Phase 17 health dashboard facts). `fact` is the table
# whose row counts measure availability; `source_filters` scope the count.
LIVE_PROVIDERS = [
    {
        "key": "data_gov_in", "name": "api.data.gov.in (official market prices)",
        "fact": "market_prices", "source_fields": {"source_name": "data.gov.in"},
        "needs_keys": ["data_gov_api_key"], "refresh_cadence": "daily",
    },
    {
        "key": "acrop_mirror", "name": "Agmarknet via ACROP mirror",
        "fact": "market_prices", "source_fields": {"source_name": "Agmarknet"},
        "needs_keys": [], "refresh_cadence": "daily",
    },
    {
        "key": "openstreetmap", "name": "OpenStreetMap (businesses & infrastructure)",
        "fact": "businesses", "source_fields": {"source": "osm"},
        "needs_keys": [], "refresh_cadence": "monthly",
    },
    {
        "key": "open_meteo", "name": "Open-Meteo ERA5/forecast",
        "fact": "weather_statistics", "source_fields": {"source_name": "Open-Meteo"},
        "needs_keys": [], "refresh_cadence": "hourly",
    },
    {
        "key": "nasa_power", "name": "NASA POWER",
        "fact": "weather_statistics", "source_fields": {"source_name": "NASA POWER"},
        "needs_keys": [], "refresh_cadence": "daily",
    },
    {
        "key": "bharat_atlas", "name": "Bharat Atlas (LGD geocodes)",
        "fact": "locations", "source_fields": {"source_name": "Bharat Atlas"},
        "needs_keys": [], "refresh_cadence": "quarterly",
    },
    {
        "key": "census_2011", "name": "Census 2011 (historical baseline)",
        "fact": "population_statistics", "source_fields": {},
        "needs_keys": [], "refresh_cadence": "decadal", "is_historical": True,
    },
    {
        "key": "imd", "name": "India Meteorological Department",
        "fact": "weather_statistics", "source_fields": {"source_name": "IMD"},
        "needs_keys": ["imd_api_key"], "refresh_cadence": "hourly",
        "note": "No keyless public endpoint is available; Open-Meteo/NASA POWER are used instead.",
    },
]

_SOURCE_MODELS = {
    "market_prices": MarketPrice,
    "businesses": Business,
    "weather_statistics": WeatherStatistic,
    "locations": Location,
}


def _provider_rows(db: Session, spec: dict) -> int:
    model = _SOURCE_MODELS.get(spec["fact"])
    if model is None:
        return 0
    filters = [getattr(model, k) == v for k, v in spec.get("source_fields", {}).items()]
    return int(db.execute(select(func.count()).select_from(model).where(*filters)).scalar_one_or_none() or 0)


def _attr_value(db: Session, key: str, attr: str):
    return getattr(db.execute(select(DataSource).where(DataSource.key == key)).scalar_one_or_none(), attr, None)


def _source_status(r: DataSource) -> str:
    """Derived, honest status for a registered data source."""
    if r.is_demo:
        return "demo"
    if r.is_active is False:
        return "disabled"
    if not r.record_count:
        return "no_rows"
    note = (r.freshness_note or "").lower()
    if "unavailable" in note or "key" in note:
        return "unavailable"
    if r.reference_year and not r.reference_date:
        return "historical"
    return "operational"


@router.get("")
def list_data_sources(db: Session = Depends(get_db)):
    rows = list(db.execute(select(DataSource).order_by(DataSource.category)).scalars())
    return {
        "note": "Freshness shown per dataset. Historical baselines are labelled, never presented as current.",
        "sources": [
            {
                "key": r.key,
                "display_name": r.display_name,
                "category": r.category,
                "dataset_name": r.dataset_name,
                "source_url": r.source_url,
                "publisher": r.source_name,
                "reference_year": r.reference_year,
                "reference_date": r.reference_date.isoformat() if r.reference_date else None,
                "retrieved_at": r.retrieved_at.isoformat() if r.retrieved_at else None,
                "last_updated": r.last_updated.isoformat() if r.last_updated else None,
                "geographic_level": r.geographic_level,
                "confidence": r.confidence,
                "license_note": r.methodology,
                "is_demo": r.is_demo,
                "is_estimate": r.is_estimate,
                "record_count": r.record_count,
                "freshness_note": r.freshness_note,
                "why_used": r.why_used,
                "known_limitations": r.known_limitations or [],
            }
            for r in rows
        ],
    }


@router.get("/status")
def data_source_status(db: Session = Depends(get_db)):
    """Per-source derived freshness + status (Phase 17)."""
    rows = list(db.execute(select(DataSource).order_by(DataSource.category)).scalars())
    today = dt.date.today()
    out = []
    for r in rows:
        f = freshness_for(
            source_type=r.source_type,
            reference_date=r.last_updated.date() if r.last_updated else r.reference_date,
            reference_year=r.reference_year,
            now=today,
        )
        out.append({
            "key": r.key,
            "status": _source_status(r),
            "freshness": f,
            "last_updated": r.last_updated.isoformat() if r.last_updated else None,
            "reference_date": r.reference_date.isoformat() if r.reference_date else None,
            "reference_year": r.reference_year,
            "record_count": r.record_count,
            "is_demo": r.is_demo,
            "freshness_note": r.freshness_note,
        })
    return {"sources": out}


@router.get("/providers")
def provider_health(db: Session = Depends(get_db)):
    """Live-provider readiness: configured keys, rows in DB, latest snapshot (Phase 17)."""
    latest = db.execute(
        select(DataSnapshot).order_by(DataSnapshot.started_at.desc().nulls_last()).limit(1)
    ).scalars().first()
    providers = []
    for spec in LIVE_PROVIDERS:
        missing = [k for k in spec.get("needs_keys", []) if not getattr(settings, k, None)]
        rows = _provider_rows(db, spec)
        if missing:
            state = "config_missing"
        elif rows == 0:
            state = "no_rows"
        else:
            state = "ready"
        providers.append({
            "key": spec["key"],
            "name": spec["name"],
            "state": state,
            "rows_in_db": rows,
            "refresh_cadence": spec.get("refresh_cadence"),
            "is_historical": bool(spec.get("is_historical")),
            "missing_keys": missing,
            "note": spec.get("note"),
        })
    return {
        "providers": providers,
        "latest_snapshot": {
            "job_name": latest.job_name,
            "status": latest.status,
            "records_ingested": latest.records_ingested,
            "started_at": latest.started_at.isoformat() if latest.started_at else None,
            "finished_at": latest.finished_at.isoformat() if latest.finished_at else None,
        } if latest else None,
    }
