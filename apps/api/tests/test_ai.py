"""AI layer tests (section 40): no unsupported statistics, no hallucinated
scheme rules, report generated from supplied context."""
from __future__ import annotations

from app.ai.compose import build_risks, build_swot
from app.ai.llm import MockLLMProvider, build_evidence_prompt, get_provider


def _evidence():
    return {
        "location": {"district": "Erode", "village": "Sathyamangalam"},
        "population": {"population": 12400, "census_year": 2011, "available": True,
                       "note": "Census 2011 baseline - NOT current population."},
        "business_competition": {"mapped_competitors_5km": 2, "data_completeness": "medium",
                                 "note": "OSM mapped data may be incomplete."},
        "opportunity_score": {"overall_score": 80.3, "confidence_label": "medium"},
        "recommendation": {"label": "GO"},
        "financial_plan": {"scheme_name": "Term Loan", "loan_amount": 900000.0,
                           "interest_rate": 8.0, "tenure_years": 7},
        "data_sources": [{"name": "Census India", "reference_year": 2011},
                         {"name": "OpenStreetMap", "confidence": "medium"}],
    }


def test_provider_default_is_mock():
    assert get_provider().name == "mock"


def test_mock_echos_evidence_not_invents():
    prov = MockLLMProvider()
    res = prov.complete("sys", "user", _evidence())
    content = res["content"]
    # The mock restates the provided opportunity score (80.3 from evidence)
    assert "80.3" in content  # echoes deterministic evidence
    assert "competitor" not in content.lower()  # never invents competitor counts


def test_mock_does_not_hallucinate_scheme_rule():
    prov = MockLLMProvider()
    res = prov.complete("sys", "user", _evidence())
    # The mock must restate only the evidence itself; it must never invent
    # parameters (e.g. a micro-finance 6.5% that is not in the evidence).
    assert "6.5" not in res["content"]
    # An AI answer grounded in evidence should reference the recommendation.
    assert "GO" in res["content"] or "recommendation" in res["content"].lower()


def test_build_evidence_prompt_includes_json_only():
    prompt = build_evidence_prompt(_evidence(), "report", "en")
    assert "Erode" in prompt
    assert "EVIDENCE" in prompt


def test_swot_built_from_evidence():
    swot = build_swot(_evidence(), "en")
    assert isinstance(swot["strengths"], list)
    assert len(swot["threats"]) == 0  # few competitors, low risk


def test_risks_flag_data_completeness():
    risks = build_risks(_evidence())
    assert any("Data completeness" in r["factor"] for r in risks)


def test_swot_translated_labels():
    swot = build_swot(_evidence(), "ta")
    assert swot["labels"]["strengths"] == "பலம்"
