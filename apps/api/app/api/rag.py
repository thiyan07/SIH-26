"""RAG endpoints (plan §21): document retrieval + grounded answers."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.ai.rag import answer_query, retrieve_chunks
from app.db.session import get_db
from app.schemas import RagAnswerRequest, RagRetrieveRequest

router = APIRouter(tags=["rag"])


@router.post("/rag/retrieve")
def rag_retrieve(req: RagRetrieveRequest, db: Session = Depends(get_db)):
    results = retrieve_chunks(db, req.query, k=req.k)
    return {
        "query": req.query,
        "results": results,
        "count": len(results),
        "notes": [
            "Retrieval is hybrid (portable vector cosine + keyword overlap) on ",
            "ingested scheme documents only.",
        ],
    }


@router.post("/rag/answer")
def rag_answer(req: RagAnswerRequest, db: Session = Depends(get_db)):
    return answer_query(db, req.question, language=req.language)
