"""Retrieval-augmented generation for scheme documents (plan §21).

Pipeline: ingest text -> chunk -> deterministic offline embeddings -> store ->
retrieve (hybrid: cosine over the portable TF-hash vector + keyword overlap)
-> grounded LLM answer with citations.

Dependency-free on purpose: the default embedding (`tf_hash_v0`) needs no model
or network and is stable across processes (MD5-bucketed word frequencies), so
the whole chain is unit-testable offline. When pgvector is available the
`document_chunks.embedding` column is created additively by `init_schema.py`;
retrieval always works from the portable `embedding_json` regardless.
"""
from __future__ import annotations

import hashlib
import math
import re
from collections import Counter

from sqlalchemy import select

from app.ai.llm import SYSTEM_INSTRUCTIONS, get_provider
from app.config import settings
from app.db.models import DocumentChunk, SchemeDocument

_WORD = re.compile(r"[a-z0-9]+")
_SENT_SPLIT = re.compile(r"(?<=[.!?।])\s+|\n+")

EMBEDDING_DIM = 1024


def tokenize(text: str) -> list[str]:
    return _WORD.findall((text or "").lower())


def _stable_bucket(word: str, dim: int) -> int:
    return int(hashlib.md5(word.encode("utf-8")).hexdigest()[:8], 16) % dim


def embed_text(text: str) -> dict:
    """Sparse deterministic TF-weighted vector: {algorithm, dim, bins:[[idx,w]]}."""
    counts = Counter(tokenize(text))
    if not counts:
        return {"algorithm": settings.embedding_mode, "dim": 0, "bins": []}
    bins = sorted(
        (_stable_bucket(word, EMBEDDING_DIM), 1.0 + math.log(count))
        for word, count in counts.items()
    )
    return {"algorithm": settings.embedding_mode, "dim": EMBEDDING_DIM, "bins": bins}


def _as_bins(vec: dict) -> dict[int, float]:
    return {idx: float(w) for idx, w in (vec or {}).get("bins", [])}


def _dot(a: dict[int, float], b: dict[int, float]) -> float:
    if len(a) > len(b):
        a, b = b, a
    return sum(val * b.get(idx, 0.0) for idx, val in a.items())


def _norm(vec: dict[int, float]) -> float:
    return math.sqrt(sum(v * v for v in vec.values())) or 1.0


def cosine_sim(a: dict, b: dict) -> float:
    va, vb = _as_bins(a), _as_bins(b)
    if not va or not vb:
        return 0.0
    return _dot(va, vb) / (_norm(va) * _norm(vb))


def keyword_overlap(text: str, query: str) -> float:
    q_terms = set(tokenize(query))
    if not q_terms:
        return 0.0
    return len(set(tokenize(text)) & q_terms) / len(q_terms)


def chunk_text(text: str, max_tokens: int = 0, overlap: int = 0) -> list[str]:
    """Greedy sentence-envelope chunking with trailing-token overlap."""
    max_tokens = max_tokens or settings.rag_chunk_tokens
    overlap = overlap or settings.rag_chunk_overlap
    sentences = [s.strip() for s in _SENT_SPLIT.split(text or "") if s.strip()]
    chunks: list[str] = []
    current: list[str] = []
    current_tokens = 0
    for sentence in sentences:
        n = len(tokenize(sentence))
        if current and current_tokens + n > max_tokens:
            chunks.append(" ".join(current))
            tail_words = tokenize(" ".join(current))[-overlap:] if overlap else []
            current = [" ".join(tail_words)] if tail_words else []
            current_tokens = len(tail_words)
        current.append(sentence)
        current_tokens += n
    if current:
        chunks.append(" ".join(current))
    return [c for c in chunks if c.strip()]


