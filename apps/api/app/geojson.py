"""GeoJSON FeatureCollection builders for map layers (plan §26).

Builds point FeatureCollections from the portable latitude/longitude columns
of the provenance-tagged facts tables. This keeps the map layer contract
independent of whether PostGIS geometry columns exist (see
scripts/db/postgis.py, which adds `geom` geography columns when available);
the served GeoJSON is always derived from the same record-level provenance
it carries in each feature's properties.

Feature properties are restricted to provenance-safe values (identifier,
kind/category, distance, source, confidence, completeness) and nothing that
would be invented.
"""
from __future__ import annotations

from typing import Any


def _point(latitude: float, longitude: float) -> dict:
    return {"type": "Point", "coordinates": [float(longitude), float(latitude)]}


def businesses_feature_collection(rows: list[tuple[Any, float]]) -> dict:
    """FeatureCollection from (Business, distance_km) pairs."""
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "id": b.id,
                    "name": b.name,
                    "category": b.category_code,
                    "subcategory": b.subcategory,
                    "distance_km": round(d, 2),
                    "source_name": b.source_name,
                    "source_type": b.source_type,
                    "confidence": b.confidence,
                    "completeness": b.completeness,
                },
                "geometry": _point(b.latitude, b.longitude),
            }
            for b, d in rows
        ],
    }


def infrastructure_feature_collection(rows: list[tuple[Any, float]]) -> dict:
    """FeatureCollection from (InfrastructurePoint, distance_km) pairs."""
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "id": i.id,
                    "kind": i.kind,
                    "name": i.name,
                    "distance_km": round(d, 2),
                    "source_name": i.source_name,
                    "source_type": i.source_type,
                    "confidence": i.confidence,
                    "completeness": i.completeness,
                },
                "geometry": _point(i.latitude, i.longitude),
            }
            for i, d in rows
        ],
    }


def empty_feature_collection() -> dict:
    return {"type": "FeatureCollection", "features": []}
