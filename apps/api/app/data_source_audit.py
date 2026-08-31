"""Persist source-level quality scores into ``data_source_quality``.

Reads live ``DataSource`` + ``DataSnapshot`` rows, pairs each with its
declarative quality definition from ``app.data_quality``, computes the five
scores using the real age of the latest successful snapshot, and upserts a
``DataSourceQuality`` ledger row. This is the operational side of the quality
system: the pure scoring lives in ``app.data_quality`` (unit-testable in
isolation); this module bridges that to the database.
"""
from __future__ import annotations

import datetime as dt
import logging

from sqlalchemy.orm import Session

from app.data_quality import (
    SOURCE_QUALITY_CATALOG,
    SourceQualityCatalogEntry,
    score_source,
)
from app.db.models import DataSnapshot, DataSource, DataSourceQuality

log = logging.getLogger("data_source_audit")

# Map source keys to snapshot job hints so we can derive the real age.
SNAPSHOT_HINTS: dict[str, str] = {
    "osm": "osm",
    "market_prices_official": "market_prices_official",
    "udyam": "udyam_erode",
    "weather_imd": "imd_rainfall",
    "soil_health": "soil_health",
    "health_facilities": "bharatlas_health",
}


def _latest_success(conn: Session, hint: str) -> DataSnapshot | None:
    rows = (
        conn.query(DataSnapshot)
        .filter(DataSnapshot.status == "completed",
                DataSnapshot.job_name.ilike(f"%{hint}%"))
        .order_by(DataSnapshot.started_at.desc())
        .limit(1)
        .all()
    )
    return rows[0] if rows else None


def audit_source(
    conn: Session,
    source: DataSource,
    entry: SourceQualityCatalogEntry,
    age_years: float | None,
    alive: bool,
) -> dict:
    scored = score_source(entry, age_years=age_years, alive_override=alive)
    row = conn.query(DataSourceQuality).filter(
        DataSourceQuality.source_key == source.key).first()
    if row is None:
        row = DataSourceQuality(source_key=source.key)
        conn.add(row)
    row.source_name = source.display_name
    row.source_type = scored["source_type"]
    row.license_id = scored["license_id"]
    row.source_quality_score = scored["source_quality_score"]
    row.freshness_score = scored["freshness_score"]
    row.completeness_score = scored["completeness_score"]
    row.verification_score = scored["verification_score"]
    row.overall_confidence_score = scored["overall_confidence_score"]
    row.confidence_label = scored["confidence_label"]
    row.verification_status = scored["verification_status"]
    row.freshness_status = scored["freshness_status"]
    row.last_successful_sync = source.last_updated
    row.geo_resolution = scored["geo_resolution"]
    row.cadence = scored["cadence"]
    row.score_meta = {"reasons": scored["reasons"]}
    row.limitations = scored["limitations"]
    conn.flush()
    return scored


def run_audit(conn: Session) -> dict[str, dict]:
    """Score every registered DataSource and persist ledgers."""
    sources = conn.query(DataSource).all()
    by_key = {s.key: s for s in sources}
    results: dict[str, dict] = {}
    now = dt.datetime.now(dt.timezone.utc)

    for key, entry in SOURCE_QUALITY_CATALOG.items():
        source = by_key.get(key)
        hint = SNAPSHOT_HINTS.get(key)
        snap = _latest_success(conn, hint) if hint else None
        age_years = None
        alive = False
        if snap is not None and snap.finished_at is not None:
            age_days = max(0.0, (now - snap.finished_at).total_seconds() / 86400.0)
            age_years = age_days / 365.25
            alive = True
        elif source is not None and source.last_updated is not None:
            age_years = max(0.0, (now - source.last_updated).total_seconds() / 86400.0 / 365.25)
            alive = False
        scored = audit_source(conn, source, entry, age_years, alive)
        results[key] = scored
    conn.commit() if getattr(conn, "commit", None) else None
    return results
