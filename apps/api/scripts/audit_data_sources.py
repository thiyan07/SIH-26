"""CLI: score every registered data source and persist the quality ledger.

Reads live ``DataSource`` + ``DataSnapshot`` rows, computes the five quality
scores for each (source quality, freshness, completeness, verification, overall
confidence), and upserts ``data_source_quality`` ledgers. Test-safe and honest:
a source with no successful snapshot is scored low on freshness, never assumed
fresh.

Usage:
  python -m scripts.audit_data_sources            # everything
  python -m scripts.audit_data_sources --key osm  # one source
"""
from __future__ import annotations

import argparse
import logging
import sys

from app.data_source_audit import run_audit
from app.db.session import session_scope


def main(argv=None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    ap = argparse.ArgumentParser()
    ap.add_argument("--key", default=None, help="only audit this source key")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    session = session_scope()
    conn = session.__enter__()
    try:
        results = run_audit(conn)
        for key in sorted(results):
            if args.key and key != args.key:
                continue
            r = results[key]
            print(f"[{key:<22}] overall={r['overall_confidence_score']:>5} "
                  f"({r['confidence_label']:>6}) qual={r['source_quality_score']:.0f} "
                  f"fresh={r['freshness_score']:.0f}({r['freshness_status']}) "
                  f"comp={r['completeness_score']:.0f} verify={r['verification_score']:.0f} "
                  f"status={r['verification_status']}")
        return 0
    finally:
        session.__exit__(None, None, None)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
