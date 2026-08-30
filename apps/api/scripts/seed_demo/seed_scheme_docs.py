"""Seed demo scheme documents into the RAG corpus (plan §21).

Content mirrors the assumed demo parameters from the supplied problem
statement (Micro Finance / Term Loan) and is clearly flagged demo: it is NOT
an official document. RAG citations surface this provenance.

Usage:
  python -m scripts.seed_demo.seed_scheme_docs
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.ai.rag import store_document  # noqa: E402
from app.db.session import session_scope  # noqa: E402

_DEMO_DOCS = [
    {
        "title": "Micro Finance (demo parameters, assumed from problem statement)",
        "doc_type": "scheme",
        "url": "https://example.in/schemes/demo-micro-finance",
        "dataset_name": "Demo scheme parameters (assumed)",
        "text": (
            "Micro Finance Scheme. Demo parameters assumed from the supplied "
            "problem statement (not an official document). Maximum project cost "
            "is Rs 1,40,000. Maximum loan amount is Rs 1,25,000. Interest rate "
            "6.5 percent. Repayment tenure 3 years. Moratorium 3 months. These "
            "values appear only in the demo dataset and must be replaced with an "
            "official scheme document before real use."
        ),
    },
    {
        "title": "Term Loan (demo parameters, assumed from problem statement)",
        "doc_type": "scheme",
        "url": "https://example.in/schemes/demo-term-loan",
        "dataset_name": "Demo scheme parameters (assumed)",
        "text": (
            "Term Loan Scheme. Demo parameters assumed from the supplied problem "
            "statement (not an official document). Maximum project cost is Rs "
            "50,00,000. Maximum loan amount is Rs 45,00,000. Interest rate 8 "
            "percent. Repayment tenure 7 years. Moratorium 6 months. These values "
            "appear only in the demo dataset and must be replaced with an official "
            "scheme document before real use."
        ),
    },
]


def main():
    with session_scope() as s:
        for doc in _DEMO_DOCS:
            store_document(
                s, title=doc["title"], content_text=doc["text"], url=doc["url"],
                doc_type=doc["doc_type"], dataset_name=doc["dataset_name"],
            )
    print(f"seeded {len(_DEMO_DOCS)} demo scheme documents")


if __name__ == "__main__":
    main()
