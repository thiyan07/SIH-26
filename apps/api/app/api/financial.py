"""Financial, EMI, simulate, scheme endpoints (deterministic)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import GovernmentScheme
from app.db.session import get_db
from app.engines.finance import DEFAULT_SCHEMES, SchemeRule, derive_financial_plan
from app.engines.profit import model_inputs_schema, simulate_model
from app.engines.repayment import build_schedule, repayment_health
from app.schemas import (
    EmiRequest,
    FinancialCalculateRequest,
    SchemeRecommendRequest,
    SimulateRequest,
)

router = APIRouter(tags=["financial"])


def _scheme_rules(db: Session):
    rows = list(db.execute(select(GovernmentScheme).where(GovernmentScheme.is_active.is_(True))).scalars())
    if rows:
        return tuple(
            SchemeRule(
                code=r.code, name=r.name, min_project_cost=float(r.min_project_cost) if r.min_project_cost is not None else None,
                max_project_cost=float(r.max_project_cost) if r.max_project_cost is not None else None,
                max_loan_amount=float(r.max_loan_amount) if r.max_loan_amount is not None else None,
                interest_rate=r.interest_rate if r.interest_rate is not None else 12.0,
                tenure_years=r.tenure_years if r.tenure_years is not None else 5.0,
                moratorium_months=r.moratorium_months if r.moratorium_months is not None else 0,
                margin_pct=r.margin_pct if r.margin_pct is not None else 10.0,
                moratorium_mode=r.moratorium_mode or "interest_only_during_moratorium",
                source_document=r.source_url, source_date=r.reference_date.strftime("%Y-%m-%d") if r.reference_date else None,
                note=(r.description or ""),
            )
            for r in rows
        )
    return DEFAULT_SCHEMES


@router.post("/financial/calculate")
def financial_calculate(req: FinancialCalculateRequest, db: Session = Depends(get_db)):
    rules = _scheme_rules(db)
    plan = derive_financial_plan(req.capital_available, rules)
    scheme = plan.scheme
    schedule = None
    if scheme is not None:
        schedule = build_schedule(
            principal=plan.loan_amount,
            annual_rate=scheme.interest_rate,
            tenure_years=scheme.tenure_years,
            moratorium_months=scheme.moratorium_months,
            moratorium_mode=scheme.moratorium_mode,
        )
    profit = simulate_model(req.category_code, req.model_inputs)
    health = None
    if schedule and schedule.monthly_emi_effective > 0:
        health = repayment_health(profit.outputs.get("estimated_monthly_operating_profit", 0.0),
                                  schedule.monthly_emi_effective)

    return {
        "capital_available": req.capital_available,
        "project_cost": round(plan.project_cost, 2),
        "loan_amount": round(plan.loan_amount, 2),
        "margin_pct": plan.margin_pct,
        "scheme": {
            "code": scheme.code if scheme else None,
            "name": scheme.name if scheme else None,
            "max_loan": scheme.max_loan_amount if scheme else None,
            "interest_rate": scheme.interest_rate if scheme else None,
            "tenure_years": scheme.tenure_years if scheme else None,
            "moratorium_months": scheme.moratorium_months if scheme else None,
            "moratorium_mode": scheme.moratorium_mode if scheme else None,
            "source_document": scheme.source_document if scheme else None,
            "source_date": scheme.source_date if scheme else None,
            "reason": plan.scheme_reason,
        } if scheme else {"code": None, "reason": plan.scheme_reason},
        "scheme_decision": plan.scheme_decision,
        "notes": plan.notes,
        "repayment": {
            "monthly_emi": round(schedule.monthly_emi_effective, 2) if schedule else None,
            "total_repayment": round(schedule.total_repayment, 2) if schedule else None,
            "total_interest": round(schedule.total_interest, 2) if schedule else None,
            "quarterly": schedule.quarterly if schedule else [],
            "moratorium_mode": schedule.moratorium_mode if schedule else None,
        } if schedule else None,
        "profit_model": {
            "category_code": req.category_code,
            "label": profit.label,
            "is_estimate": profit.is_estimate,
            "outputs": profit.outputs,
            "inputs_schema": model_inputs_schema(req.category_code)["inputs_schema"],
        },
        "repayment_health": health,
        "disclaimer": "Scheme parameters are demo assumptions based on the problem statement; verify with the agency.",
    }


@router.post("/financial/emi")
def financial_emi(req: EmiRequest):
    schedule = build_schedule(req.loan_amount, req.interest_rate, req.tenure_years,
                              req.moratorium_months, req.moratorium_mode)
    return {
        "loan_amount": req.loan_amount,
        "annual_rate": req.interest_rate,
        "tenure_years": req.tenure_years,
        "moratorium_months": req.moratorium_months,
        "moratorium_mode": req.moratorium_mode,
        "monthly_emi_effective": round(schedule.monthly_emi_effective, 2),
        "monthly_emi_standard": round(schedule.monthly_emi_standard, 2),
        "total_repayment": round(schedule.total_repayment, 2),
        "total_interest": round(schedule.total_interest, 2),
        "quarterly": schedule.quarterly,
        "notes": schedule.notes,
    }


@router.post("/financial/simulate")
def financial_simulate(req: SimulateRequest):
    """What-if: run baseline plus scenario variations and compare health."""
    base = build_schedule(req.loan_amount, req.interest_rate, req.tenure_years,
                          req.moratorium_months, req.moratorium_mode)
    base_health = repayment_health(req.baseline_monthly_profit, base.monthly_emi_effective)

    scenarios_out = []
    for name, delta in (req.scenarios or {}).items():
        if "profit_change_pct" in delta:
            pct = delta["profit_change_pct"]
            profit = req.baseline_monthly_profit * (1 + pct / 100.0)
            # rebuild schedule if loan inputs change
            sc_l = delta.get("loan_amount", req.loan_amount)
            sc_rate = delta.get("interest_rate", req.interest_rate)
            sc_tenure = delta.get("tenure_years", req.tenure_years)
            sc = build_schedule(sc_l, sc_rate, sc_tenure, req.moratorium_months, req.moratorium_mode)
            h = repayment_health(profit, sc.monthly_emi_effective)
            scenarios_out.append({
                "name": name,
                "profit_change_pct": pct,
                "projected_profit": round(profit, 2),
                "monthly_debt_service": round(sc.monthly_emi_effective, 2),
                "coverage_ratio": h["coverage_ratio"],
                "health_label": h["label"],
            })

    return {
        "baseline": {
            "monthly_profit": req.baseline_monthly_profit,
            "monthly_debt_service": round(base.monthly_emi_effective, 2),
            "coverage_ratio": base_health["coverage_ratio"],
            "health_label": base_health["label"],
        },
        "scenarios": scenarios_out,
        "disclaimer": base_health["disclaimer"],
    }


@router.post("/schemes/recommend")
def schemes_recommend(req: SchemeRecommendRequest, db: Session = Depends(get_db)):
    rules = _scheme_rules(db)
    # route a project of given cost directly (capital margin-independent)
    for s in rules:
        lo = s.min_project_cost if s.min_project_cost is not None else float("-inf")
        hi = s.max_project_cost if s.max_project_cost is not None else float("inf")
        if lo <= req.project_cost <= hi:
            return {
                "project_cost": req.project_cost,
                "scheme": {"code": s.code, "name": s.name,
                           "max_loan": s.max_loan_amount, "interest_rate": s.interest_rate,
                           "tenure_years": s.tenure_years, "moratorium_months": s.moratorium_months,
                           "source_document": s.source_document, "source_date": s.source_date},
                "reason": f"Project cost ₹{req.project_cost:,.0f} within {s.name} range.",
            }
    return {"project_cost": req.project_cost, "scheme": None, "reason": "No supported scheme covers this project cost."}


@router.get("/schemes")
def schemes(db: Session = Depends(get_db)):
    rules = _scheme_rules(db)
    return {
        "schemes": [
            {"code": s.code, "name": s.name, "min_project_cost": s.min_project_cost,
             "max_project_cost": s.max_project_cost, "max_loan_amount": s.max_loan_amount,
             "interest_rate": s.interest_rate, "tenure_years": s.tenure_years,
             "moratorium_months": s.moratorium_months, "moratorium_mode": s.moratorium_mode,
             "source_document": s.source_document, "source_date": s.source_date, "note": s.note}
            for s in rules
        ],
        "note": "Parameters are demo assumptions based on the problem statement; verify with the agency.",
    }


@router.get("/financial/categories")
def categories():
    from app.engines.profit import known_categories
    return {"categories": known_categories()}


@router.get("/financial/categories/{code}/profile")
def category_profile(code: str, db: Session = Depends(get_db)):
    from app.engines.category_profiles import CATEGORY_PROFILES, get_category_profile
    if code not in CATEGORY_PROFILES:
        raise HTTPException(status_code=404, detail=f"unknown category: {code}")
    return {"profile": get_category_profile(db, code)}
