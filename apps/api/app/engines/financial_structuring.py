"""Detailed financial structuring engine.

Takes a beneficiary profile + business category and produces a full
CAPEX/WC/equipment/inventory/licensing breakdown, scheme routing,
loan structure, subsidy calculation, and repayment schedule.

Pure deterministic logic — no LLM calls.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from app.engines.cost_templates import get_cost_template
from app.engines.finance import SchemeRule, derive_financial_plan
from app.engines.repayment import build_schedule, repayment_health
from app.engines.scheme_eligibility import BeneficiaryProfile, EligibilityResult


@dataclass
class CostBreakdown:
    category_code: str
    scale: str  # micro|small|medium
    capital_expenditure: dict[str, float]  # equipment, furniture, fixtures
    working_capital: dict[str, float]  # inventory, operating buffer
    infrastructure: dict[str, float]  # shop renovation, signage
    licensing_compliance: dict[str, float]  # registrations, permits
    contingency_pct: float
    contingency_amount: float
    total_project_cost: float
    notes: list[str] = field(default_factory=list)


@dataclass
class LoanStructure:
    scheme_code: Optional[str]
    scheme_name: Optional[str]
    total_project_cost: float
    beneficiary_contribution: float
    beneficiary_contribution_pct: float
    loan_amount: float
    max_loan_allowed: Optional[float]
    subsidy_amount: float
    subsidy_pct: Optional[float]
    interest_rate: float
    tenure_years: float
    moratorium_months: int
    moratorium_mode: str
    monthly_emi_during_moratorium: float
    monthly_emi_after_moratorium: float
    total_repayment: float
    total_interest: float
    repayment_health: Optional[dict] = None
    quarterly: list[dict] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


@dataclass
class FinancialStructure:
    beneficiary: dict
    cost_breakdown: CostBreakdown
    loan_structure: LoanStructure
    scheme_eligibility: Optional[dict] = None
    recommended_scheme: Optional[str] = None
    alternatives: list[dict] = field(default_factory=list)
    disclaimer: str = (
        "This is an estimated financial structure based on category defaults and "
        "scheme parameters. Actual amounts depend on lender appraisal, scheme "
        "sanction, and market conditions. Verify with the implementing agency."
    )


def build_cost_breakdown(
    category_code: str,
    scale: str = "micro",
    custom_items: Optional[dict[str, float]] = None,
    location_factor: float = 1.0,
) -> CostBreakdown:
    """Build a detailed cost breakdown using category cost templates.

    custom_items: override specific cost items (e.g. {"equipment": 150000})
    location_factor: multiplier for regional cost variation (1.0 = Erode baseline)
    """
    template = get_cost_template(category_code, scale)

    capex = {}
    for item in template["capital_expenditure"]:
        capex[item["name"]] = round(item["amount"] * location_factor, 2)

    wc = {}
    for item in template["working_capital"]:
        wc[item["name"]] = round(item["amount"] * location_factor, 2)

    infra = {}
    for item in template["infrastructure"]:
        infra[item["name"]] = round(item["amount"] * location_factor, 2)

    licensing = {}
    for item in template["licensing_compliance"]:
        licensing[item["name"]] = round(item["amount"] * location_factor, 2)

    # Apply custom overrides
    if custom_items:
        for key, val in custom_items.items():
            if key in capex:
                capex[key] = val
            elif key in wc:
                wc[key] = val
            elif key in infra:
                infra[key] = val
            elif key in licensing:
                licensing[key] = val

    subtotal = sum(capex.values()) + sum(wc.values()) + sum(infra.values()) + sum(licensing.values())
    contingency_pct = template.get("contingency_pct", 10.0)
    contingency_amount = round(subtotal * contingency_pct / 100.0, 2)
    total = round(subtotal + contingency_amount, 2)

    notes = []
    if location_factor != 1.0:
        notes.append(f"Costs adjusted by location factor {location_factor}x (Erode baseline = 1.0).")
    if custom_items:
        notes.append(f"Custom overrides applied for: {', '.join(custom_items.keys())}.")

    return CostBreakdown(
        category_code=category_code,
        scale=scale,
        capital_expenditure=capex,
        working_capital=wc,
        infrastructure=infra,
        licensing_compliance=licensing,
        contingency_pct=contingency_pct,
        contingency_amount=contingency_amount,
        total_project_cost=total,
        notes=notes,
    )


def structure_loan(
    cost: CostBreakdown,
    capital_available: float,
    eligible_schemes: Optional[list[EligibilityResult]] = None,
    preferred_scheme_code: Optional[str] = None,
    beneficiary_contribution_pct: Optional[float] = None,
    beneficiary_profile: Optional[BeneficiaryProfile] = None,
) -> LoanStructure:
    """Structure a loan against the cost breakdown, routing through eligible schemes.

    If eligible_schemes are provided, picks the best matching scheme (highest
    score that is ELIGIBLE). Otherwise falls back to default micro/term loan.
    """
    total_cost = cost.total_project_cost

    # Determine scheme to use
    scheme_rule = None
    chosen_eligibility = None
    if eligible_schemes:
        # Prefer explicitly requested scheme
        if preferred_scheme_code:
            for e in eligible_schemes:
                if e.scheme_code == preferred_scheme_code and e.status == "ELIGIBLE":
                    chosen_eligibility = e
                    break
        # Otherwise pick highest-scoring ELIGIBLE scheme
        if chosen_eligibility is None:
            for e in eligible_schemes:
                if e.status == "ELIGIBLE":
                    chosen_eligibility = e
                    break

        if chosen_eligibility:
            sd = chosen_eligibility.scheme_details
            scheme_rule = SchemeRule(
                code=sd["code"],
                name=sd["name"],
                min_project_cost=sd.get("min_project_cost"),
                max_project_cost=sd.get("max_project_cost"),
                max_loan_amount=sd.get("max_loan_amount"),
                interest_rate=sd.get("interest_rate") if sd.get("interest_rate") is not None else 10.0,
                tenure_years=sd.get("tenure_years") if sd.get("tenure_years") is not None else 5,
                moratorium_months=sd.get("moratorium_months") if sd.get("moratorium_months") is not None else 0,
                margin_pct=sd.get("margin_pct") if sd.get("margin_pct") is not None else 10.0,
                moratorium_mode=sd.get("moratorium_mode") or "interest_only_during_moratorium",
            )

    if scheme_rule is None:
        # Fallback: derive plan from capital available (only when capital is a
        # positive, usable amount). Otherwise use a neutral default rule so a
        # beneficiary who provided a project cost but no capital can still get a
        # structured plan without an artificial crash.
        if capital_available and capital_available > 0:
            from app.engines.finance import DEFAULT_SCHEMES
            plan = derive_financial_plan(capital_available, DEFAULT_SCHEMES)
            if plan.scheme:
                scheme_rule = plan.scheme
        if scheme_rule is None:
            scheme_rule = SchemeRule(
                code="term_loan", name="Term Loan",
                min_project_cost=0.0, max_project_cost=5_000_000,
                max_loan_amount=4_500_000,
                interest_rate=8.0, tenure_years=7, moratorium_months=6,
                margin_pct=10.0,
                source_document="Assumed demo parameters; verify with channelizing agency.",
            )

    # Beneficiary contribution
    if beneficiary_contribution_pct is not None:
        bc_pct = beneficiary_contribution_pct
    elif scheme_rule and scheme_rule.margin_pct:
        bc_pct = scheme_rule.margin_pct
    else:
        bc_pct = 10.0

    beneficiary_contribution = round(total_cost * bc_pct / 100.0, 2)
    loan_amount = round(total_cost - beneficiary_contribution, 2)

    # Enforce scheme loan cap
    max_loan = None
    notes = []
    if scheme_rule and scheme_rule.max_loan_amount:
        max_loan = scheme_rule.max_loan_amount
        if loan_amount > max_loan:
            notes.append(
                f"Loan capped from ₹{loan_amount:,.0f} to ₹{max_loan:,.0f} "
                f"(scheme maximum for {scheme_rule.name})."
            )
            loan_amount = max_loan
            # Recalculate contribution
            beneficiary_contribution = round(total_cost - loan_amount, 2)

    # Subsidy
    subsidy_amount = 0.0
    subsidy_pct = None
    sp = chosen_eligibility.scheme_details.get("subsidy_pct") if chosen_eligibility else None
    if sp is not None and sp > 0:
        subsidy_pct = sp
        subsidy_amount = round(loan_amount * subsidy_pct / 100.0, 2)
        notes.append(f"Subsidy of {subsidy_pct}% (₹{subsidy_amount:,.0f}) may be available under {scheme_rule.name}.")

    # Interest rate
    interest_rate = scheme_rule.interest_rate if scheme_rule else 10.0
    tenure_years = scheme_rule.tenure_years if scheme_rule else 5
    moratorium_months = scheme_rule.moratorium_months if scheme_rule else 6
    moratorium_mode = scheme_rule.moratorium_mode if scheme_rule else "interest_only_during_moratorium"

    # Build repayment schedule
    schedule = None
    emi_moratorium = 0.0
    emi_after = 0.0
    total_repayment = 0.0
    total_interest = 0.0
    quarterly = []

    if loan_amount > 0:
        schedule = build_schedule(
            principal=loan_amount,
            annual_rate=interest_rate,
            tenure_years=tenure_years,
            moratorium_months=moratorium_months,
            moratorium_mode=moratorium_mode,
        )
        emi_moratorium = schedule.monthly_emi_during_moratorium
        emi_after = schedule.monthly_emi_effective
        total_repayment = schedule.total_repayment
        total_interest = schedule.total_interest
        quarterly = schedule.quarterly

    # Repayment health
    health = None
    if beneficiary_profile:
        from app.engines.profit import simulate_model
        if beneficiary_profile.business_type:
            try:
                profit = simulate_model(beneficiary_profile.business_type)
                monthly_profit = profit.outputs.get("estimated_monthly_operating_profit", 0.0)
                # Debt service uses the ongoing post-moratorium EMI, which is the
                # recurring obligation the borrower services beyond the moratorium.
                if schedule and schedule.monthly_emi_effective > 0:
                    health = repayment_health(monthly_profit, schedule.monthly_emi_effective)
            except (ValueError, KeyError):
                pass

    # Build alternatives list
    alternatives = []
    if eligible_schemes:
        for e in eligible_schemes:
            if e.scheme_code != (chosen_eligibility.scheme_code if chosen_eligibility else None):
                sd = e.scheme_details
                alternatives.append({
                    "scheme_code": e.scheme_code,
                    "scheme_name": e.scheme_name,
                    "status": e.status,
                    "match_score": e.match_score,
                    "max_loan": sd.get("max_loan_amount"),
                    "interest_rate": sd.get("interest_rate"),
                    "reasons": e.mismatch_reasons[:3],
                })

    return LoanStructure(
        scheme_code=scheme_rule.code if scheme_rule else None,
        scheme_name=scheme_rule.name if scheme_rule else None,
        total_project_cost=total_cost,
        beneficiary_contribution=beneficiary_contribution,
        beneficiary_contribution_pct=bc_pct,
        loan_amount=loan_amount,
        max_loan_allowed=max_loan,
        subsidy_amount=subsidy_amount,
        subsidy_pct=subsidy_pct,
        interest_rate=interest_rate,
        tenure_years=tenure_years,
        moratorium_months=moratorium_months,
        moratorium_mode=moratorium_mode,
        monthly_emi_during_moratorium=emi_moratorium,
        monthly_emi_after_moratorium=emi_after,
        total_repayment=total_repayment,
        total_interest=total_interest,
        repayment_health=health,
        quarterly=quarterly,
        notes=notes,
    )


def structure_financials(
    profile: BeneficiaryProfile,
    category_code: str,
    scale: str = "micro",
    capital_available: float = 0.0,
    eligible_schemes: Optional[list[EligibilityResult]] = None,
    custom_cost_items: Optional[dict[str, float]] = None,
    location_factor: float = 1.0,
    beneficiary_contribution_pct: Optional[float] = None,
    preferred_scheme_code: Optional[str] = None,
) -> FinancialStructure:
    """Full financial structuring: cost breakdown + loan structure + scheme routing.

    This is the main entry point for the advisory financial analysis.
    """
    cost = build_cost_breakdown(category_code, scale, custom_cost_items, location_factor)
    loan = structure_loan(
        cost, capital_available, eligible_schemes, preferred_scheme_code,
        beneficiary_contribution_pct, profile,
    )

    return FinancialStructure(
        beneficiary={
            "state": profile.state,
            "district": profile.district,
            "block": profile.block,
            "village": profile.village,
            "business_type": profile.business_type,
            "age": profile.age,
            "beneficiary_category": profile.beneficiary_category,
            "capital_available": profile.capital_available,
        },
        cost_breakdown=cost,
        loan_structure=loan,
        scheme_eligibility=eligible_schemes[0].scheme_details if eligible_schemes and eligible_schemes[0].status == "ELIGIBLE" else None,
        recommended_scheme=loan.scheme_name,
        alternatives=loan.notes and [] or [],
    )


def to_dict(result: FinancialStructure) -> dict:
    """Serialize to JSON-safe dict."""
    return {
        "beneficiary": result.beneficiary,
        "cost_breakdown": {
            "category_code": result.cost_breakdown.category_code,
            "scale": result.cost_breakdown.scale,
            "capital_expenditure": result.cost_breakdown.capital_expenditure,
            "working_capital": result.cost_breakdown.working_capital,
            "infrastructure": result.cost_breakdown.infrastructure,
            "licensing_compliance": result.cost_breakdown.licensing_compliance,
            "contingency_pct": result.cost_breakdown.contingency_pct,
            "contingency_amount": result.cost_breakdown.contingency_amount,
            "total_project_cost": result.cost_breakdown.total_project_cost,
            "notes": result.cost_breakdown.notes,
        },
        "loan_structure": {
            "scheme_code": result.loan_structure.scheme_code,
            "scheme_name": result.loan_structure.scheme_name,
            "total_project_cost": result.loan_structure.total_project_cost,
            "beneficiary_contribution": result.loan_structure.beneficiary_contribution,
            "beneficiary_contribution_pct": result.loan_structure.beneficiary_contribution_pct,
            "loan_amount": result.loan_structure.loan_amount,
            "max_loan_allowed": result.loan_structure.max_loan_allowed,
            "subsidy_amount": result.loan_structure.subsidy_amount,
            "subsidy_pct": result.loan_structure.subsidy_pct,
            "interest_rate": result.loan_structure.interest_rate,
            "tenure_years": result.loan_structure.tenure_years,
            "moratorium_months": result.loan_structure.moratorium_months,
            "monthly_emi_during_moratorium": result.loan_structure.monthly_emi_during_moratorium,
            "monthly_emi_after_moratorium": result.loan_structure.monthly_emi_after_moratorium,
            "total_repayment": result.loan_structure.total_repayment,
            "total_interest": result.loan_structure.total_interest,
            "repayment_health": result.loan_structure.repayment_health,
            "quarterly": result.loan_structure.quarterly,
            "notes": result.loan_structure.notes,
        },
        "recommended_scheme": result.recommended_scheme,
        "alternatives": result.alternatives,
        "disclaimer": result.disclaimer,
    }
