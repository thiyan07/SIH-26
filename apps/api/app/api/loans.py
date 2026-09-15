"""Actual loan + EMI lifecycle — deterministic, separate from Pre-Loan assumption."""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.db.models import Business, Loan, LoanPayment
from app.db.session import get_db
from app.engines.repayment import build_schedule

router = APIRouter(prefix="/user/loans", tags=["loans"])


class CreateLoanRequest(BaseModel):
    business_id: str
    lender: str | None = None
    account_ref: str | None = None
    principal: float = Field(gt=0, le=1e9)
    interest_rate: float | None = Field(default=None, ge=0, le=30)
    interest_type: str = Field(default="reducing", pattern="^(reducing|flat)$")
    start_date: date | None = None
    tenure_months: int | None = Field(default=None, ge=1, le=360)
    emi: float | None = Field(default=None, ge=0)
    frequency: str = Field(default="monthly", pattern="^(monthly|weekly)$")
    moratorium_months: int | None = Field(default=0, ge=0, le=60)


class LoanResponse(BaseModel):
    id: str
    business_id: str
    lender: str | None
    principal: float
    interest_rate: float | None
    tenure_months: int | None
    emi: float | None
    outstanding: float | None
    status: str

    class Config:
        from_attributes = True


def _calc_emi(principal: float, rate: float | None, tenure: int | None, moratorium: int = 0) -> float | None:
    if not principal or not rate or not tenure:
        return None
    try:
        sched = build_schedule(principal, rate, tenure / 12, moratorium, "interest_only_during_moratorium")
        return round(sched.monthly_emi_effective, 2)
    except Exception:
        return None


def _outstanding(loan: Loan, payments: list[LoanPayment]) -> float | None:
    if not payments:
        return float(loan.principal) if loan.principal else None
    # Last payment's outstanding, or compute via schedule if missing
    last = sorted(payments, key=lambda p: p.due_date)[-1]
    if last.outstanding is not None:
        return float(last.outstanding)
    # Deterministic fallback: principal - sum(principal_paid)
    paid = sum(float(p.principal_paid or 0) for p in payments)
    return max(0.0, float(loan.principal) - paid)


