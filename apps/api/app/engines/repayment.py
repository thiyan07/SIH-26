"""Repayment engine: EMI, moratorium modes, schedules, and coverage health.

Moratorium treatment varies by actual loan rules, so we support multiple modes:

- interest_only_during_moratorium : during moratorium only interest accrues and
  is paid; principal is amortised over the remaining tenure starting after the
  moratorium.
- deferred_interest : interest during moratorium is capitalised (added to
  principal); no payments during moratorium.
- principal_deferred : principal repayments are deferred but interest is paid
  during moratorium.
- custom_schedule : caller provides an explicit list of monthly amounts.

We never claim a specific treatment is official unless a verified scheme
document confirms it; the default is configurable per scheme.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

MODES = ("interest_only_during_moratorium", "deferred_interest", "principal_deferred", "custom_schedule")


@dataclass
class MonthlyRow:
    month: int
    interest_payment: float
    principal_payment: float
    total_payment: float
    principal_outstanding: float


@dataclass
class RepaymentSchedule:
    monthly_emi_standard: float
    monthly_emi_effective: float
    total_repayment: float
    total_interest: float
    moratorium_months: int
    moratorium_mode: str
    months: list[MonthlyRow] = field(default_factory=list)
    quarterly: list[dict] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def _monthly_rate(annual_rate: float) -> float:
    return annual_rate / 100.0 / 12.0


def interest_only_during_moratorium(principal, annual_rate, tenure_years, moratorium_months) -> tuple:
    """Interest accrues and is paid each month during moratorium; principal
    then amortises over the remaining months at the post-moratorium rate."""
    mr = _monthly_rate(annual_rate)
    remaining_months = max(int(round(tenure_years * 12)) - moratorium_months, 1)
    monthly_interest = principal * mr

    # principal amortised over remaining months
    if mr == 0:
        p_payment = principal / remaining_months
    else:
        factor = (1 + mr) ** remaining_months
        p_payment = principal * mr * factor / (factor - 1)

    total_interest = monthly_interest * moratorium_months + (p_payment * remaining_months - principal)
    total_repayment = monthly_interest * moratorium_months + p_payment * remaining_months
    return p_payment, total_repayment, total_interest


def _build_rows(principal, annual_rate, tenure_years, moratorium_months, mode, custom=None) -> RepaymentSchedule:
    mr = _monthly_rate(annual_rate)
    total_months = int(round(tenure_years * 12))
    rows: list[MonthlyRow] = []
    outstanding = principal
    notes: list[str] = []

    if mode in ("interest_only_during_moratorium", "principal_deferred"):
        # During moratorium: pay interest (or defer depending on mode)
        if mode == "interest_only_during_moratorium":
            mo_payment = outstanding * mr
            for m in range(1, moratorium_months + 1):
                rows.append(MonthlyRow(m, mo_payment, 0.0, mo_payment, outstanding))
        else:  # principal_deferred: no payment, interest recorded/accrued
            for m in range(1, moratorium_months + 1):
                rows.append(MonthlyRow(m, outstanding * mr, 0.0, outstanding * mr, outstanding))
        remaining_months = total_months - moratorium_months
        # amortise the principal (interest continues normally)
        if mr == 0:
            p_pay = outstanding / remaining_months
        else:
            factor = (1 + mr) ** remaining_months
            p_pay = outstanding * mr * factor / (factor - 1)
        for i in range(1, remaining_months + 1):
            m = moratorium_months + i
            interest = outstanding * mr
            principal_pay = min(p_pay, outstanding)
            outstanding = max(outstanding - principal_pay, 0.0)
            rows.append(MonthlyRow(m, interest, principal_pay, interest + principal_pay, outstanding))
        notes.append(f"moratorium mode '{mode}': no payments skip/interest during moratorium, principal amortised after.")

    elif mode == "deferred_interest":
        # No payments during moratorium; interest capitalises onto principal,
        # then entire balance amortised over the remaining months.
        rows = _deferred_rows(principal, annual_rate, tenure_years, moratorium_months)
        notes.append("moratorium mode 'deferred_interest': interest capitalised, no payments during moratorium.")

    elif mode == "custom_schedule":
        if not custom:
            raise ValueError("custom_schedule requires a list of monthly amounts")
        for m, amt in enumerate(custom, start=1):
            interest = outstanding * mr
            principal_pay = min(amt - interest, outstanding) if amt >= interest else 0.0
            # if amount < interest we don't reduce principal
            if amt < interest:
                principal_pay = 0.0
            outstanding = max(outstanding - principal_pay, 0.0)
            rows.append(MonthlyRow(m, interest, principal_pay, amt, outstanding))
    else:
        raise ValueError(f"unknown moratorium mode: {mode}")

    # Derive standard EMI for reporting (fully amortised, no moratorium)
    std_emi = _std_emi(principal, annual_rate, total_months)
    total_repayment = sum(r.total_payment for r in rows)
    total_interest = sum(r.interest_payment for r in rows)

    return RepaymentSchedule(
        monthly_emi_standard=std_emi,
        monthly_emi_effective=(rows[0].total_payment if rows else std_emi),
        total_repayment=total_repayment,
        total_interest=total_interest,
        moratorium_months=moratorium_months,
        moratorium_mode=mode,
        months=rows,
        notes=notes,
    )


def _deferred_rows(principal, annual_rate, tenure_years, moratorium_months) -> list[MonthlyRow]:
    mr = _monthly_rate(annual_rate)
    total_months = int(round(tenure_years * 12))
    if mr == 0:
        deferred = 0.0
    else:
        deferred = principal * ((1 + mr) ** moratorium_months - 1)
    cap = principal + deferred
    rows: list[MonthlyRow] = []
    for m in range(1, moratorium_months + 1):
        rows.append(MonthlyRow(m, 0.0, 0.0, 0.0, cap))
    remaining = total_months - moratorium_months
    if mr == 0:
        p_pay = cap / remaining
    else:
        factor = (1 + mr) ** remaining
        p_pay = cap * mr * factor / (factor - 1)
    for i in range(1, remaining + 1):
        m = moratorium_months + i
        interest = cap * mr
        principal_pay = min(p_pay, cap)
        cap = max(cap - principal_pay, 0.0)
        rows.append(MonthlyRow(m, interest, principal_pay, interest + principal_pay, cap))
    return rows


def _std_emi(principal, annual_rate, months) -> float:
    mr = _monthly_rate(annual_rate)
    if mr == 0:
        return principal / months if months else 0.0
    factor = (1 + mr) ** months
    return principal * mr * factor / (factor - 1)


def build_schedule(
    principal: float,
    annual_rate: float,
    tenure_years: float,
    moratorium_months: int = 0,
    moratorium_mode: str = "interest_only_during_moratorium",
    custom: Optional[list[float]] = None,
) -> RepaymentSchedule:
    if principal <= 0:
        raise ValueError("principal must be positive")
    if annual_rate < 0:
        raise ValueError("annual_rate must be >= 0")
    if moratorium_mode not in MODES:
        raise ValueError(f"moratorium_mode must be one of {MODES}")
    schedule = _build_rows(principal, annual_rate, tenure_years, moratorium_months, moratorium_mode, custom)
    # quarterly summary
    q = {}
    for r in schedule.months:
        qnum = (r.month - 1) // 3 + 1
        q.setdefault(qnum, {"quarter": qnum, "payment": 0.0, "interest": 0.0, "principal": 0.0})
        q[qnum]["payment"] += r.total_payment
        q[qnum]["interest"] += r.interest_payment
        q[qnum]["principal"] += r.principal_payment
    schedule.quarterly = list(q.values())
    return schedule


def repayment_health(monthly_profit: float, monthly_debt_service: float) -> dict:
    """Coverage = estimated_monthly_operating_profit / monthly debt service."""
    if monthly_debt_service <= 0:
        ratio = float("inf")
        label = "Healthy"
    else:
        ratio = monthly_profit / monthly_debt_service
        if ratio >= 1.5:
            label = "Healthy"
        elif ratio >= 1.0:
            label = "Moderate"
        else:
            label = "High Risk"
    return {
        "coverage_ratio": round(ratio, 2),
        "label": label,
        "monthly_profit": round(monthly_profit, 2),
        "monthly_debt_service": round(monthly_debt_service, 2),
        "disclaimer": "Repayment health is an estimate based on modelled operating profit.",
    }
