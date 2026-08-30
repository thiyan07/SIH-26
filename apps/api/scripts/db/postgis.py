"""Idempotent PostGIS geometry bootstrap (plan §6).

Adds a `geom` geography(Point,4326) column to the lat/lng facts tables,
backfills it from the portable latitude/longitude columns, and creates GIST
indexes so radius/distance queries can use ST_DWithin instead of the
haversine fallback in app/geo.py.

Safe to re-run. If the PostGIS extension is unavailable (e.g. the dev
sandbox described in docs/assumptions.md §8), the script reports SKIPPED
and exits 0 — the portable haversine path in app/geo.py remains the active
implementation.

Usage: python -m scripts.db.postgis
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from sqlalchemy import text  # noqa: E402

from app.db.session import session_scope  # noqa: E402

# (table, lat_column, lon_column) pairs that carry a geom geography column.
_GEOM_TABLES = [
    ("businesses", "latitude", "longitude"),
    ("infrastructure_points", "latitude", "longitude"),
    ("locations", "latitude", "longitude"),
    ("administrative_boundaries", "latitude", "longitude"),
]


def ensure_postgis() -> bool:
    """Enable the extension; returns False when PostGIS is unavailable."""
    with session_scope() as s:
        try:
            s.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
            s.flush()
            s.execute(text("SELECT postgis_version()")).scalar()
        except Exception as e:  # noqa: BLE001
            print(f"PostGIS unavailable: {e}")
            return False
    return True


def add_geom_columns() -> None:
    with session_scope() as s:
        for table, lat, lon in _GEOM_TABLES:
            s.execute(text(
                f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS geom geography(Point,4326)"
            ))
            # Backfill from the portable coordinates (idempotent).
            s.execute(text(
                f"UPDATE {table} SET geom = ST_SetSRID(ST_MakePoint({lon}, {lat}), 4326)::geography "
                f"WHERE geom IS NULL AND {lat} IS NOT NULL AND {lon} IS NOT NULL"
            ))
            s.execute(text(
                f"CREATE INDEX IF NOT EXISTS idx_{table}_geom ON {table} USING GIST (geom)"
            ))
    print("Geometry columns backfilled and GIST indexes created.")


if __name__ == "__main__":
    print("Enabling PostGIS extension...")
    if not ensure_postgis():
        print("SKIPPED — PostGIS not available; haversine fallback in app/geo.py stays active.")
        sys.exit(0)
    add_geom_columns()
    print("PostGIS bootstrap complete.")
