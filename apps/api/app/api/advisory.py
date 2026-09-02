"""Advisory endpoints: NLP parse, scheme match, financial structure, full advisory report."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.engines.cost_templates import get_cost_template, list_categories, get_total_template_cost
from app.engines.nlp_parser import parse_free_text, to_dict as nlp_to_dict
from app.engines.scheme_eligibility import BeneficiaryProfile, match_schemes, to_dict as eligibility_to_dict
from app.engines.financial_structuring import (
    build_cost_breakdown, structure_loan, structure_financials, to_dict as financial_to_dict,
)
from app.engines.profit import simulate_model, known_categories
from app.limiter import limiter
from app.services.advisory import run_advisory, report_to_dict

from pydantic import BaseModel, Field
from typing import Optional


router = APIRouter(prefix="/advisory", tags=["advisory"])


# ── Request schemas (local to this router to avoid circular imports) ──

class NlpParseRequest(BaseModel):
    free_text: str = Field(..., min_length=1, max_length=5000)
    language: Optional[str] = Field(None, description="Override language: en|ta|hi")


class SchemeMatchRequest(BaseModel):
    state: Optional[str] = None
    district: Optional[str] = None
    block: Optional[str] = None
    village: Optional[str] = None
    business_type: Optional[str] = None
    project_cost: Optional[float] = None
    capital_available: Optional[float] = None
    age: Optional[int] = None
    annual_income: Optional[float] = None
    beneficiary_category: Optional[str] = None


class FinancialStructureRequest(BaseModel):
    state: Optional[str] = "Tamil Nadu"
    district: Optional[str] = "Erode"
    block: Optional[str] = None
    village: Optional[str] = None
    business_type: str = Field(..., min_length=1)
    scale: str = Field("micro", pattern="^(micro|small|medium)$")
    capital_available: float = Field(0, ge=0)
    project_cost: Optional[float] = None
    age: Optional[int] = None
    annual_income: Optional[float] = None
    beneficiary_category: Optional[str] = None
    preferred_scheme_code: Optional[str] = None
    custom_cost_items: Optional[dict[str, float]] = None
    location_factor: Optional[float] = None


class AdvisoryReportRequest(BaseModel):
    free_text: Optional[str] = Field(None, max_length=5000)
    state: Optional[str] = None
    district: Optional[str] = None
    block: Optional[str] = None
    village: Optional[str] = None
    business_type: Optional[str] = None
    scale: Optional[str] = None
    project_cost: Optional[float] = None
    capital_available: Optional[float] = None
    age: Optional[int] = None
    annual_income: Optional[float] = None
    beneficiary_category: Optional[str] = None
    language: Optional[str] = None


# ── Endpoints ──

@router.post("/parse")
@limiter.limit("60/minute")
def parse_nlp(request: Request, req: NlpParseRequest):
    """Parse free text in English/Tamil/Hindi into structured beneficiary data."""
    parsed = parse_free_text(req.free_text, lang_override=req.language)
    return nlp_to_dict(parsed)


@router.post("/schemes/match")
@limiter.limit("30/minute")
def match_scheme(request: Request, req: SchemeMatchRequest, db: Session = Depends(get_db)):
    """Match beneficiary profile against all government schemes."""
    profile = BeneficiaryProfile(
        state=req.state,
        district=req.district or "Erode",
        block=req.block,
        village=req.village,
        business_type=req.business_type,
        project_cost=req.project_cost,
        capital_available=req.capital_available,
        age=req.age,
        annual_income=req.annual_income,
        beneficiary_category=req.beneficiary_category,
    )
    results = match_schemes(db, profile)
    return {
        "total_schemes": len(results),
        "eligible": sum(1 for r in results if r.status == "ELIGIBLE"),
        "partially_eligible": sum(1 for r in results if r.status == "PARTIALLY_ELIGIBLE"),
        "not_eligible": sum(1 for r in results if r.status == "NOT_ELIGIBLE"),
        "insufficient_info": sum(1 for r in results if r.status == "INSUFFICIENT_INFO"),
        "matches": [eligibility_to_dict(r) for r in results],
    }


@router.post("/financial/structure")
@limiter.limit("30/minute")
def financial_structure(request: Request, req: FinancialStructureRequest, db: Session = Depends(get_db)):
    """Full financial structuring: cost breakdown + loan + EMI schedule."""
    profile = BeneficiaryProfile(
        state=req.state,
        district=req.district or "Erode",
        block=req.block,
        village=req.village,
        business_type=req.business_type,
        project_cost=req.project_cost,
        capital_available=req.capital_available,
        age=req.age,
        annual_income=req.annual_income,
        beneficiary_category=req.beneficiary_category,
        preferred_scale=req.scale,
    )
    # Get scheme eligibility first
    eligibility = match_schemes(db, profile)

    location_factor = req.location_factor if req.location_factor is not None else 1.0

    result = structure_financials(
        profile=profile,
        category_code=req.business_type,
        scale=req.scale,
        capital_available=req.capital_available,
        eligible_schemes=eligibility,
        custom_cost_items=req.custom_cost_items,
        location_factor=location_factor,
        preferred_scheme_code=req.preferred_scheme_code,
    )
    return financial_to_dict(result)


@router.post("/report")
@limiter.limit("15/minute")
def advisory_report(request: Request, req: AdvisoryReportRequest, db: Session = Depends(get_db)):
    """Generate a complete advisory report with all sections."""
    # Always forward the explicitly supplied structured fields (when present) so
    # they can supplement the free-text NLP parse rather than being discarded.
    structured_input = {
        "language": req.language or "en",
        "state": req.state,
        "district": req.district,
        "block": req.block,
        "village": req.village,
        "business_type": req.business_type,
        "scale": req.scale,
        "project_cost": req.project_cost,
        "capital_available": req.capital_available,
        "age": req.age,
        "annual_income": req.annual_income,
        "beneficiary_category": req.beneficiary_category,
    }
    # Only treat the dict as authoritative when no free text was provided; when
    # free text is present run_advisory overlays structured fields onto the parse.
    if req.free_text:
        structured_input = {k: v for k, v in structured_input.items() if v is not None}

    try:
        report = run_advisory(
            db,
            free_text=req.free_text,
            structured_input=structured_input,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    return report_to_dict(report)


# ── Utility endpoints ──

@router.get("/categories")
def advisory_categories():
    """List business categories with cost template totals."""
    return {"categories": list_categories()}


@router.get("/categories/{code}/template")
def category_template(code: str, scale: str = "micro"):
    """Get detailed cost template for a category at a given scale."""
    if scale not in ("micro", "small", "medium"):
        raise HTTPException(status_code=400, detail="scale must be micro, small, or medium")
    template = get_cost_template(code, scale)
    total = get_total_template_cost(code, scale)
    return {
        "category": code,
        "scale": scale,
        "template": template,
        "total_project_cost": total,
    }


@router.get("/categories/{code}/profit")
def category_profit_model(code: str):
    """Get profit model for a category with default inputs."""
    try:
        result = simulate_model(code)
        return {
            "category_code": code,
            "label": result.label,
            "inputs": result.inputs,
            "outputs": result.outputs,
            "is_estimate": result.is_estimate,
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
