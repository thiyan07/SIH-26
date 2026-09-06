"""Analysis endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.db.models import AnalysisRun
from app.db.session import get_db
from app.limiter import limiter
from app.schemas import AnalysisRequest
from app.services.analysis import run_analysis

router = APIRouter(prefix="/analysis", tags=["analysis"])


@router.post("")
@limiter.limit("30/minute")
def create_analysis(request: Request, req: AnalysisRequest, db: Session = Depends(get_db)):
    try:
        evidence, run = run_analysis(db, req)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return evidence


@router.get("/list")
def list_analyses(limit: int = 20, db: Session = Depends(get_db)):
    from sqlalchemy import select as _select
    rows = list(db.execute(_select(AnalysisRun).order_by(AnalysisRun.created_at.desc()).limit(max(1, min(limit, 100)))).scalars())
    return {
        "runs": [
            {
                "analysis_id": r.id,
                "state": r.state,
                "district": r.district,
                "block": r.block,
                "village": r.village,
                "category_code": r.category_code,
                "capital_available": r.capital_available,
                "language": r.language,
                "result": r.result,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]
    }


@router.get("/{analysis_id}")
def get_analysis(analysis_id: str, db: Session = Depends(get_db)):
    run = db.get(AnalysisRun, analysis_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return {
        "analysis_id": run.id,
        "state": run.state,
        "district": run.district,
        "block": run.block,
        "village": run.village,
        "category_code": run.category_code,
        "capital_available": run.capital_available,
        "language": run.language,
        "result": run.result,
        "report_text": run.report_text,
        "created_at": run.created_at.isoformat() if run.created_at else None,
    }
