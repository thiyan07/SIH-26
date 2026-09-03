"""Tests for the AI-powered multilingual extractor (app.ai.extractor).

Covers:
  * Transparent fallback to the deterministic regex parser when no LLM is set.
  * LLM-driven extraction when a provider is configured (via a fake provider).
  * Multilingual (En / Ta / Hi / Tanglish) handling.
  * Input validation / clamping so the LLM can never inject absurd figures.
  * Provenance flags surfaced on the parsed confidence dict.
"""
from __future__ import annotations

from app.ai import extractor as ex
from app.engines.nlp_parser import parse_free_text


def test_fallback_regex_when_mock_provider():
    # conftest sets LLM_PROVIDER=mock with no key, so the extractor must fall
    # back to the deterministic regex parser and still parse multilingual input.
    p = ex.parse_multilingual_free_text(
        "எனக்கு பவானியில் 5 லட்சம் ரூபாயில் ஒரு பால் பண்ணை ஆரம்பிக்கணும்."
    )
    assert p.confidence["engine"] == "regex"
    assert p.confidence["llm_available"] is False
    assert p.business_type == "dairy"
    assert p.location["block"] == "Bhavani"
    assert p.project_cost == 500000.0


def test_parse_free_text_still_works_directly():
    # The low-level regex parser is unchanged.
    p = parse_free_text("Can I start a dairy farm in Bhavani with a budget of five lakh rupees?")
    assert p.business_type == "dairy"
    assert p.location["block"] == "Bhavani"
    assert p.project_cost == 500000.0


class FakeLLM:
    """Deterministic fake provider that returns a canned JSON payload."""

    name = "fake"

    def __init__(self, payload: str):
        self.payload = payload

    def complete(self, system, user, evidence):
        return {"content": self.payload}


_GOOD_JSON = (
    '```json\n'
    '{"business_type": "dairy", "scale": "small", '
    '"project_cost": 200000, "capital_available": 50000, '
    '"annual_income": 120000, "age": 32, '
    '"beneficiary_category": "women", '
    '"state": "Tamil Nadu", "district": "Erode", '
    '"block": "Perundurai", "village": "Surampatti"}\n'
    '```'
)


def _patch_llm(monkeypatch, payload=_GOOD_JSON):
    monkeypatch.setattr(ex, "_is_llm_available", lambda: True)
    monkeypatch.setattr(ex, "get_provider", lambda: FakeLLM(payload))


def test_llm_driven_parse(monkeypatch):
    _patch_llm(monkeypatch)
    p = ex.parse_multilingual_free_text(
        "I want to start a dairy business in Perundurai, Erode with 2 lakh budget."
    )
    assert p.confidence["engine"] == "llm"
    assert p.business_type == "dairy"
    assert p.scale == "small"
    assert p.project_cost == 200000.0
    assert p.capital_available == 50000.0
    assert p.annual_income == 120000.0
    assert p.age == 32
    assert p.beneficiary_category == "women"
    assert p.location["state"] == "Tamil Nadu"
    assert p.location["district"] == "Erode"
    assert p.location["block"] == "Perundurai"
    assert p.location["village"] == "Surampatti"


def test_llm_handles_hindi_and_null_fields(monkeypatch):
    payload = (
        '{"business_type": "poultry", "scale": null, "project_cost": 300000, '
        '"capital_available": null, "annual_income": null, "age": null, '
        '"beneficiary_category": null, "state": "Tamil Nadu", "district": "Erode", '
        '"block": null, "village": null}'
    )
    _patch_llm(monkeypatch, payload)
    p = ex.parse_multilingual_free_text(
        "मैं ईरोड में 3 लाख में मुर्गी पालन शुरू करना चाहता हूँ।"
    )
    assert p.confidence["engine"] == "llm"
    assert p.business_type == "poultry"
    assert p.project_cost == 300000.0
    assert p.scale is None
    assert "budget" not in p.missing_fields
    # district supplied -> no "district" missing
    assert "district" not in p.missing_fields
    # state supplied
    assert p.location["state"] == "Tamil Nadu"


