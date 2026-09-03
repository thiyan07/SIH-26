"""Financial structuring honesty tests (audit §5: no unlabeled assumptions).

These verify that default financial parameters are never presented as if they
came from the underlying scheme, and that scheme routing is honest.
"""
from __future__ import annotations

import pytest

from app.engines.financial_structuring import (
    build_cost_breakdown,
    structure_financials,
    structure_loan,
    to_dict,
)
from app.engines.scheme_eligibility import BeneficiaryProfile, EligibilityResult


def _demo_eligible(interest=None, tenure=None, margin=None, moratorium=None,
                   max_loan=4_500_000, code="test_scheme", name="Test Scheme"):
    sd = {
        "code": code, "name": name,
        "min_project_cost": 0, "max_project_cost": 5_000_000,
        "max_loan_amount": max_loan,
        "interest_rate": interest, "tenure_years": tenure,
        "moratorium_months": moratorium, "margin_pct": margin, "subsidy_pct": None,
    }
    return EligibilityResult(
        scheme_code=code, scheme_name=name, status="ELIGIBLE",
        match_score=90, scheme_details=sd, mismatch_reasons=[],
    )


def test_grant_scheme_defaults_marked_assumed():
    # A grant-style scheme with no declared terms must NOT present 10%/5yr as its own.
    eligible = [_demo_eligible(interest=None, tenure=None, margin=None)]
    cost = build_cost_breakdown("dairy", "micro")
    loan = structure_loan(cost, 0.0, eligible)
    assert loan.scheme_code == "test_scheme"
    assert loan.is_assumed is True
    assert "interest_rate" in loan.assumed_fields
    assert "tenure_years" in loan.assumed_fields
    assert "margin_pct" in loan.assumed_fields
    assert any("ASSUMED" in n for n in loan.notes)


def test_real_scheme_terms_not_marked_assumed():
    eligible = [_demo_eligible(interest=6.5, tenure=3, margin=10, moratorium=0)]
    cost = build_cost_breakdown("dairy", "micro")
    loan = structure_loan(cost, 0.0, eligible)
    assert loan.is_assumed is False
    assert loan.assumed_fields == []
    assert loan.interest_rate == 6.5
    assert loan.tenure_years == 3


def test_fallback_term_loan_is_assumed():
    cost = build_cost_breakdown("dairy", "micro")
    loan = structure_loan(cost, 0.0, None)
    assert loan.is_assumed is True
    assert loan.scheme_code == "term_loan"
    assert "interest_rate" in loan.assumed_fields
    # The framework fallback must be clearly labelled as a demo/assumed source,
    # never presented as an official verified scheme.
    assert "assumed demo" in (loan.scheme_source or "").lower()
    assert any("ASSUMED" in n for n in loan.notes)


def test_scheme_eligibility_aligns_with_recommended():
    # Even if a NOT-eligible scheme scores highest, the eligibility shown must
    # match the recommended (chosen, ELIGIBLE) scheme.
    high_not = _demo_eligible(interest=5.0, tenure=2, margin=5, code="high_not", name="High Not")
    high_not.status = "NOT_ELIGIBLE"
    low_ok = _demo_eligible(interest=6.0, tenure=3, margin=10, code="low_ok", name="Low Ok")
    # sort descending puts high_not first
    eligible = [high_not, low_ok]
    profile = BeneficiaryProfile(
        state="Tamil Nadu", district="Erode", block="Bhavani",
        business_type="dairy", age=30, beneficiary_category="general",
        capital_available=0.0,
    )
    result = structure_financials(profile, "dairy", "micro", eligible_schemes=eligible)
    d = to_dict(result)
    assert d["recommended_scheme"] == "Low Ok"
    assert d["scheme_eligibility"]["code"] == "low_ok"


def test_assumption_flags_serialized():
    eligible = [_demo_eligible(interest=None)]
    profile = BeneficiaryProfile(
        state="Tamil Nadu", district="Erode", block="Bhavani",
        business_type="dairy", age=30, beneficiary_category="general",
        capital_available=0.0,
    )
    d = to_dict(structure_financials(profile, "dairy", "micro", eligible_schemes=eligible))
    ls = d["loan_structure"]
    assert "is_assumed" in ls
    assert "assumed_fields" in ls
    assert "scheme_source" in ls
    assert ls["is_assumed"] is True


# ---------- Cost-driven financing (redesign) ----------

def test_loan_equals_cost_minus_own_capital():
    """Loan is only what own capital cannot cover, capped by the scheme."""
    eligible = [_demo_eligible(interest=6.5, tenure=3, margin=10, max_loan=125_000)]
    cost = build_cost_breakdown("dairy", "micro")  # ~₹1,68,300 for dairy micro
    loan = structure_loan(cost, capital_available=100_000, eligible_schemes=eligible)
    expected_financing = round(max(0.0, cost.total_project_cost - 100_000), 2)
    assert loan.required_financing == pytest.approx(expected_financing, rel=1e-6)
    assert loan.own_contribution == pytest.approx(100_000, rel=1e-6)
    assert loan.loan_amount == pytest.approx(min(expected_financing, loan.max_loan_allowed), rel=1e-6)


def test_no_forced_loan_when_self_funded():
    """If own capital >= project cost, the loan is ₹0 (not forced 90%)."""
    eligible = [_demo_eligible(interest=6.5, tenure=3, margin=10, max_loan=125_000)]
    cost = build_cost_breakdown("dairy", "micro")
    loan = structure_loan(cost, capital_available=cost.total_project_cost + 50_000, eligible_schemes=eligible)
    assert loan.required_financing == 0
    assert loan.loan_amount == 0
    assert loan.beneficiary_contribution == pytest.approx(cost.total_project_cost, rel=1e-6)


def test_shortfall_surfaced_when_capital_below_contribution_floor():
    """When own capital is below the scheme's minimum contribution and the
    loan is capped, the shortfall is surfaced explicitly."""
    eligible = [_demo_eligible(interest=6.5, tenure=3, margin=10, max_loan=125_000)]
    cost = build_cost_breakdown("dairy", "micro")
    tiny_capital = 5_000
    loan = structure_loan(cost, capital_available=tiny_capital, eligible_schemes=eligible)
    floor = cost.total_project_cost * 10 / 100.0
    if loan.required_financing > 0 and loan.own_contribution < floor:
        assert loan.shortfall == pytest.approx(round(floor - tiny_capital, 2), rel=1e-6)
        assert any("Shortfall" in n for n in loan.notes)
    else:
        assert loan.shortfall == 0


def test_new_financing_fields_serialized():
    eligible = [_demo_eligible(interest=6.5, tenure=3, margin=10)]
    d = to_dict(structure_financials(
        BeneficiaryProfile(
            state="Tamil Nadu", district="Erode", block="Bhavani",
            business_type="dairy", age=30, beneficiary_category="general",
            capital_available=100_000,
        ),
        "dairy", "micro", eligible_schemes=eligible,
    ))
    ls = d["loan_structure"]
    assert "own_contribution" in ls
    assert "required_financing" in ls
    assert "shortfall" in ls
