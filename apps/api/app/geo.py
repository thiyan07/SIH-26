"""Geospatial helpers.

Radius and distance queries run through a PostGIS geography path when the
database supports it (``ST_DWithin``/``ST_Distance`` against the optional
``geom`` geography column bootstrapped by ``scripts/db/postgis.py``) and fall
back to a portable haversine SQL expression otherwise. Both branches return
the same rows ordered nearest-first and equivalent distance values; the
PostGIS path is preferred in production because it is index-backed and
scalable (no Python-side distance math for the ordering filter, no frontend
math). Capability probes are cached per process so the cost is negligible.

Only already-ingested rows are read here; there are no live external calls.
"""
from __future__ import annotations

import math
from functools import lru_cache
from typing import Any, Optional

from sqlalchemy import or_, text

# PostGIS geography point expression for bound params :lat / :lon.
_PG_POINT = "ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography"


def real_data_condition(model):
    """SQLAlchemy condition selecting REAL (non-demo / unset) records.

    Real analysis must never mix in demo/proxy rows. Rows where `is_demo`
    was never set (NULL) are treated as real so older ingests keep working.
    """
    return or_(model.is_demo.is_(None), model.is_demo.is_(False))


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in km (WGS84 sphere, mean Earth radius)."""
    r = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def distance_to(row, lat: float, lon: float) -> float:
    """Distance km from a point to a row exposing .latitude/.longitude."""
    return haversine_km(lat, lon, row.latitude, row.longitude)


def distance_expr_sql(lat: float, lon: float) -> str:
    """Portable SQL haversine expression given bound params :lat / :lon.

    Returns an expression referencing a table's `latitude`/`longitude`
    columns. Pair with bound params via sqlalchemy text().
    """
    return """
    (6371.0088 * 2 * asin(
      sqrt(
        power(sin(radians((:lat - latitude))/2), 2)
        + cos(radians(:lat)) * cos(radians(latitude))
        * power(sin(radians((:lon - longitude))/2), 2)
      )
    ))
    """


# --------------------------------------------------------------------------
# PostGIS capability detection (cached per process)
# --------------------------------------------------------------------------

def _bind_url(session) -> str:
    """Stable DB key used for the capability caches."""
    engine = session.get_bind()
    url = getattr(engine, "url", None)
    return str(url) if url is not None else "default"


@lru_cache(maxsize=8)
def _postgis_available(url: str) -> bool:
    """True when the connected database supports PostGIS.

    Probed once per database URL and cached; a probe failure is treated as
    "unavailable" so geo queries never break in a sandbox without PostGIS.
    """
    from app.db.session import session_scope

    try:
        with session_scope() as s:
            s.execute(text("SELECT postgis_version()")).scalar()
        return True
    except Exception:  # noqa: BLE001 - capability probe must never break geo
        return False


@lru_cache(maxsize=64)
def _table_has_geom(url: str, table_name: str) -> bool:
    """True when the table carries the optional `geom` geography column."""
    from app.db.session import session_scope

    try:
        with session_scope() as s:
            found = s.execute(
                text(
                    "SELECT count(*) FROM information_schema.columns "
                    "WHERE table_name = :table AND column_name = 'geom'"
                ),
                {"table": table_name},
            ).scalar()
        return bool(found)
    except Exception:  # noqa: BLE001
        return False


def _table_name(model) -> str:
    return model.__tablename__


def geography_enabled(session, model) -> bool:
    """True when PostGIS AND the table's `geom` column are present, so radius
    queries can use ST_DWithin. False otherwise (haversine fallback active)."""
    url = _bind_url(session)
    return _postgis_available(url) and _table_has_geom(url, _table_name(model))


def geo_backend_name(session, model) -> str:
    """Machine-readable name of the active radius-query backend."""
    return "postgis" if geography_enabled(session, model) else "haversine"


# --------------------------------------------------------------------------
# PostGIS query path
# --------------------------------------------------------------------------

def _radius_m(radius_km: float) -> float:
    return float(radius_km) * 1000.0


def _postgis_radius_stmt(model, lat: float, lon: float, radius_km: float,
                         filters: Optional[dict[str, Any]], limit: int,
                         real_only: bool = True):
    """Build a radius SELECT using PostGIS ST_DWithin / ST_Distance.

    Returns (statement, bound_params). Not executed here so the SQL can be
    exercised by tests without a live PostGIS database.

    The distance ordering uses ST_Distance (spheroidal geography distance,
    monotonic with the portable haversine branch for the radii this MVP
    handles), while the returned distance values always come off the same
    portable `distance_to` helper so both branches agree to the metre.
    """
    from sqlalchemy import select

    conds = [text(f"ST_DWithin(geom, {_PG_POINT}, :radius_m)")]
    for k, v in (filters or {}).items():
        conds.append(getattr(model, k) == v)
    if real_only:
        conds.append(real_data_condition(model))
    stmt = (
        select(model)
        .where(*conds)
        .order_by(text(f"ST_Distance(geom, {_PG_POINT})"))
        .limit(limit)
    )
    bound = {"lat": float(lat), "lon": float(lon), "radius_m": _radius_m(radius_km)}
    return stmt, bound


def _postgis_nearby(session, model, lat: float, lon: float, radius_km: float,
                    filters: Optional[dict[str, Any]], limit: int,
                    real_only: bool = True) -> list[Any]:
    stmt, bound = _postgis_radius_stmt(model, lat, lon, radius_km, filters, limit, real_only)
    result = session.execute(stmt, bound).scalars().all()
    return list(result)


# --------------------------------------------------------------------------
# Portable haversine query path
# --------------------------------------------------------------------------

def _haversine_nearby(session, model, lat: float, lon: float, radius_km: float,
                      filters: Optional[dict[str, Any]], limit: int,
                      real_only: bool = True) -> list[Any]:
    from sqlalchemy import select

    where_sql = distance_expr_sql(lat, lon)
    cond_sql = text(f"{where_sql} <= :radius")
    bound = {"lat": float(lat), "lon": float(lon), "radius": float(radius_km)}

    conds = []
    for k, v in (filters or {}).items():
        conds.append(getattr(model, k) == v)
    if real_only:
        conds.append(real_data_condition(model))

    stmt = select(model).where(cond_sql, *conds).order_by(text(where_sql)).limit(limit)
    result = session.execute(stmt, bound).scalars().all()
    return list(result)


# --------------------------------------------------------------------------
# Public router
# --------------------------------------------------------------------------

def find_nearby(
    session,
    model,
    lat: float,
    lon: float,
    radius_km: float,
    filters: Optional[dict[str, Any]] = None,
    limit: int = 500,
    real_only: bool = True,
) -> list[Any]:
    """Return model rows within radius_km, nearest first.

    Uses the index-backed PostGIS ST_DWithin path when the database has
    PostGIS and the table's `geom` column (bootstrap scripts/db/postgis.py);
    otherwise the portable haversine SQL expression. Either way the filter
    and radius check happen in the database.

    `real_only=True` (default) excludes demo/proxy rows so real analysis and
    map layers never mix synthetic data into real evidence.
    """
    if geography_enabled(session, model):
        return _postgis_nearby(session, model, lat, lon, radius_km, filters, limit, real_only)
    return _haversine_nearby(session, model, lat, lon, radius_km, filters, limit, real_only)


def find_nearby_with_distance(
    session,
    model,
    lat: float,
    lon: float,
    radius_km: float,
    filters: Optional[dict[str, Any]] = None,
    limit: int = 500,
    real_only: bool = True,
) -> list[tuple[Any, float]]:
    """Like find_nearby but also returns distance_km for each row.

    Distance is always computed by the portable `distance_to` helper on the
    already-filtered set, so both backends return identical values.
    """
    rows = find_nearby(session, model, lat, lon, radius_km, filters, limit, real_only)
    return [(row, distance_to(row, lat, lon)) for row in rows]
