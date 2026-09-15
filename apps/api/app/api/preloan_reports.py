"""Pre-Loan report persistence — structured, versioned, reproducible."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.db.models import AnalysisRun, Business, PreLoanReport
from app.db.session import get_db

router = APIRouter(prefix="/user/pre-loan-reports", tags=["pre-loan-reports"])


class CreateReportRequest(BaseModel):
    analysis_run_id: str = Field(description="Existing AnalysisRun id to snapshot")
    title: str | None = Field(default=None, max_length=200)
    business_id: str | None = None  # optional link to user business


class ReportResponse(BaseModel):
    id: str
    user_id: str
    business_id: str | None
    analysis_run_id: str | None
    business_type: str | None
    business_idea: str | None
    location_id: str | None
    title: str | None
    report_version: int
    created_at: str | None
    financial_snapshot: dict | None
    opportunity_snapshot: dict | None


def _to_resp(r: PreLoanReport) -> dict:
    return {
        "id": r.id,
        "user_id": r.user_id,
        "business_id": r.business_id,
        "analysis_run_id": r.analysis_run_id,
        "business_type": r.business_type,
        "business_idea": r.business_idea,
        "location_id": r.location_id,
        "title": r.title,
        "report_version": r.report_version,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "financial_snapshot": r.financial_snapshot,
        "opportunity_snapshot": r.opportunity_snapshot,
    }


@router.post("", response_model=ReportResponse, status_code=status.HTTP_201_CREATED)
def create_report(body: CreateReportRequest, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    run = db.get(AnalysisRun, body.analysis_run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AnalysisRun not found")
    # If run has owner and not current user, deny (tenant isolation)
    if run.user_id and run.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized for this analysis")
    # Claim the run if it was anonymous (public explore)
    if not run.user_id:
        run.user_id = current_user.id
        run.is_saved = True
    # Business ownership check
    if body.business_id:
        b = db.get(Business, body.business_id)
        if not b or b.owner_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business not found")

    # Derive structured snapshots from run.result (reproducible)
    result = run.result or {}
    # Extract engine versions if present
    engine_versions = run.engine_versions or {
        "finance": "2.0.0",
        "score": "2.0.0",
        "repayment": "2.0.0",
        "business_intelligence": "2.0.0",
    }
    report = PreLoanReport(
        user_id=current_user.id,
        business_id=body.business_id,
        analysis_run_id=run.id,
        business_type=run.category_code,
        business_idea=(run.inputs or {}).get("business_idea") or run.category_code,
        location_id=run.location_id,
        exact_latitude=result.get("location", {}).get("latitude") if isinstance(result.get("location"), dict) else None,
        exact_longitude=result.get("location", {}).get("longitude") if isinstance(result.get("location"), dict) else None,
        geo_precision=result.get("location", {}).get("geo_precision") if isinstance(result.get("location"), dict) else None,
        market_snapshot=result.get("market"),
        competitor_snapshot=result.get("business_competition"),
        financial_snapshot=result.get("financial_plan"),
        opportunity_snapshot=result.get("opportunity_score"),
        provenance_snapshot=result.get("data_sources"),
        engine_versions=engine_versions,
        report_version=1,
        title=body.title or f"{run.category_code or 'Business'} — {run.district}, {run.state}",
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return _to_resp(report)


@router.get("", response_model=list[ReportResponse])
def list_reports(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    rows = list(db.execute(select(PreLoanReport).where(PreLoanReport.user_id == current_user.id).order_by(PreLoanReport.created_at.desc())).scalars())
    return [_to_resp(r) for r in rows]


@router.get("/{report_id}", response_model=ReportResponse)
def get_report(report_id: str, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    r = db.get(PreLoanReport, report_id)
    if not r or r.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
    return _to_resp(r)


@router.delete("/{report_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_report(report_id: str, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    r = db.get(PreLoanReport, report_id)
    if not r or r.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
    db.delete(r)
    db.commit()
    return None
