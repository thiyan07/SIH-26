"""Financial engine tests (cost-driven financing redesign).

The project cost is driven by the beneficiary's actual business requirement
(cost template / explicit figure), NOT by ``Available Capital x 10``. The loan
is ``min(required_financing, scheme cap)`` where
``required_financing = max(0, project_cost - own_capital)``. The 90% figure is
a ceiling, never a forced loan.
"""
from __future__ import annotations

import pytest

from app.engines.finance import (
    MICRO_FINANCE,
    TERM_LOAN,
    FinancialEngineError,
    derive_financial_plan,
    emi,
)
from app.engines.repayment import build_schedule, repayment_health

# ---------- Core cost-driven semantics ----------

def test_project_cost_driven_by_cost_not_capital():
    """Project cost is used verbatim; the loan is only what capital can't cover."""
    # A ₹1,00,000 project with ₹1,00,000 own capital -> NO loan needed.
    plan = derive_financial_plan(100_000, capital_available=100_000)
    assert plan.project_cost == pytest.approx(100_000, rel=1e-6)
    assert plan.own_contribution == pytest.approx(100_000, rel=1e-6)
    assert plan.required_financing == pytest.approx(0, rel=1e-6)
    assert plan.loan_amount == pytest.approx(0, rel=1e-6)
    assert plan.scheme is not None  # still routed to a scheme; loan is just 0


def test_no_forced_90_percent_loan():
    """₹1,00,000 project with ₹90,000 capital -> loan ₹10,000, NOT ₹90,000."""
    plan = derive_financial_plan(100_000, capital_available=90_000)
    assert plan.project_cost == pytest.approx(100_000, rel=1e-6)
    assert plan.required_financing == pytest.approx(10_000, rel=1e-6)
    assert plan.loan_amount == pytest.approx(10_000, rel=1e-6)


def test_loan_never_negative_when_capital_exceeds_cost():
    plan = derive_financial_plan(80_000, capital_available=120_000)
    assert plan.required_financing == 0
    assert plan.loan_amount == 0
    assert plan.own_contribution == pytest.approx(80_000, rel=1e-6)


# ---------- Scheme routing boundaries ----------

def test_micro_finance_boundary():
    # project cost = ₹1.40 lakh exactly -> micro finance
    plan = derive_financial_plan(140_000, capital_available=0)
    assert plan.scheme.code == "micro_finance"
    assert plan.scheme_decision == "scheme:micro_finance"
    # no capital -> required financing = full cost, capped at ₹1.25 lakh
    assert plan.loan_amount == pytest.approx(125_000, rel=1e-6)


def test_term_loan_boundary():
    # project cost just above ₹1.40 lakh -> term loan
    plan = derive_financial_plan(140_001, capital_available=0)
    assert plan.scheme.code == "term_loan"
    assert plan.scheme_decision == "scheme:term_loan"


def test_micro_finance_max_loan_cap():
    # micro project cost at cap: full financing need -> 1.25 lakh cap
    plan = derive_financial_plan(125_000, capital_available=0)
    assert plan.scheme.code == "micro_finance"
    assert plan.loan_amount <= MICRO_FINANCE.max_loan_amount + 0.01
    assert plan.max_loan_allowed == pytest.approx(125_000, rel=1e-6)


def test_term_loan_max_loan_cap():
    # term project with financing need above 45 lakh -> capped at 45 lakh
    plan = derive_financial_plan(5_000_000, capital_available=0)
    assert plan.scheme.code == "term_loan"
    assert plan.loan_amount <= TERM_LOAN.max_loan_amount + 0.01
    assert plan.loan_amount == pytest.approx(4_500_000, rel=1e-6)


def test_above_maximum_project_cost():
    # project cost > ₹50 lakh -> no supported scheme (SCHEME_UNAVAILABLE)
    plan = derive_financial_plan(5_000_001, capital_available=0)
    assert plan.scheme is None
    assert plan.scheme_decision == "no_supported_scheme"
    assert plan.beyond_maximum is True
    assert plan.loan_amount == 0


def test_cost_zero_allowed_with_no_capital():
    """A zero-cost plan with no capital yields no financing and no note crash."""
    plan = derive_financial_plan(0, capital_available=0)
    assert plan.project_cost == 0
    assert plan.required_financing == 0
    assert plan.loan_amount == 0


def test_negative_project_cost_invalid():
    with pytest.raises(FinancialEngineError):
        derive_financial_plan(-1)


def test_negative_capital_invalid():
    with pytest.raises(FinancialEngineError):
        derive_financial_plan(100_000, capital_available=-50_000)


# ---------- Contribution shortfall ----------

def test_shortfall_when_own_capital_below_floor():
    """Project ₹1,00,000, own capital ₹5,000 -> financing ₹95,000, but the
    scheme expects ≥10% (₹10,000) own contribution; shortfall surfaced."""
    plan = derive_financial_plan(100_000, capital_available=5_000)
    assert plan.scheme.code == "micro_finance"
    assert plan.required_financing == pytest.approx(95_000, rel=1e-6)
    if plan.scheme.max_loan_amount is not None:
        assert plan.loan_amount == pytest.approx(min(95_000, plan.scheme.max_loan_amount), rel=1e-6)
    assert plan.shortfall > 0
    assert plan.shortfall_reason is not None


def test_no_shortfall_when_own_capital_meets_floor():
    plan = derive_financial_plan(100_000, capital_available=10_000)
    assert plan.shortfall == 0
    assert plan.shortfall_reason is None


# ---------- EMI / repayment (unchanged) ----------

def test_emi_basic():
    # 1,00,000 at 10% over 12 months -> 8791.59 (approx)
    e = emi(100_000, 10.0, 1.0)
    assert e == pytest.approx(8791.59, rel=1e-2)


def test_repayment_schedule_total():
    schedule = build_schedule(90_000, 6.5, 3, moratorium_months=3,
                              moratorium_mode="interest_only_during_moratorium")
    assert schedule.monthly_emi_effective > 0
    assert schedule.total_repayment == pytest.approx(
        sum(r.total_payment for r in schedule.months), rel=1e-6)


def test_repayment_health_labels():
    assert repayment_health(6000, 4000)["label"] == "Healthy"
    assert repayment_health(4000, 4000)["label"] == "Moderate"
    assert repayment_health(2000, 4000)["label"] == "High Risk"


def test_scheme_defaults_are_demo():
    assert MICRO_FINANCE.source_document == "Problem Statement 26091 (assumed demo config)"
