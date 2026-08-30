"""Plan §33: structured JSON-line observability."""
from __future__ import annotations

import json
import logging

import pytest

from app.engines.score import compute_opportunity
from app.log import JsonFormatter, get_logger, log_event
from app.schemas import AnalysisRequest


class Capture(logging.Handler):
    def __init__(self):
        super().__init__()
        self.lines: list[str] = []

    def emit(self, record):
        self.lines.append(self.format(record))


@pytest.fixture()
def captured():
    root = get_logger()
    cap = Capture()
    cap.setFormatter(JsonFormatter())
    root.addHandler(cap)
    yield cap
    root.removeHandler(cap)


def _record(payload):
    r = logging.LogRecord("grambiz.analysis", logging.INFO, __file__, 1,
                          "", (), None)
    r.payload = payload
    return r


def test_formatter_emits_one_json_line_with_metadata():
    line = JsonFormatter().format(_record({"scope": "analysis", "run_id": "r1", "overall_score": 72}))
    data = json.loads(line)
    assert data["scope"] == "analysis"
    assert data["run_id"] == "r1"
    assert data["overall_score"] == 72
    assert "ts" in data and "level" in data and "logger" in data and "path" in data


def test_log_event_flows_through_logger(captured):
    log_event("analysis", run_id="abc", step="completed", overall=72)
    assert len(captured.lines) == 1
    data = json.loads(captured.lines[0])
    assert data["scope"] == "analysis"
    assert data["run_id"] == "abc"
    assert data["step"] == "completed"


def test_log_event_without_run_id(captured):
    log_event("stale", population_freshness="stale", years_since_census=15)
    data = json.loads(captured.lines[0])
    assert data["run_id"] is None
    assert data["population_freshness"] == "stale"


def test_analysis_emits_start_stale_and_completed(session, captured):
    req = AnalysisRequest(
        state="Tamil Nadu", district="Erode", block="Sathyamangalam",
        village="Sathyamangalam", capital_available=100000,
        category_code="dairy", language="en",
    )
    from app.services.analysis import run_analysis

    evidence, run = run_analysis(session, req)
    events = [json.loads(ln) for ln in captured.lines]
    assert any(e["scope"] == "analysis" and e["step"] == "start" for e in events)
    assert any(e["scope"] == "stale" for e in events)
    completed = [e for e in events if e["scope"] == "analysis" and e["step"] == "completed"]
    assert completed and completed[0]["run_id"] == run.id
    assert completed[0]["overall_score"] == evidence["opportunity_score"]["overall_score"]


def test_score_event_emitted(captured):
    result = compute_opportunity(demand=70, competition=60, accessibility=80,
                                 financial_fit=65, risk=30)
    data = json.loads(captured.lines[0])
    assert data["scope"] == "score"
    assert data["overall"] == result.overall_score
    assert data["recommendation"] == result.recommendation