def store_document(db, *, title: str, content_text: str, url: str = None,
                   doc_type: str = None, dataset_name: str = None) -> SchemeDocument:
    """Upsert a document and (re)build its chunks with embeddings."""
    doc = db.execute(select(SchemeDocument).where(SchemeDocument.title == title)).scalars().first()
    if doc is None:
        doc = SchemeDocument(
            title=title, doc_type=doc_type, url=url,
            content_text=content_text,
            dataset_name=dataset_name or doc_type or "Scheme guideline",
            source_type="government", source_name="Government of India",
            embedding_ready=False,
        )
        db.add(doc)
        db.flush()
    else:
        doc.content_text = content_text
        doc.url = url or doc.url
        doc.doc_type = doc_type or doc.doc_type
        doc.dataset_name = dataset_name or doc.dataset_name
        old = db.execute(select(DocumentChunk).where(DocumentChunk.document_id == doc.id)).scalars().all()
        for chunk in old:
            db.delete(chunk)
        db.flush()
    chunks = chunk_text(content_text)
    for index, text in enumerate(chunks):
        db.add(DocumentChunk(
            document_id=doc.id,
            chunk_index=index,
            content=text,
            token_count=len(tokenize(text)),
            embedding_source=settings.embedding_mode,
            embedding_json=embed_text(text),
            metadata_json={"title": doc.title, "url": doc.url,
                           "doc_type": doc.doc_type, "chunk_index": index},
        ))
    doc.embedding_ready = bool(chunks)
    db.flush()
    return doc


def retrieve_chunks(db, query: str, k: int = 5, min_score: float = 0.15) -> list[dict]:
    qvec = embed_text(query)
    stmt = (
        select(DocumentChunk, SchemeDocument)
        .join(SchemeDocument, SchemeDocument.id == DocumentChunk.document_id)
        .limit(2000)
    )
    rows = db.execute(stmt).all()
    scored = []
    for chunk, doc in rows:
        vec = chunk.embedding_json or {"bins": []}
        cosine = cosine_sim(qvec, vec)
        overlap = keyword_overlap(chunk.content or "", query)
        score = 0.85 * cosine + 0.15 * overlap
        if score >= min_score:
            meta = chunk.metadata_json or {}
            scored.append({
                "chunk_index": chunk.chunk_index,
                "content": chunk.content,
                "score": round(score, 4),
                "token_count": chunk.token_count,
                "document": {
                    "title": (doc.title if doc else None) or meta.get("title") or "Untitled",
                    "url": (doc.url if doc else None) or meta.get("url"),
                    "doc_type": (doc.doc_type if doc else None) or meta.get("doc_type"),
                    "dataset_name": doc.dataset_name if doc else None,
                },
            })
    scored.sort(key=lambda r: r["score"], reverse=True)
    top = scored[:k]
    from app.log import log_event

    log_event("rag", step="retrieve", query_len=len(query or ""), k=k,
              hits=len(top), scored=len(scored))
    return top


def _citation_evidence(hits: list[dict]) -> dict:
    return {
        "rag_citations": [
            {
                "title": h["document"]["title"],
                "url": h["document"].get("url"),
                "doc_type": h["document"].get("doc_type"),
                "chunk_index": h["chunk_index"],
                "excerpt": (h["content"] or "")[:400],
            }
            for h in hits
        ]
    }


def answer_query(db, question: str, language: str = "en") -> dict:
    hits = retrieve_chunks(db, question)
    if not hits:
        from app.log import log_event

        log_event("rag", step="answer", mode="insufficient", question_len=len(question or ""))
        return {
            "answer": "No documents have been ingested yet, or none match the question. "
                      "Evidence is insufficient; nothing can be stated about this.",
            "citations": [],
            "mode": "insufficient",
        }
    evidence = _citation_evidence(hits)
    system = (
        SYSTEM_INSTRUCTIONS
        + " Answer ONLY from the retrieved document excerpts. Cite the excerpt title "
        + "and URL for every claim. If the excerpts do not answer the question, say "
        + "the evidence is insufficient."
    )
    user = (
        f"Language: {language}\n\nRETRIEVED DOCUMENTS (only source of truth):\n"
        f"{evidence}\n\nQuestion: {question}"
    )
    response = get_provider().complete(system, user, evidence)
    from app.log import log_event

    log_event("rag", step="answer", mode="grounded", language=language,
              question_len=len(question or ""), citations=len(evidence["rag_citations"]),
              provider=get_provider().name)
    return {
        "answer": response.get("content", ""),
        "citations": evidence["rag_citations"],
        "mode": "grounded",
    }
