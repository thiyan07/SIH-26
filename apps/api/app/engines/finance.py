"""Deterministic financial structuring engine.

All values here are computed, never guessed. Scheme parameters come from the
configured rules (in production from the `government_schemes` table). The
values used are the demo defaults from the problem statement and are always
labelled as such.

Financing model (SIH 26091): a project's cost is driven by the beneficiary's
actual business requirements (business category + scale + location cost
templates), NOT by ``Available Capital x 10``. The required financing is simply
what the beneficiary cannot cover from their own capital::

    required_financing = max(0, project_cost - own_capital)

the resulting loan is then capped by the governing scheme's financing limits.
The 90%-of-cost figure in the problem statement is a *ceiling*, not a mandated
loan — a beneficiary who can self-fund should not be forced to borrow.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

# Deprecated inverse-margin constant retained for external callers that still
# reference it, but no longer used to derive a project cost from capital.
DEFAULT_MARGIN_PCT = 10.0  # legacy: beneficiary margin assumed = 10% of cost


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
    project_cost: float
    capital_available: float
    required_financing: float
    own_contribution: float
    loan_amount: float
    max_loan_allowed: Optional[float]
    scheme: Optional[SchemeRule] = None
    scheme_decision: Optional[str] = None  # micro_finance | term_loan | no_supported_scheme
    scheme_reason: Optional[str] = None
    beyond_maximum: bool = False
    shortfall: float = 0.0
    shortfall_reason: Optional[str] = None
    notes: list[str] = field(default_factory=list)


class FinancialEngineError(ValueError):
    pass


def derive_financial_plan(
    project_cost: float,
    capital_available: float = 0.0,
    schemes: tuple[SchemeRule, ...] = DEFAULT_SCHEMES,
) -> FinancialPlan:
    """Derive a financing plan from the *actual project cost*, not from capital.

    ``project_cost`` is the business's real cost (business category + scale +
    location cost template, or an explicitly stated figure). It is used
    verbatim — it is never re-invented from available capital.

    ``capital_available`` is the beneficiary's own contribution toward that
    cost (defaults to 0 when unknown). Financing is what the beneficiary cannot
    cover themselves: ``required_financing = max(0, project_cost - capital)``,
    and the resulting loan is capped by the governing scheme's maximum. The 90%
    figure from the problem statement is treated as a ceiling, never as a
    mandatory loan.
    """
    if project_cost is None or project_cost < 0:
        raise FinancialEngineError("project_cost must be a non-negative amount")
    if capital_available is None:
        capital_available = 0.0
    if capital_available < 0:
        raise FinancialEngineError("capital_available must be non-negative")

    required_financing = max(0.0, project_cost - capital_available)
    own_contribution = min(capital_available, project_cost)

    scheme, decision, reason = _route(project_cost, schemes)

    plan = FinancialPlan(
        project_cost=project_cost,
        capital_available=capital_available,
        required_financing=required_financing,
        own_contribution=own_contribution,
        loan_amount=0.0,
        max_loan_allowed=None,
        scheme=scheme,
        scheme_decision=decision,
        scheme_reason=reason,
    )

    if scheme is None:
        plan.beyond_maximum = True
        plan.notes.append(
            f"Project cost ₹{project_cost:,.0f} exceeds the largest supported scheme "
            f"maximum; no supported scheme recommended. Show as ESTIMATED / "
            f"non-scheme financing (SCHEME_UNAVAILABLE)."
        )
        return plan

    plan.max_loan_allowed = scheme.max_loan_amount
    loan_amount = min(required_financing, scheme.max_loan_amount) if scheme.max_loan_amount is not None else required_financing

    # Scheme financing cap: if the beneficiary needs more than the scheme can
    # lend, the remainder must come from own capital or other sources.
    if scheme.max_loan_amount is not None and required_financing > scheme.max_loan_amount:
        plan.notes.append(
            f"Financing need ₹{required_financing:,.0f} exceeds the {scheme.name} "
            f"maximum of ₹{scheme.max_loan_amount:,.0f}; loan capped and the "
            f"shortfall must be covered by own capital or other sources."
        )

    plan.loan_amount = loan_amount

    # Own-capital shortfall vs. the scheme's contribution expectation.
    _apply_shortfall(plan, scheme)

    return plan


def _apply_shortfall(plan: FinancialPlan, scheme: SchemeRule) -> None:
    """Detect and explain an own-capital shortfall against the scheme rules.

    The 90%-financing ceiling implies the beneficiary is expected to cover at
    least 10% of the project cost from their own pocket. If their stated own
    capital is below that floor *and* the loan is already at the cap, surface
    the shortfall explicitly so the caller can display it.
    """
    floor_pct = scheme.margin_pct if scheme.margin_pct is not None else DEFAULT_MARGIN_PCT
    required_contribution_floor = plan.project_cost * floor_pct / 100.0
    if plan.own_contribution < required_contribution_floor and plan.required_financing > 0:
        plan.shortfall = round(required_contribution_floor - plan.own_contribution, 2)
        plan.shortfall_reason = (
            f"{scheme.name} expects a beneficiary contribution of at least "
            f"₹{required_contribution_floor:,.0f} (≥{floor_pct:g}% of project cost). "
            f"You have ₹{plan.own_contribution:,.0f}; add ₹{plan.shortfall:,.0f} "
            f"to qualify for the full {scheme.name} financing."
        )
        plan.notes.append(plan.shortfall_reason)


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
