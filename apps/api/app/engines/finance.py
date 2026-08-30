"""Deterministic financial structuring engine.

All values here are computed, never guessed. Scheme parameters come from the
configured rules (in production from the `government_schemes` table). The
values used are the demo defaults from the problem statement and are always
labelled as such.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

DEFAULT_MARGIN_PCT = 10.0  # available margin = 10% of project cost


@dataclass
class SchemeRule:
    code: str
    name: str
    min_project_cost: Optional[float]
    max_project_cost: Optional[float]
    max_loan_amount: Optional[float]
    interest_rate: float
    tenure_years: float
    moratorium_months: int
    margin_pct: float = DEFAULT_MARGIN_PCT
    moratorium_mode: str = "interest_only_during_moratorium"
    source_document: Optional[str] = None
    source_date: Optional[str] = None
    note: str = ""


# Demo defaults from the supplied problem statement (not verified policy).
MICRO_FINANCE = SchemeRule(
    code="micro_finance",
    name="Micro Finance",
    min_project_cost=0.0,
    max_project_cost=140_000.0,      # ₹1.40 lakh
    max_loan_amount=125_000.0,       # ₹1.25 lakh
    interest_rate=6.5,
    tenure_years=3,
    moratorium_months=3,
    moratorium_mode="interest_only_during_moratorium",
    source_document="Problem Statement 26091 (assumed demo config)",
    source_date="contest brief",
    note="Assumed demo parameters; verify with channelizing agency.",
)

TERM_LOAN = SchemeRule(
    code="term_loan",
    name="Term Loan",
    min_project_cost=140_000.0,       # > ₹1.40 lakh
    max_project_cost=5_000_000.0,     # ₹50 lakh
    max_loan_amount=4_500_000.0,      # ₹45 lakh
    interest_rate=8.0,
    tenure_years=7,
    moratorium_months=6,
    moratorium_mode="interest_only_during_moratorium",
    source_document="Problem Statement 26091 (assumed demo config)",
    source_date="contest brief",
    note="Assumed demo parameters; verify with channelizing agency.",
)

DEFAULT_SCHEMES = (MICRO_FINANCE, TERM_LOAN)


@dataclass
class FinancialPlan:
    capital_available: float
    project_cost: float
    loan_amount: float
    margin_amount: float
    margin_pct: float
    scheme: Optional[SchemeRule] = None
    scheme_decision: Optional[str] = None  # micro_finance | term_loan | no_supported_scheme
    scheme_reason: Optional[str] = None
    beyond_maximum: bool = False
    notes: list[str] = field(default_factory=list)


class FinancialEngineError(ValueError):
    pass


def derive_financial_plan(
    capital_available: float,
    schemes: tuple[SchemeRule, ...] = DEFAULT_SCHEMES,
) -> FinancialPlan:
    """Compute project_cost, loan_amount, and route to a scheme."""
    if capital_available <= 0:
        raise FinancialEngineError("capital_available must be positive")

    # Available margin is configurable; we use the first scheme's margin as the
    # global default (all schemes share the same 10% assumption by default).
    margin_pct = schemes[0].margin_pct if schemes else DEFAULT_MARGIN_PCT
    margin_frac = margin_pct / 100.0

    project_cost = capital_available / margin_frac
    loan_amount = project_cost * (1 - margin_frac)

    plan = FinancialPlan(
        capital_available=capital_available,
        project_cost=project_cost,
        loan_amount=loan_amount,
        margin_amount=capital_available,
        margin_pct=margin_pct,
    )

    scheme, decision, reason = _route(project_cost, schemes)
    plan.scheme = scheme
    plan.scheme_decision = decision
    plan.scheme_reason = reason

    if scheme is not None:
        # enforce loan maximum cap
        if scheme.max_loan_amount is not None and loan_amount > scheme.max_loan_amount:
            plan.notes.append(
                f"Loan amount capped from ₹{loan_amount:,.0f} to ₹{scheme.max_loan_amount:,.0f} "
                f"(scheme maximum)."
            )
            loan_amount = scheme.max_loan_amount
    else:
        plan.beyond_maximum = True
        plan.notes.append(
            f"Project cost ₹{project_cost:,.0f} exceeds the largest supported scheme "
            f"maximum; no supported scheme recommended."
        )

    plan.loan_amount = loan_amount
    return plan


def _route(
    project_cost: float,
    schemes: tuple[SchemeRule, ...],
) -> tuple[Optional[SchemeRule], str, str]:
    for s in schemes:
        lo = s.min_project_cost if s.min_project_cost is not None else float("-inf")
        hi = s.max_project_cost if s.max_project_cost is not None else float("inf")
        if lo <= project_cost <= hi:
            return s, f"scheme:{s.code}", (
                f"Project cost ₹{project_cost:,.0f} falls within {s.name} range "
                f"(₹{s.min_project_cost or 0:,.0f}–₹{s.max_project_cost:,.0f})."
            )
    # if none matched
    largest = max(schemes, key=lambda s: s.max_project_cost if s.max_project_cost is not None else 0)
    return None, "no_supported_scheme", (
        f"Project cost ₹{project_cost:,.0f} exceeds the largest supported scheme maximum "
        f"(₹{largest.max_project_cost:,.0f})."
    )


def emi(
    principal: float,
    annual_rate: float,
    tenure_years: float,
    months_paid: Optional[int] = None,
    months_remaining: Optional[int] = None,
) -> float:
    """Standard reducing-balance monthly EMI.

    principal and rate describe the *fully amortised* portion (i.e. after
    moratorium handling has been applied by the caller). Returns the constant
    monthly payment.
    """
    monthly_rate = annual_rate / 100.0 / 12.0
    if months_remaining is None:
        months = tenure_years * 12
    else:
        months = months_remaining
    if monthly_rate == 0:
        return principal / months if months else 0.0
    factor = (1 + monthly_rate) ** months
    return principal * monthly_rate * factor / (factor - 1)


def emi_reducing(principal, annual_rate, months):
    """Alias with explicit month count; used by tests."""
    return emi(principal, annual_rate, months / 12.0, months_remaining=months)
