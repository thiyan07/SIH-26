"""Business Setup & Operating Plan endpoints."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AnalysisRun, BusinessSetupPlan
from app.db.session import get_db
from app.engines.business_setup import available_models, build_setup_plan

router = APIRouter(prefix="/business-setup", tags=["business-setup"])


@router.get("/plan")
def get_plan_for_analysis(
    analysis_id: str = Query(..., description="AnalysisRun id"),
    model: Optional[str] = None,
    db: Session = Depends(get_db),
):
    run = db.get(AnalysisRun, analysis_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Analysis not found")
    result = run.result or {}
    # Prefer stored plan if matching model, else rebuild deterministically
    stored = result.get("business_setup_plan")
    if stored and (model is None or stored.get("model") == model):
        return {"analysis_id": analysis_id, "plan": stored, "version": result.get("business_setup_plan_version", 1)}

    # Rebuild from analysis context without re-running full analysis
    category = result.get("cost_breakdown", {}).get("category_code") or run.category_code
    scale = result.get("cost_breakdown", {}).get("scale") or "micro"
    loc_factor = result.get("cost_breakdown", {}).get("location_factor", 1.0)
    cap = float(run.capital_available or 0)
    # Fetch plan from DB if exists
    existing = db.execute(select(BusinessSetupPlan).where(BusinessSetupPlan.analysis_run_id == analysis_id).order_by(BusinessSetupPlan.version.desc())).scalars().first()
    if existing and (model is None or existing.model_code == model):
        return {"analysis_id": analysis_id, "plan": existing.plan_json, "version": existing.version}

    # Build deterministically
    plan = build_setup_plan(
        category_code=category,
        scale=scale,
        model=model,
        location_factor=loc_factor,
        capital_available=cap,
        monthly_economics_dict=result.get("monthly_economics"),
        financial_plan=result.get("financial_plan"),
        seasonal=result.get("seasonal_intelligence"),
        infrastructure=result.get("infrastructure"),
        market_evidence=result.get("price"),
    )
    return {"analysis_id": analysis_id, "plan": plan, "version": 1}


@router.post("/plan/calculate")
def calculate_plan(
    category_code: str,
    scale: str = "micro",
    model: Optional[str] = None,
    capital_available: float = 0,
    location_factor: float = 1.0,
    state: Optional[str] = None,
    district: Optional[str] = None,
    db: Session = Depends(get_db),
):
    # Direct calculation without analysis — uses same deterministic engine
    # Optionally enrich with location-aware evidence if state/district provided
    market_evidence = None
    infrastructure = None
    try:
        if state and district:
            from app.engines.prices import derive_price_evidence
            market_evidence = derive_price_evidence(db, district=district, category_code=category_code)
    except Exception:
        market_evidence = None

    # Economics for targets (month rev via business_intelligence defaults)
    try:
        from app.engines.business_intelligence import monthly_economics, monthly_economics_to_dict
        econ = monthly_economics(category_code, emi=0)
        econ_dict = monthly_economics_to_dict(econ)
    except Exception:
        econ_dict = None

    try:
        from app.engines.business_intelligence import seasonal_intelligence
        seasonal = seasonal_intelligence(category_code)
    except Exception:
        seasonal = None

    plan = build_setup_plan(
        category_code=category_code,
        scale=scale,
        model=model,
        location_factor=location_factor,
        capital_available=capital_available,
        monthly_economics_dict=econ_dict,
        financial_plan=None,
        seasonal=seasonal,
        infrastructure=infrastructure,
        market_evidence=market_evidence,
    )
    return {"plan": plan}


@router.get("/models/{category_code}")
def list_models(category_code: str):
    return {"category_code": category_code, "models": available_models(category_code)}


@router.get("/plan/versions/{analysis_id}")
def list_versions(analysis_id: str, db: Session = Depends(get_db)):
    rows = db.execute(select(BusinessSetupPlan).where(BusinessSetupPlan.analysis_run_id == analysis_id).order_by(BusinessSetupPlan.version.asc())).scalars().all()
    return {
        "analysis_id": analysis_id,
        "versions": [
            {
                "id": r.id,
                "version": r.version,
                "category_code": r.category_code,
                "model_code": r.model_code,
                "scale": r.scale,
                "capital_available": float(r.capital_available) if r.capital_available else None,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "plan": r.plan_json,
            }
            for r in rows
        ],
    }


@router.get("/kpis/{category_code}")
def get_kpis(category_code: str):
    from app.engines.business_setup import DEFAULT_KPIS, KPI_DEFS
    kpis = KPI_DEFS.get(category_code, DEFAULT_KPIS)
    return {"category_code": category_code, "kpis": kpis}