def test_llm_clamps_absurd_values(monkeypatch):
    # A misbehaving model returns an absurd cost; the extractor must clamp it.
    payload = (
        '{"business_type": "grocery", "scale": "micro", '
        '"project_cost": 99999999999, "capital_available": 100000000, '
        '"age": 999, "annual_income": null, "beneficiary_category": null, '
        '"state": null, "district": null, "block": null, "village": null}'
    )
    _patch_llm(monkeypatch, payload)
    p = ex.parse_multilingual_free_text("grocery shop")
    assert p.project_cost is None  # clamped out of range
    assert p.capital_available is None  # clamped out of range
    assert p.age is None


def test_llm_maps_human_labels_to_codes(monkeypatch):
    payload = (
        '{"business_type": "Grocery Store", "scale": "medium", '
        '"project_cost": 1000000, "capital_available": 200000, '
        '"annual_income": null, "age": null, '
        '"beneficiary_category": "SC", "state": "Tamil Nadu", '
        '"district": "Erode", "block": null, "village": null}'
    )
    _patch_llm(monkeypatch, payload)
    p = ex.parse_multilingual_free_text("grocery store in erode")
    assert p.business_type == "grocery"
    assert p.scale == "medium"
    assert p.beneficiary_category == "sc_st"


def test_malformed_llm_response_falls_back(monkeypatch):
    # Provider returns garbage -> fall back to regex parser, not break.
    _patch_llm(monkeypatch, payload="this is not json at all")
    p = ex.parse_multilingual_free_text("ஈரோட்டில் ஒரு கடை ஆரம்பிக்கணும்")
    assert p.confidence["engine"] == "regex"
    assert p.location["district"] == "Erode"


def test_llm_call_error_falls_back(monkeypatch):
    # Provider raises -> the extractor must not propagate the exception.
    class Boom:
        def complete(self, system, user, evidence):
            raise RuntimeError("provider down")

    monkeypatch.setattr(ex, "_is_llm_available", lambda: True)
    monkeypatch.setattr(ex, "get_provider", lambda: Boom())
    p = ex.parse_multilingual_free_text(
        "எனக்கு பவானியில் 5 லட்சம் ரூபாயில் ஒரு பால் பண்ணை ஆரம்பிக்கணும்."
    )
    assert p.confidence["engine"] == "regex"
    assert p.business_type == "dairy"


def test_empty_input_reports_missing():
    p = ex.parse_multilingual_free_text("   ")
    assert "All fields required" in p.missing_fields


def test_parse_provenance_on_api_dict():
    # to_dict must surface the new engine/llm_available provenance.
    from app.engines.nlp_parser import to_dict

    p = ex.parse_multilingual_free_text("start a dairy")
    d = to_dict(p)
    assert "engine" in d["confidence"]
    assert "llm_available" in d["confidence"]


def test_run_advisory_pipeline_with_llm_parse(monkeypatch, session):
    """The full advisory report pipeline works when parsing is LLM-driven."""
    from app.services.advisory import run_advisory

    payload = (
        '{"business_type": "dairy", "scale": "small", "project_cost": 200000, '
        '"capital_available": 50000, "annual_income": null, "age": 30, '
        '"beneficiary_category": null, "state": "Tamil Nadu", "district": "Erode", '
        '"block": "Bhavani", "village": null}'
    )
    _patch_llm(monkeypatch, payload)

    report = run_advisory(
        db=session,
        free_text="I want a dairy in Bhavani, Erode with 2 lakh.",
        structured_input={"language": "en"},
    )
    assert report.parsed_input.business_type == "dairy"
    assert report.parsed_input.confidence["engine"] == "llm"
    assert report.financial_structure is not None
    assert report.summary
    assert report.action_plan

