"""Data provenance endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import DataSource
from app.db.session import get_db

router = APIRouter(prefix="/data-sources", tags=["data-sources"])


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
