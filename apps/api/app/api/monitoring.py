"""Monitoring — metrics, health, risk alerts."""
from __future__ import annotations

from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.db.models import Business, BusinessHealthSnapshot, BusinessMetric, RiskAlert
from app.db.session import get_db
from app.engines.business_health import compute_health
from app.engines.risk import evaluate_risks

router = APIRouter(prefix="/user/businesses/{business_id}", tags=["monitoring"])


class CreateMetricRequest(BaseModel):
    period: date = Field(description="Month start YYYY-MM-01")
    revenue: float | None = None
    expenses: float | None = None
    profit: float | None = None
    cash_surplus: float | None = None
    units_produced: int | None = None
    units_sold: int | None = None
    demand_score: float | None = Field(default=None, ge=0, le=100)
    competition_count: int | None = None
    market_score: float | None = Field(default=None, ge=0, le=100)
    emi_paid: float | None = None
    emi_status: str | None = Field(default=None, pattern="^(on_time|late|missed)?$")
    notes: str | None = None


@router.post("/metrics", status_code=status.HTTP_201_CREATED)
def create_metric(business_id: str, body: CreateMetricRequest, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    b = db.get(Business, business_id)
    if not b or b.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business not found")
    # Profit fallback
    profit = body.profit
    if profit is None and body.revenue is not None and body.expenses is not None:
        profit = body.revenue - body.expenses
    cash = body.cash_surplus
    if cash is None and profit is not None and body.emi_paid is not None:
        cash = profit - body.emi_paid
    m = BusinessMetric(
        business_id=business_id,
        user_id=current_user.id,
        period=body.period,
        revenue=body.revenue,
        expenses=body.expenses,
        profit=profit,
        cash_surplus=cash,
        units_produced=body.units_produced,
        units_sold=body.units_sold,
        demand_score=body.demand_score,
        competition_count=body.competition_count,
        market_score=body.market_score,
        emi_paid=body.emi_paid,
        emi_status=body.emi_status,
        notes=body.notes,
        source="manual",
    )
    db.add(m)
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        # Unique violation → already exists for this period
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Metric for this period already exists") from e
    db.refresh(m)
    return {"id": m.id, "period": m.period.isoformat(), "revenue": float(m.revenue) if m.revenue else None}

@router.get("/metrics")
def list_metrics(business_id: str, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    b = db.get(Business, business_id)
    if not b or b.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business not found")
    rows = list(db.execute(select(BusinessMetric).where(BusinessMetric.business_id == business_id).order_by(BusinessMetric.period)).scalars())
    return [
        {
            "id": r.id,
            "period": r.period.isoformat(),
            "revenue": float(r.revenue) if r.revenue else None,
            "expenses": float(r.expenses) if r.expenses else None,
            "profit": float(r.profit) if r.profit else None,
            "cash_surplus": float(r.cash_surplus) if r.cash_surplus else None,
            "emi_paid": float(r.emi_paid) if r.emi_paid else None,
            "demand_score": float(r.demand_score) if r.demand_score else None,
            "competition_count": r.competition_count,
            "notes": r.notes,
        }
        for r in rows
    ]


@router.post("/health/recalculate", status_code=status.HTTP_201_CREATED)
def recalculate_health(business_id: str, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    b = db.get(Business, business_id)
    if not b or b.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business not found")
    # Fetch last two metrics for trend
    metrics = list(db.execute(select(BusinessMetric).where(BusinessMetric.business_id == business_id).order_by(BusinessMetric.period.desc()).limit(2)).scalars())
    if not metrics:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No metrics yet — add at least one month")
    latest = metrics[0]
    prev = metrics[1] if len(metrics) > 1 else None
    # Also fetch latest loan for repayment health
    from app.db.models import Loan
    loan = db.execute(select(Loan).where(Loan.business_id == business_id, Loan.user_id == current_user.id).order_by(Loan.created_at.desc())).scalars().first()
    repay_label = None
    if loan and latest.emi_paid is not None and latest.cash_surplus is not None:
        # Simple health: cash vs emi
        if latest.cash_surplus >= (loan.emi or 0):
            repay_label = "Healthy"
        elif latest.cash_surplus >= 0:
            repay_label = "Moderate"
        else:
            repay_label = "High Risk"

    result = compute_health(
        revenue=float(latest.revenue) if latest.revenue else None,
        revenue_prev=float(prev.revenue) if prev and prev.revenue else None,
        expenses=float(latest.expenses) if latest.expenses else None,
        expenses_prev=float(prev.expenses) if prev and prev.expenses else None,
        profit=float(latest.profit) if latest.profit else None,
        profit_prev=float(prev.profit) if prev and prev.profit else None,
        cash_surplus=float(latest.cash_surplus) if latest.cash_surplus else None,
        cash_prev=float(prev.cash_surplus) if prev and prev.cash_surplus else None,
        demand_score=float(latest.demand_score) if latest.demand_score else None,
        competition_level=None,
        repayment_health=repay_label,
        as_of=latest.period,
    )
    snap = BusinessHealthSnapshot(
        business_id=business_id,
        user_id=current_user.id,
        as_of=latest.period,
        score=int(result["score"]),
        dimensions=result["dimensions"],
        weights_version=result["weights_version"],
        drivers=result["drivers"],
        explanation=result["explanation"],
    )
    db.add(snap)
    try:
        db.commit()
    except Exception:
        db.rollback()
        # If already exists for this period, update
        existing = db.execute(select(BusinessHealthSnapshot).where(BusinessHealthSnapshot.business_id == business_id, BusinessHealthSnapshot.as_of == latest.period)).scalars().first()
        if existing:
            existing.score = int(result["score"])
            existing.dimensions = result["dimensions"]
            existing.drivers = result["drivers"]
            existing.explanation = result["explanation"]
            db.commit()
            db.refresh(existing)
            return {"id": existing.id, "score": existing.score, "as_of": existing.as_of.isoformat(), "explanation": existing.explanation, "drivers": existing.drivers}
        raise
    db.refresh(snap)
    # Auto-evaluate risks after health calc
    _ = _evaluate_and_store_risks(db, b, latest, prev, loan, current_user.id)
    return {"id": snap.id, "score": snap.score, "as_of": snap.as_of.isoformat(), "explanation": snap.explanation, "drivers": snap.drivers}


def _evaluate_and_store_risks(db, business, latest: BusinessMetric, prev: BusinessMetric | None, loan, user_id: str):
    metrics = {
        "revenue": float(latest.revenue) if latest.revenue else None,
        "revenue_prev": float(prev.revenue) if prev and prev.revenue else None,
        "profit": float(latest.profit) if latest.profit else None,
        "profit_prev": float(prev.profit) if prev and prev.profit else None,
        "expenses": float(latest.expenses) if latest.expenses else None,
        "expenses_prev": float(prev.expenses) if prev and prev.expenses else None,
        "cash_surplus": float(latest.cash_surplus) if latest.cash_surplus else None,
        "demand_score": float(latest.demand_score) if latest.demand_score else None,
        "competition_count": latest.competition_count,
        "competition_prev": prev.competition_count if prev else None,
        "emi": float(loan.emi) if loan and loan.emi else None,
    }
    alerts = evaluate_risks(business_id=business.id, metrics=metrics, business_type=business.category_code)
    for a in alerts:
        # Dedupe by dedupe_key
        exists = db.execute(select(RiskAlert).where(RiskAlert.dedupe_key == a["dedupe_key"])).scalars().first()
        if exists:
            continue
        ra = RiskAlert(
            business_id=business.id,
            user_id=user_id,
            alert_type=a["alert_type"],
            severity=a["severity"],
            detected_at=a["detected_at"],
            metrics=a["metrics"],
            threshold=a["threshold"],
            model_version=a["model_version"],
            explanation=a["explanation"],
            recommended_action=a["recommended_action"],
            status="OPEN",
            dedupe_key=a["dedupe_key"],
        )
        db.add(ra)
    try:
        db.commit()
    except Exception:
        db.rollback()
    return alerts


@router.get("/health/history")
def health_history(business_id: str, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    b = db.get(Business, business_id)
    if not b or b.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business not found")
    rows = list(db.execute(select(BusinessHealthSnapshot).where(BusinessHealthSnapshot.business_id == business_id).order_by(BusinessHealthSnapshot.as_of)).scalars())
    return [
        {"id": r.id, "as_of": r.as_of.isoformat(), "score": r.score, "drivers": r.drivers, "explanation": r.explanation, "weights_version": r.weights_version}
        for r in rows
    ]


@router.get("/alerts")
def list_alerts(business_id: str, status: str | None = None, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    b = db.get(Business, business_id)
    if not b or b.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business not found")
    stmt = select(RiskAlert).where(RiskAlert.business_id == business_id).order_by(RiskAlert.detected_at.desc())
    if status:
        stmt = stmt.where(RiskAlert.status == status.upper())
    rows = list(db.execute(stmt).scalars())
    return [
        {
            "id": r.id,
            "alert_type": r.alert_type,
            "severity": r.severity,
            "detected_at": r.detected_at.isoformat() if r.detected_at else None,
            "metrics": r.metrics,
            "threshold": r.threshold,
            "explanation": r.explanation,
            "recommended_action": r.recommended_action,
            "status": r.status,
            "dedupe_key": r.dedupe_key,
        }
        for r in rows
    ]


@router.post("/alerts/{alert_id}/ack", status_code=status.HTTP_200_OK)
def ack_alert(business_id: str, alert_id: str, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    ra = db.get(RiskAlert, alert_id)
    if not ra or ra.business_id != business_id or ra.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")
    ra.status = "ACKNOWLEDGED"
    db.commit()
    return {"id": ra.id, "status": ra.status}


@router.post("/alerts/{alert_id}/resolve", status_code=status.HTTP_200_OK)
def resolve_alert(business_id: str, alert_id: str, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    ra = db.get(RiskAlert, alert_id)
    if not ra or ra.business_id != business_id or ra.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")
    ra.status = "RESOLVED"
    ra.resolved_at = datetime.now(timezone.utc)
    db.commit()
    return {"id": ra.id, "status": ra.status}
