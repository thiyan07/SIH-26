"""Structured JSON-line event logging (plan §33).

Emit one JSON object per line to stderr so pipeline events can be ingested
by any log collector, keyed by `run_id` (e.g. an analysis_run id) and
labelled with a `scope` (analysis|score|rag|ai|ingest|stale). No external
dependencies; designed to be sandbox-friendly.

Usage:
    from app.log import log_event
    log_event("analysis", run_id=run.id, step="completed", overall_score=72)
"""
from __future__ import annotations

import json
import logging
import time

_LOG_ROOT = "grambiz"
_HANDLER = None


class JsonFormatter(logging.Formatter):
    """Formats a LogRecord holding a dict payload into a single JSON line."""

    def format(self, record: logging.LogRecord) -> str:
        payload = dict(getattr(record, "payload", {}) or {})
        payload.update({
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(record.created)),
            "level": record.levelname,
            "logger": record.name,
            "path": f"{record.module}:{record.lineno}",
        })
        return json.dumps(payload, default=str, ensure_ascii=False)


def _root() -> logging.Logger:
    global _HANDLER
    logger = logging.getLogger(_LOG_ROOT)
    if _HANDLER is None:
        logger.setLevel(logging.INFO)
        logger.propagate = False
        _HANDLER = logging.StreamHandler()
        _HANDLER.setFormatter(JsonFormatter())
        logger.addHandler(_HANDLER)
    return logger


def get_logger(scope: str | None = None) -> logging.Logger:
    root = _root()
    return root if not scope else root.getChild(scope)


def log_event(scope: str, run_id: str | None = None, **fields) -> None:
    payload = {"scope": scope, "run_id": run_id}
    payload.update(fields)
    get_logger(scope).info("", extra={"payload": payload})
