"""Ingest scheme/guideline documents into the RAG corpus (plan §21).

Text and Markdown are ingested directly. PDF files are extracted only when
`pypdf` is installed (optional dependency), otherwise ingestion stops with a
clear message rather than silently producing empty chunks.

Usage:
  python -m scripts.ingest_docs.ingest --file scheme.txt \
      --title "Micro Finance - scheme guideline" --url https://... \
      --doc-type guideline [--dataset-name "e.g. Scheme guideline"]
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.ai.rag import store_document  # noqa: E402
from app.db.session import session_scope  # noqa: E402

log = logging.getLogger("ingest_docs")


def extract_text(file_path: Path) -> str:
    suffix = file_path.suffix.lower()
    if suffix in (".txt", ".md", ".markdown"):
        return file_path.read_text(encoding="utf-8", errors="replace")
    if suffix == ".pdf":
        try:
            from pypdf import PdfReader  # type: ignore
        except ImportError as exc:
            raise SystemExit(
                "PDF ingestion requires the optional 'pypdf' package: pip install pypdf"
            ) from exc
        reader = PdfReader(str(file_path))
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    raise SystemExit(f"unsupported file type: {suffix} (supported: .txt .md .pdf)")


def main():
    ap = argparse.ArgumentParser(description="Ingest documents into the RAG corpus")
    ap.add_argument("--file", required=True, help="path to .txt/.md/.pdf document")
    ap.add_argument("--title", help="document title (defaults to filename stem)")
    ap.add_argument("--url")
    ap.add_argument("--doc-type", default="guideline",
                    choices=["guideline", "notification", "circular", "scheme", "faq"])
    ap.add_argument("--dataset-name", default="Scheme guideline")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO)
    file_path = Path(args.file)
    content = extract_text(file_path)
    title = args.title or file_path.stem
    with session_scope() as s:
        doc = store_document(
            s, title=title, content_text=content, url=args.url,
            doc_type=args.doc_type, dataset_name=args.dataset_name,
        )
    log.info("ingested %r: %d chars, embedding_ready=%s", title, len(content), doc.embedding_ready)


if __name__ == "__main__":
    main()
