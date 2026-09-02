"""AI endpoints: advice, SWOT, report generation. LLM explains only."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.ai.compose import build_report, build_risks, build_swot
from app.ai.llm import SYSTEM_INSTRUCTIONS, build_evidence_prompt, get_provider
from app.db.models import AnalysisRun, Report
from app.db.session import get_db
from app.limiter import limiter
from app.schemas import AiAdviceRequest

router = APIRouter(prefix="/ai", tags=["ai"])

def _load_evidence(db, analysis_id):
    run = db.get(AnalysisRun, analysis_id)
    if run is None or not run.result:
        raise HTTPException(status_code=404, detail="Analysis not found or no evidence")
    return run.result


@router.post("/advice")
@limiter.limit("15/minute")
def ai_advice(request: Request, req: AiAdviceRequest, db: Session = Depends(get_db)):
    evidence = req.evidence if req.evidence else _load_evidence(db, req.analysis_id)
    return {"role": "assistant", "content": _run_completion(evidence, "advice", req.language)}


@router.post("/report")
@limiter.limit("15/minute")
def ai_report(request: Request, req: AiAdviceRequest, db: Session = Depends(get_db)):
    evidence = req.evidence if req.evidence else _load_evidence(db, req.analysis_id)
    content = _run_completion(evidence, "report", req.language)
    if req.analysis_id:
        db.add(Report(analysis_id=req.analysis_id, language=req.language,
                      content=evidence, markdown=content))
        db.commit()
    return {"role": "assistant", "content": content,
            "sections": build_report(evidence, req.language)}


@router.post("/swot")
@limiter.limit("15/minute")
def ai_swot(request: Request, req: AiAdviceRequest, db: Session = Depends(get_db)):
    evidence = req.evidence if req.evidence else _load_evidence(db, req.analysis_id)
    return {"swot": build_swot(evidence, req.language)}


@router.post("/risks")
@limiter.limit("15/minute")
def ai_risks(request: Request, req: AiAdviceRequest, db: Session = Depends(get_db)):
    evidence = req.evidence if req.evidence else _load_evidence(db, req.analysis_id)
    return {"risks": build_risks(evidence)}


def _run_completion(evidence, mode, language) -> str:
    provider = get_provider()
    prompt = build_evidence_prompt(evidence, mode, language)
    res = provider.complete(SYSTEM_INSTRUCTIONS, prompt, evidence)
    return res.get("content", "")
