"""Financial engine tests (section 40)."""
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


def test_lakh_to_lakh_project():
    """₹1 lakh capital -> ₹10 lakh project -> ₹9 lakh loan."""
    plan = derive_financial_plan(100_000)
    assert plan.project_cost == pytest.approx(1_000_000, rel=1e-6)
    assert plan.loan_amount == pytest.approx(900_000, rel=1e-6)
    assert plan.scheme_decision == "scheme:term_loan"


def test_micro_finance_boundary():
    # project cost <= 1.40 lakh -> micro finance
    capital = 10_000  # -> 1.0 lakh project
    plan = derive_financial_plan(capital)
    assert plan.scheme.code == "micro_finance"
    # loan = 0.9*1.0l = 90k, under 1.25l cap
    assert plan.loan_amount == pytest.approx(90_000, rel=1e-6)
    # At the exact boundary: capital=14,000 -> project 1.40 lakh
    plan2 = derive_financial_plan(14_000)
    assert plan2.scheme.code == "micro_finance"
    assert plan2.project_cost == pytest.approx(140_000, rel=1e-6)


def test_term_loan_boundary():
    # capital=14,001 -> project 1.4001 lakh > 1.40 -> term loan
    plan = derive_financial_plan(14_001)
    assert plan.scheme.code == "term_loan"


def test_micro_finance_max_loan_cap():
    # capital=13,889 -> project 1.3889l -> loan 1.25l roughly, cap at 1.25l
    plan = derive_financial_plan(13_889)
    assert plan.scheme.code == "micro_finance"
    assert plan.loan_amount <= MICRO_FINANCE.max_loan_amount + 0.01


def test_term_loan_max_loan_cap():
    # Large capital within term range but force loan above 45l cap
    plan = derive_financial_plan(500_000)  # project 50l -> loan 45l exactly at cap
    assert plan.scheme.code == "term_loan"
    assert plan.loan_amount <= TERM_LOAN.max_loan_amount + 0.01


def test_above_maximum_project_cost():
    # capital=600_000 -> project 60l > 50l -> no supported scheme
    plan = derive_financial_plan(600_000)
    assert plan.scheme is None
    assert plan.scheme_decision == "no_supported_scheme"
    assert plan.beyond_maximum is True


def test_zero_capital_invalid():
    with pytest.raises(FinancialEngineError):
        derive_financial_plan(0)


def test_negative_capital_invalid():
    with pytest.raises(FinancialEngineError):
        derive_financial_plan(-100)


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


# ---------- Exact boundary/edge cases (plan §31) ----------

def test_capital_one():
    """₹1 capital -> ₹10 project -> ₹9 loan (micro finance)."""
    plan = derive_financial_plan(1)
    assert plan.project_cost == pytest.approx(10, rel=1e-6)
    assert plan.loan_amount == pytest.approx(9, rel=1e-6)
    assert plan.scheme.code == "micro_finance"


def test_capital_50000():
    """₹50,000 capital -> ₹5 lakh project -> ₹4.5 lakh loan (micro finance, under 1.25l? no)."""
    # 50,000/0.10 = 5,00,000 project; this is > 1.40 lakh -> term loan
    plan = derive_financial_plan(50_000)
    assert plan.project_cost == pytest.approx(500_000, rel=1e-6)
    assert plan.scheme.code == "term_loan"


def test_capital_1_lakh_and_1_25_lakh():
    # ₹1,00,000 capital
    p1 = derive_financial_plan(100_000)
    assert p1.project_cost == pytest.approx(1_000_000, rel=1e-6)
    assert p1.scheme.code == "term_loan"
    # ₹1,25,000 capital
    p2 = derive_financial_plan(125_000)
    assert p2.project_cost == pytest.approx(1_250_000, rel=1e-6)
    assert p2.scheme.code == "term_loan"


def test_capital_1_40_lakh_exact():
    """₹1.40 lakh(capital) -> ₹14 lakh project (term loan)."""
    plan = derive_financial_plan(140_000)
    assert plan.project_cost == pytest.approx(1_400_000, rel=1e-6)
    assert plan.scheme.code == "term_loan"


def test_project_cost_boundary_140k_plus_1():
    """Project cost boundary around ₹1.40 lakh (capital 14,000/14,001).
    The loan-avoiding micro/term boundary is on project cost <= 1.40 lakh."""
    plan = derive_financial_plan(14_000)   # project = 1.40 lakh exactly -> micro
    assert plan.project_cost == pytest.approx(140_000, rel=1e-6)
    assert plan.scheme.code == "micro_finance"
    plan2 = derive_financial_plan(14_001)  # project = 1.4001 lakh -> term
    assert plan2.scheme.code == "term_loan"


def test_capital_5_lakh():
    """₹5,00,000 capital -> ₹50 lakh project (term loan at max)."""
    plan = derive_financial_plan(500_000)
    assert plan.project_cost == pytest.approx(5_000_000, rel=1e-6)
    assert plan.scheme.code == "term_loan"
    # loan 45 lakh = max loan cap
    assert plan.loan_amount == pytest.approx(TERM_LOAN.max_loan_amount, rel=1e-6)


def test_project_cost_50_lakh_plus_1_no_scheme():
    """Project cost just over ₹50 lakh -> no supported scheme."""
    # capital 500_001 -> project 50.0001 lakh > 50 lakh
    plan = derive_financial_plan(500_001)
    assert plan.scheme is None
    assert plan.scheme_decision == "no_supported_scheme"
    assert plan.beyond_maximum is True


def test_negative_and_zero_invalid_reinforced():
    with pytest.raises(FinancialEngineError):
        derive_financial_plan(0)
    with pytest.raises(FinancialEngineError):
        derive_financial_plan(-1)
    with pytest.raises(FinancialEngineError):
        derive_financial_plan(-50_000)
