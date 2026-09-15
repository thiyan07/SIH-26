"""Analysis endpoints — public explore stays unauthenticated, but associates with user when token present."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user_optional
from app.db.models import AnalysisRun, User
from app.db.session import get_db
from app.limiter import limiter
from app.schemas import AnalysisRequest
from app.services.analysis import run_analysis

router = APIRouter(prefix="/analysis", tags=["analysis"])


@router.post("")
@limiter.limit("30/minute")
def create_analysis(
    request: Request,
    req: AnalysisRequest,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
):
    try:
        # Pass user_id to service so AnalysisRun can be owned (public explore remains without user)
        user_id = current_user.id if current_user else None
        evidence, run = run_analysis(db, req, user_id=user_id)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return evidence


@router.get("/list")
def list_analyses(
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
):
    from sqlalchemy import select as _select

    stmt = _select(AnalysisRun).order_by(AnalysisRun.created_at.desc()).limit(max(1, min(limit, 100)))
    # Tenant isolation: if authenticated, only own runs; else only anonymous (public) runs
    if current_user:
        stmt = stmt.where(AnalysisRun.user_id == current_user.id)
    else:
        stmt = stmt.where(AnalysisRun.user_id.is_(None))
    rows = list(db.execute(stmt).scalars())
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
                "user_id": r.user_id,
            }
            for r in rows
        ]
    }


@router.get("/{analysis_id}")
def get_analysis(
    analysis_id: str,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
):
    run = db.get(AnalysisRun, analysis_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Analysis not found")
    # If run is owned and requester is not owner, deny
    if run.user_id and (not current_user or run.user_id != current_user.id):
        raise HTTPException(status_code=403, detail="Not authorized for this analysis")
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
        "user_id": run.user_id,
    }
