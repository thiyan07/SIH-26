"""Ingest real government scheme guidelines into the RAG corpus.

Replaces the demo scheme documents (example.in URLs) with two official,
verifiable Ministry of Food Processing Industries documents that are directly
useful for Erode: the PMFME Operational Guidelines (credit-linked subsidy for
micro food-processing units, 35% of capital up to Rs 10 lakh) and the revised
One District One Product list where Erode is assigned "Turmeric based
products". Both are upstream official PDF URLs that are checked for reachability.

The existing document store + chunking/embedding pipeline (app.ai.rag) is
reused verbatim; provenance is set to the real publisher, URL and retrieval
timestamps. is_demo=False, nothing fabricated.

Usage:
  python -m scripts.ingest_government.ingest_scheme_docs
"""
from __future__ import annotations

import logging
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import pdfplumber

from app.ai.rag import store_document
from app.db.models import DataSnapshot, DocumentChunk, SchemeDocument
from app.db.session import session_scope
from app.log import log_event
from scripts.ingest_government.ingest import register_data_source

log = logging.getLogger("ingest_scheme_docs")

UA = "GramBizAI/1.0 (Erode scheme guideline ingest; keyless official govt site)"
MOFPI = "Ministry of Food Processing Industries (MoFPI), Government of India"

DOCS = [
    dict(
        file="pmfme_guidelines_english.pdf",
        title="PMFME Scheme Operational Guidelines (credit-linked subsidy for "
              "micro food processing units)",
        url="https://www.mofpi.gov.in/sites/default/files/pmfme_guidelines_english.pdf",
        doc_type="guideline",
        dataset=("Official operational guidelines of the Pradhan Mantri Formalisation "
                 "of Micro Food processing Enterprises (PMFME) scheme, 2020-25."),
    ),
    dict(
        file="odop_revised_2024.pdf",
        title="Revised One District One Product (ODOP) list for 35 States/UTs, 13.03.2024",
        url="https://www.mofpi.gov.in/sites/default/files/"
            "revised_list_of_odop_for_35_states_13.03.2024_1.pdf",
        doc_type="scheme_list",
        dataset=("Revised ODOP list of 726 districts in 35 States/UTs for the PMFME "
                 "scheme; Erode - Turmeric based products."),
    ),
]


def _cache_dir() -> Path:
    p = Path("data/ingest_cache/scheme_docs")
    p.mkdir(parents=True, exist_ok=True)
    return p


def download_pdf(url: str, dest: Path) -> None:
    if dest.exists() and dest.stat().st_size > 0:
        return
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=120) as resp:  # noqa: S310
        dest.write_bytes(resp.read())
    log.info("downloaded %s (%d bytes)", url, dest.stat().st_size)


def extract_text(path: Path) -> str:
    with pdfplumber.open(path) as pdf:
        return "\n".join((p.extract_text() or "") for p in pdf.pages)


def remove_demo_documents(session) -> int:
    docs = session.query(SchemeDocument).filter(
        (SchemeDocument.url.like("https://example.in%")) |
        (SchemeDocument.title.like("%demo%")),
    ).all()
    removed = 0
    for doc in docs:
        session.query(DocumentChunk).filter(DocumentChunk.document_id == doc.id).delete()
        session.delete(doc)
        removed += 1
    return removed


def main(argv=None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    snapshot = DataSnapshot(job_name="scheme_docs_ingest", status="running",
                            records_ingested=0, errors=0,
                            started_at=datetime.now(timezone.utc))
    with session_scope() as s:
        register_data_source(
            s, "scheme_guidelines_live",
            "Government scheme guidelines (RAG corpus)",
            "schemes", "scheme_documents",
            "Official MoFPI guidelines (PMFME + revised ODOP list) ingested with "
            "chunks + deterministic embeddings; demo documents removed.")
        removed = remove_demo_documents(s)
        log.info("removed demo scheme documents: %d", removed)

        for spec in DOCS:
            path = _cache_dir() / spec["file"]
            try:
                download_pdf(spec["url"], path)
                text = extract_text(path)
            except Exception as exc:  # noqa: BLE001
                log.error("failed to ingest %s: %s", spec["title"], exc)
                snapshot.errors += 1
                continue
            doc = store_document(
                s,
                title=spec["title"],
                content_text=text,
                url=spec["url"],
                doc_type=spec["doc_type"],
                dataset_name=spec["dataset"],
            )
            doc.source_name = MOFPI
            doc.source_url = spec["url"]
            doc.retrieved_at = datetime.now(timezone.utc)
            doc.confidence = "high"
            doc.is_demo = False
            doc.is_estimate = False
            doc.completeness = 0.9
            doc.methodology = ("Full text of the official published guideline/list "
                               "PDF, extracted and chunked verbatim.")
            chunk_count = s.query(DocumentChunk).filter(
                DocumentChunk.document_id == doc.id).count()
            snapshot.records_ingested += 1
            log.info("ingested: %s (%d chunks)", doc.title, chunk_count)
        snapshot.status = "completed"
        snapshot.finished_at = datetime.now(timezone.utc)
        s.add(snapshot)
        n_chunks = s.query(DocumentChunk).count()
    log_event("ingest", job="scheme_docs_ingest",
              records=snapshot.records_ingested, status="completed")
    log.info("scheme documents ingested; chunks now: %d", n_chunks)
    return 0


if __name__ == "__main__":
    sys.exit(main())
