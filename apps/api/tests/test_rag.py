"""Plan §21: RAG pipeline (chunking, embeddings, retrieval, grounded answers)."""
from __future__ import annotations

from app.ai.rag import (
    answer_query,
    chunk_text,
    cosine_sim,
    embed_text,
    keyword_overlap,
    retrieve_chunks,
    store_document,
    tokenize,
)
from app.db.models import DocumentChunk, SchemeDocument

_SCHEME = (
    "Micro Finance Scheme guideline. The scheme supports rural enterprises. "
    "Maximum project cost is Rs 1,40,000. Maximum loan amount is Rs 1,25,000. "
    "The interest rate is 6.5 percent per annum. Repayment tenure is 3 years. "
    "A moratorium of 3 months may be granted. Eligibility includes families "
    "living in villages. These are assumed demo parameters from the problem "
    "statement and are not an official government document."
)


def _seed_doc(session):
    return store_document(
        session, title="Micro Finance (demo)", content_text=_SCHEME,
        url="https://example.in/schemes/micro-finance", doc_type="scheme",
        dataset_name="Demo scheme parameters (assumed)",
    )


def test_tokenize_and_embedding_stable_across_calls():
    vec = embed_text(_SCHEME)
    assert vec["algorithm"] == "tf_hash_v0"
    assert vec["dim"] == 1024
    assert vec["bins"]
    assert embed_text(_SCHEME) == vec
    assert tokenize("Milk Rs. 40 /litre!") == ["milk", "rs", "40", "litre"]


def test_cosine_similarity_ranks_similar_text_high():
    a = embed_text("loan amount is Rs 1,25,000 with interest rate 6.5 percent")
    b = embed_text("loan amount rules for interest rate and repayment tenure")
    c = embed_text("festivals celebrations fairs mela")
    assert cosine_sim(a, b) > 0.3
    assert cosine_sim(a, c) < 0.1
    assert cosine_sim(a, {}) == 0.0


def test_keyword_overlap():
    assert keyword_overlap("The loan tenure is 3 years", "loan tenure") == 1.0
    assert keyword_overlap("completely unrelated text here", "loan tenure") == 0.0


def test_chunk_text_respects_budget_and_overlap():
    text = "One sentence has seven words. " * 3 + "Another sentence has seven words."
    chunks = chunk_text(text, max_tokens=10, overlap=3)
    assert len(chunks) >= 2
    for chunk in chunks:
        assert len(tokenize(chunk)) <= 10 + 3
    if len(chunks) > 1:
        assert any(w in tokenize(chunks[1]) for w in tokenize(chunks[0])[-3:])


def test_chunk_single_sentence_not_split():
    assert chunk_text("short sentence here", max_tokens=100) == ["short sentence here"]


def test_store_document_creates_chunks_with_embeddings(session):
    doc = _seed_doc(session)
    session.flush()
    chunks = session.query(DocumentChunk).filter(DocumentChunk.document_id == doc.id).all()
    assert chunks
    assert doc.embedding_ready is True
    for chunk in chunks:
        assert chunk.embedding_json and chunk.embedding_json["bins"]
        assert chunk.token_count
        assert chunk.embedding_source == "tf_hash_v0"
        assert chunk.metadata_json["title"] == "Micro Finance (demo)"


def test_store_document_upsert_replaces_chunks(session):
    first = _seed_doc(session)
    session.flush()
    count_before = len(session.query(DocumentChunk).filter(DocumentChunk.document_id == first.id).all())
    second = store_document(session, title="Micro Finance (demo)", content_text=_SCHEME + " Extra details here.")
    session.flush()
    count_after = len(session.query(DocumentChunk).filter(DocumentChunk.document_id == second.id).all())
    assert second.id == first.id
    assert count_after == count_before  # replaced, not accumulated


def test_retrieve_ranks_query_matching_chunk_first(session):
    store_document(session, title="Dairy Cooperative",
                   content_text="Milk collection and dairy cooperative support for rural farmers. "
                                "Dairy farming requires veterinary care and feed management. "
                                "We help dairy farmers with loans.")
    session.flush()
    hits = retrieve_chunks(session, "dairy farmers loan milk collection donation", k=5)
    assert hits
    top = hits[0]
    assert top["document"]["title"] == "Dairy Cooperative"
    assert top["score"] > 0
    assert top["content"]


def test_retrieve_returns_citations_with_url(session):
    _seed_doc(session)
    session.flush()
    hits = retrieve_chunks(session, "maximum loan amount for micro finance", k=3)
    assert hits
    doc = hits[0]["document"]
    assert doc["url"] == "https://example.in/schemes/micro-finance"
    assert doc["dataset_name"] == "Demo scheme parameters (assumed)"
    assert doc["doc_type"] == "scheme"


def test_retrieve_empty_without_docs(session):
    assert retrieve_chunks(session, "loan rate tenure") == []


def test_answer_query_insufficient_when_no_docs(session):
    out = answer_query(session, "what are the scheme rules?")
    assert out["mode"] == "insufficient"
    assert out["citations"] == []
    assert "insufficient" in out["answer"].lower()


def test_answer_query_grounded_with_citations(session):
    _seed_doc(session)
    session.flush()
    out = answer_query(session, "maximum loan amount and interest rate for micro finance")
    assert out["mode"] == "grounded"
    assert out["citations"]
    assert all(c["title"] for c in out["citations"])
    assert out["answer"]
    assert "Excerpt" in out["answer"]


def test_scheme_document_persisted_in_corpus(session):
    _seed_doc(session)
    session.flush()
    docs = session.query(SchemeDocument).all()
    assert len(docs) == 1
    assert docs[0].content_text.startswith("Micro Finance Scheme guideline")