@router.post("", response_model=LoanResponse, status_code=status.HTTP_201_CREATED)
def create_loan(body: CreateLoanRequest, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    b = db.get(Business, body.business_id)
    if not b or b.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business not found")
    # Auto-calc EMI if not provided
    emi_val = body.emi
    if emi_val is None and body.interest_rate and body.tenure_months:
        emi_val = _calc_emi(body.principal, body.interest_rate, body.tenure_months, body.moratorium_months or 0)
    loan = Loan(
        business_id=body.business_id,
        user_id=current_user.id,
        lender=body.lender,
        account_ref=body.account_ref,
        principal=body.principal,
        interest_rate=body.interest_rate,
        interest_type=body.interest_type,
        start_date=body.start_date,
        tenure_months=body.tenure_months,
        emi=emi_val,
        frequency=body.frequency,
        moratorium_months=body.moratorium_months or 0,
        status="active",
    )
    if body.start_date and body.tenure_months:
        loan.maturity_date = body.start_date + timedelta(days=body.tenure_months * 30)
    db.add(loan)
    db.commit()
    db.refresh(loan)
    return {**loan.__dict__, "outstanding": float(loan.principal)}


@router.get("", response_model=list[LoanResponse])
def list_loans(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    rows = list(db.execute(select(Loan).where(Loan.user_id == current_user.id).order_by(Loan.created_at.desc())).scalars())
    out = []
    for loan in rows:
        pays = list(db.execute(select(LoanPayment).where(LoanPayment.loan_id == loan.id)).scalars())
        out.append({**loan.__dict__, "outstanding": _outstanding(loan, pays)})
    return out


@router.get("/{loan_id}", response_model=LoanResponse)
def get_loan(loan_id: str, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    loan = db.get(Loan, loan_id)
    if not loan or loan.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Loan not found")
    pays = list(db.execute(select(LoanPayment).where(LoanPayment.loan_id == loan.id)).scalars())
    return {**loan.__dict__, "outstanding": _outstanding(loan, pays)}


class CreatePaymentRequest(BaseModel):
    due_date: date
    paid_date: date | None = None
    amount: float | None = Field(default=None, ge=0)
    principal_paid: float | None = None
    interest_paid: float | None = None
    status: str | None = Field(default=None, pattern="^(on_time|late|missed|partial)?$")


@router.post("/{loan_id}/payments", status_code=status.HTTP_201_CREATED)
def add_payment(loan_id: str, body: CreatePaymentRequest, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    loan = db.get(Loan, loan_id)
    if not loan or loan.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Loan not found")
    # Compute outstanding deterministically
    existing = list(db.execute(select(LoanPayment).where(LoanPayment.loan_id == loan_id)).scalars())
    outstanding = _outstanding(loan, existing)
    # If amount and principal/interest not split, estimate
    principal_paid = body.principal_paid
    interest_paid = body.interest_paid
    if principal_paid is None and body.amount is not None and loan.interest_rate:
        # Simple split: interest = outstanding * monthly_rate, principal = amount - interest
        monthly_rate = (loan.interest_rate or 0) / 100 / 12
        interest_est = (outstanding or 0) * monthly_rate if outstanding else 0
        interest_paid = round(min(body.amount, interest_est), 2)
        principal_paid = round(body.amount - interest_paid, 2) if body.amount else None
    new_outstanding = None
    if outstanding is not None and principal_paid is not None:
        new_outstanding = max(0.0, outstanding - principal_paid)
    pay = LoanPayment(
        loan_id=loan_id,
        due_date=body.due_date,
        paid_date=body.paid_date,
        amount=body.amount,
        principal_paid=principal_paid,
        interest_paid=interest_paid,
        outstanding=new_outstanding,
        status=body.status or ("missed" if not body.paid_date else "on_time"),
        source="manual",
    )
    db.add(pay)
    db.commit()
    db.refresh(pay)
    return {"id": pay.id, "outstanding": new_outstanding, "status": pay.status}


@router.get("/{loan_id}/payments")
def list_payments(loan_id: str, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    loan = db.get(Loan, loan_id)
    if not loan or loan.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Loan not found")
    pays = list(db.execute(select(LoanPayment).where(LoanPayment.loan_id == loan_id).order_by(LoanPayment.due_date)).scalars())
    return [
        {
            "id": p.id,
            "due_date": p.due_date.isoformat() if p.due_date else None,
            "paid_date": p.paid_date.isoformat() if p.paid_date else None,
            "amount": float(p.amount) if p.amount else None,
            "principal_paid": float(p.principal_paid) if p.principal_paid else None,
            "interest_paid": float(p.interest_paid) if p.interest_paid else None,
            "outstanding": float(p.outstanding) if p.outstanding else None,
            "status": p.status,
        }
        for p in pays
    ]


@router.get("/{loan_id}/schedule")
def get_schedule(loan_id: str, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    loan = db.get(Loan, loan_id)
    if not loan or loan.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Loan not found")
    if not loan.principal or not loan.interest_rate or not loan.tenure_months:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Loan missing principal/rate/tenure")
    sched = build_schedule(float(loan.principal), float(loan.interest_rate), loan.tenure_months / 12, loan.moratorium_months or 0, "interest_only_during_moratorium")
    return {
        "monthly_emi_effective": sched.monthly_emi_effective,
        "total_repayment": sched.total_repayment,
        "total_interest": sched.total_interest,
        "schedule": [
            {"month": r.month, "payment": r.payment, "principal": r.principal, "interest": r.interest, "balance": r.balance}
            for r in sched.schedule
        ],
    }
