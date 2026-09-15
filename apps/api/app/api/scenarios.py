"""Advanced Scenario Simulator — 4 kinds, isolated from actuals."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.db.models import Business, Forecast, Scenario
from app.db.session import get_db
from app.engines.business_health import compute_health
from app.engines.repayment import build_schedule

router = APIRouter(prefix="/user/businesses/{business_id}/scenarios", tags=["scenarios"])


class CreateScenarioRequest(BaseModel):
    base_forecast_id: str | None = None
    kind: str = Field(pattern="^(BASELINE|OPTIMISTIC|PESSIMISTIC|CUSTOM)$")
    overrides: dict = Field(default_factory=dict)  # {revenue_pct, price_pct, cogs_pct, opex_pct, production_pct, emi, tenure_months}


def _apply_overrides(base: dict, overrides: dict) -> dict:
    """Apply % overrides to forecast outputs deterministically."""
    # base outputs: revenue, expenses, profit, cash, etc.
    result = {}
    rev = base.get("revenue", [0])[0] if isinstance(base.get("revenue"), list) else base.get("revenue", 0)
    # Support revenue_pct: -20 means -20%
    rev_pct = overrides.get("revenue_pct") or overrides.get("revenue") or overrides.get("sales")
    if rev_pct is not None:
        try:
            # If value is like -20, treat as %
            pct = float(rev_pct)
            if abs(pct) < 1:  # 0.1 means 10%? ignore
                pct = pct * 100
            rev = rev * (1 + pct / 100)
        except Exception:
            pass
    # Similar for other overrides
    for k in ["revenue", "expenses", "profit", "cash_surplus"]:
        base_vals = base.get(k)
        if isinstance(base_vals, list):
            # Apply same pct to all months
            pct_key = k + "_pct" if k != "revenue" else "revenue_pct"
            pct = overrides.get(pct_key)
            if pct is not None:
                try:
                    pct_f = float(pct)
                    result[k] = [round(v * (1 + pct_f / 100), 2) for v in base_vals]
                except Exception:
                    result[k] = base_vals
            else:
                result[k] = base_vals
        else:
            result[k] = base_vals

    # EMI override
    if "emi" in overrides and overrides["emi"] is not None:
        result["emi"] = float(overrides["emi"])
    elif "interest_rate" in overrides:
        # Recompute EMI if principal known
        pass

    # Simple derived: cash = profit - emi, emi_coverage = cash / emi, health via compute_health
    # For now, keep as is; detailed calc in response
    return result


@router.post("", status_code=status.HTTP_201_CREATED)
def create_scenario(business_id: str, body: CreateScenarioRequest, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    b = db.get(Business, business_id)
    if not b or b.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business not found")
    base_fc = None
    base_outputs = {}
    if body.base_forecast_id:
        base_fc = db.get(Forecast, body.base_forecast_id)
        if not base_fc or base_fc.business_id != business_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Base forecast not found")
        base_outputs = base_fc.outputs or {}

    # If no base, use a simple baseline (revenue 50k etc.)
    if not base_outputs:
        base_outputs = {"revenue": [50000] * 6, "expenses": [30000] * 6, "profit": [20000] * 6, "cash_surplus": [5000] * 6}

    # Kind-based defaults
    overrides = dict(body.overrides)
    if body.kind == "OPTIMISTIC" and not overrides:
        overrides = {"revenue_pct": 20}
    elif body.kind == "PESSIMISTIC" and not overrides:
        overrides = {"revenue_pct": -20}
    elif body.kind == "BASELINE":
        overrides = {}

    results = _apply_overrides(base_outputs, overrides)
    # Compute health and risk for scenario
    # Simplified: use revenue/expenses/profit from first month
    rev = results.get("revenue", [0])[0] if isinstance(results.get("revenue"), list) else results.get("revenue", 0)
    exp = results.get("expenses", [0])[0] if isinstance(results.get("expenses"), list) else results.get("expenses", 0)
    profit = rev - exp if rev and exp else 0
    emi = overrides.get("emi") or (base_outputs.get("emi") if isinstance(base_outputs.get("emi"), (int, float)) else 5000)
    cash = profit - (emi or 0)
    # Health
    try:
        health = compute_health(revenue=rev, expenses=exp, profit=profit, cash_surplus=cash)
        health_score = health["score"]
        health_drivers = health["drivers"]
    except Exception:
        health_score = 50
        health_drivers = ["Scenario computed"]
    # Risk simple
    emi_coverage = cash / emi if emi else 0
    risk = "High Risk" if emi_coverage < 0.8 else "Moderate" if emi_coverage < 1.5 else "Healthy"

    results["emi_coverage"] = round(emi_coverage, 2) if emi else None
    results["repayment_risk"] = risk
    results["business_health"] = {"score": health_score, "drivers": health_drivers}

    sc = Scenario(
        business_id=business_id,
        user_id=current_user.id,
        base_forecast_id=body.base_forecast_id,
        kind=body.kind,
        overrides=overrides,
        results=results,
    )
    db.add(sc)
    db.commit()
    db.refresh(sc)
    return {"id": sc.id, "kind": sc.kind, "overrides": sc.overrides, "results": sc.results}


@router.get("")
def list_scenarios(business_id: str, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    b = db.get(Business, business_id)
    if not b or b.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business not found")
    rows = list(db.execute(select(Scenario).where(Scenario.business_id == business_id).order_by(Scenario.created_at.desc())).scalars())
    return [{"id": r.id, "kind": r.kind, "overrides": r.overrides, "results": r.results, "created_at": r.created_at.isoformat() if r.created_at else None} for r in rows]


@router.get("/{scenario_id}")
def get_scenario(business_id: str, scenario_id: str, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    sc = db.get(Scenario, scenario_id)
    if not sc or sc.business_id != business_id or sc.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scenario not found")
    return {"id": sc.id, "kind": sc.kind, "overrides": sc.overrides, "results": sc.results}
