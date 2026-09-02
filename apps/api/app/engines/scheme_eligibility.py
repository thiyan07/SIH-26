"""Deterministic scheme eligibility matching engine.

Given a beneficiary profile + business context, scores every active
government scheme and returns ranked matches with reasons.

NEVER uses an LLM for eligibility decisions — purely rule-based.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import GovernmentScheme


@dataclass
class BeneficiaryProfile:
    """What we know (or don't know) about the applicant."""
    state: Optional[str] = None
    district: Optional[str] = None
    block: Optional[str] = None
    village: Optional[str] = None
    business_type: Optional[str] = None  # category_code
    project_cost: Optional[float] = None
    capital_available: Optional[float] = None
    age: Optional[int] = None
    annual_income: Optional[float] = None
    beneficiary_category: Optional[str] = None  # sc_st|obc|general|women|minority|ews
    has_existing_business: Optional[bool] = None
    is_domicile: Optional[bool] = None
    family_members: Optional[int] = None
    preferred_scale: Optional[str] = None  # micro|small|medium


@dataclass
class EligibilityResult:
    scheme_code: str
    scheme_name: str
    match_score: float  # 0-100
    status: str  # ELIGIBLE|PARTIALLY_ELIGIBLE|NOT_ELIGIBLE|INSUFFICIENT_INFO
    matching_reasons: list[str] = field(default_factory=list)
    mismatch_reasons: list[str] = field(default_factory=list)
    missing_information: list[str] = field(default_factory=list)
    scheme_details: dict = field(default_factory=dict)


def _rule_matches(rule_value: Any, profile_value: Any, label: str) -> tuple[bool, str]:
    """Check if a single rule condition matches. Returns (matches, reason)."""
    if rule_value is None:
        return True, f"{label}: no restriction (any value accepted)"
    if profile_value is None:
        return False, f"{label}: information not provided"
    if isinstance(rule_value, list):
        if profile_value in rule_value:
            return True, f"{label}: '{profile_value}' is in eligible list"
        return False, f"{label}: '{profile_value}' is not in eligible list ({rule_value[:5]}{'...' if len(rule_value) > 5 else ''})"
    if isinstance(rule_value, (int, float)):
        if profile_value == rule_value:
            return True, f"{label}: matches {rule_value}"
        return False, f"{label}: {profile_value} does not match required {rule_value}"
    if isinstance(rule_value, str):
        if profile_value.lower() == rule_value.lower():
            return True, f"{label}: matches '{rule_value}'"
        return False, f"{label}: '{profile_value}' does not match '{rule_value}'"
    return True, f"{label}: rule type not recognized, accepted"


def _check_age(min_age: Optional[int], max_age: Optional[int], age: Optional[int]) -> tuple[bool, str, str]:
    """Returns (passes, match_reason, fail_reason)."""
    if min_age is None and max_age is None:
        return True, "Age: no restriction", ""
    if age is None:
        return False, "", "Age: information not provided"
    if min_age is not None and age < min_age:
        return False, "", f"Age: {age} is below minimum {min_age}"
    if max_age is not None and age > max_age:
        return False, "", f"Age: {age} exceeds maximum {max_age}"
    age_range = f"{min_age or 'any'}-{max_age or 'any'}"
    return True, f"Age: {age} within range ({age_range})", ""


def _check_income(min_income: Optional[float], max_income: Optional[float], income: Optional[float]) -> tuple[bool, str, str]:
    if min_income is None and max_income is None:
        return True, "Income: no restriction", ""
    if income is None:
        return False, "", "Income: information not provided"
    if min_income is not None and income < min_income:
        return False, "", f"Income: ₹{income:,.0f} is below minimum ₹{min_income:,.0f}"
    if max_income is not None and income > max_income:
        return False, "", f"Income: ₹{income:,.0f} exceeds maximum ₹{max_income:,.0f}"
    return True, f"Income: ₹{income:,.0f} within eligible range", ""


def _check_project_cost(scheme: GovernmentScheme, project_cost: Optional[float]) -> tuple[bool, str, str]:
    if project_cost is None:
        return False, "", "Project cost: not provided"
    min_cost = float(scheme.min_project_cost) if scheme.min_project_cost is not None else 0
    max_cost = float(scheme.max_project_cost) if scheme.max_project_cost is not None else float("inf")
    if project_cost < min_cost:
        return False, "", f"Project cost: ₹{project_cost:,.0f} is below minimum ₹{min_cost:,.0f}"
    if project_cost > max_cost:
        return False, "", f"Project cost: ₹{project_cost:,.0f} exceeds maximum ₹{max_cost:,.0f}"
    return True, f"Project cost: ₹{project_cost:,.0f} within ₹{min_cost:,.0f}–₹{max_cost:,.0f}", ""


def _check_business_type(eligible_types: Any, business_type: Optional[str]) -> tuple[bool, str, str]:
    if eligible_types is None:
        return True, "Business type: all types eligible", ""
    if business_type is None:
        return False, "", "Business type: not specified"
    if business_type in eligible_types:
        return True, f"Business type: '{business_type}' is supported", ""
    # Also check broader categories (e.g., "dairy" might match "farming" umbrella)
    return False, f"Business type: '{business_type}' is not in supported list", ""


def _check_location(eligible_states: Any, eligible_districts: Any,
                    state: Optional[str], district: Optional[str]) -> tuple[bool, str, str]:
    if eligible_states is None and eligible_districts is None:
        return True, "Location: available everywhere", ""
    if state is None:
        return False, "", "Location: state not provided"
    if eligible_states is not None and state not in eligible_states:
        return False, f"Location: '{state}' is not in eligible states", ""
    if eligible_districts is not None and district is not None and district not in eligible_districts:
        return False, f"Location: '{district}' is not in eligible districts", ""
    return True, "Location: meets geographic eligibility", ""


def _check_category_beneficiary(eligible_categories: Any, beneficiary_category: Optional[str]) -> tuple[bool, str, str]:
    if eligible_categories is None or eligible_categories == ["all"]:
        return True, "Category: open to all", ""
    if beneficiary_category is None:
        return False, "", "Category: beneficiary category not specified"
    if beneficiary_category in eligible_categories:
        return True, f"Category: '{beneficiary_category}' is a target group", ""
    return False, f"Category: '{beneficiary_category}' is not in target groups", ""


def _compute_score(passes: int, fails: int, missing: int, total: int) -> float:
    """Weighted score: passes contribute positively, fails and missing reduce."""
    if total == 0:
        return 50.0
    pass_weight = 100.0 / total
    score = passes * pass_weight - fails * (pass_weight * 0.5) - missing * (pass_weight * 0.3)
    return round(max(0.0, min(100.0, score)), 1)


def _status_from_score(score: float, has_fail: bool, all_info: bool) -> str:
    if score >= 80 and not has_fail:
        return "ELIGIBLE"
    if score >= 50 and has_fail:
        return "PARTIALLY_ELIGIBLE"
    if score < 30:
        return "NOT_ELIGIBLE"
    if not all_info:
        return "INSUFFICIENT_INFO"
    return "PARTIALLY_ELIGIBLE"


def match_schemes(db: Session, profile: BeneficiaryProfile) -> list[EligibilityResult]:
    """Score all active government schemes against the given beneficiary profile.
    
    Returns list of EligibilityResult sorted by match_score descending.
    Never fabricates — missing info is reported as missing_information.
    """
    schemes = list(db.execute(
        select(GovernmentScheme).where(GovernmentScheme.is_active.is_(True))
    ).scalars())
    
    if not schemes:
        return []
    
    results = []
    for scheme in schemes:
        matching = []
        mismatching = []
        missing = []
        passes = 0
        fails = 0
        missing_count = 0
        has_fail = False
        all_info = True
        
        # 1. Project cost (highest priority)
        cost_ok, cost_match, cost_fail = _check_project_cost(scheme, profile.project_cost)
        if cost_ok:
            matching.append(cost_match)
            passes += 1
        elif cost_fail:
            if profile.project_cost is None:
                missing.append(cost_fail)
                missing_count += 1
                all_info = False
            else:
                mismatching.append(cost_fail)
                fails += 1
                has_fail = True
        
        # 2. Business type
        biz_ok, biz_match, biz_fail = _check_business_type(scheme.eligible_business_types, profile.business_type)
        if biz_ok:
            matching.append(biz_match)
            passes += 1
        elif biz_fail:
            if profile.business_type is None:
                missing.append(biz_fail)
                missing_count += 1
                all_info = False
            else:
                mismatching.append(biz_fail)
                fails += 1
                has_fail = True
        
        # 3. Location
        loc_ok, loc_match, loc_fail = _check_location(
            scheme.eligible_states, scheme.eligible_districts,
            profile.state, profile.district,
        )
        if loc_ok:
            matching.append(loc_match)
            passes += 1
        elif loc_fail:
            if profile.state is None:
                missing.append(loc_fail)
                missing_count += 1
                all_info = False
            else:
                mismatching.append(loc_fail)
                fails += 1
                has_fail = True
        
        # 4. Beneficiary category
        cat_ok, cat_match, cat_fail = _check_category_beneficiary(
            scheme.target_beneficiary_categories, profile.beneficiary_category,
        )
        if cat_ok:
            matching.append(cat_match)
            passes += 1
        elif cat_fail:
            if profile.beneficiary_category is None:
                missing.append(cat_fail)
                missing_count += 1
                all_info = False
            else:
                mismatching.append(cat_fail)
                fails += 1
                has_fail = True
        
        # 5. Age
        if scheme.min_age is not None or scheme.max_age is not None:
            age_ok, age_match, age_fail = _check_age(scheme.min_age, scheme.max_age, profile.age)
            if age_ok:
                matching.append(age_match)
                passes += 1
            elif age_fail:
                if profile.age is None:
                    missing.append(age_fail)
                    missing_count += 1
                    all_info = False
                else:
                    mismatching.append(age_fail)
                    fails += 1
                    has_fail = True
        
        # 6. Income
        if scheme.min_annual_income is not None or scheme.max_annual_income is not None:
            inc_ok, inc_match, inc_fail = _check_income(
                float(scheme.min_annual_income) if scheme.min_annual_income else None,
                float(scheme.max_annual_income) if scheme.max_annual_income else None,
                profile.annual_income,
            )
            if inc_ok:
                matching.append(inc_match)
                passes += 1
            elif inc_fail:
                if profile.annual_income is None:
                    missing.append(inc_fail)
                    missing_count += 1
                    all_info = False
                else:
                    mismatching.append(inc_fail)
                    fails += 1
                    has_fail = True
        
        # 7. Existing business requirement
        if scheme.requires_existing_business is not None:
            if profile.has_existing_business is None:
                missing.append("Existing business status: not specified")
                missing_count += 1
                all_info = False
            elif scheme.requires_existing_business and not profile.has_existing_business:
                mismatching.append("Requires existing business: applicant does not have one")
                fails += 1
                has_fail = True
            else:
                matching.append("Existing business: requirement satisfied")
                passes += 1
        
        total_checks = passes + fails + missing_count
        score = _compute_score(passes, fails, missing_count, total_checks)
        status = _status_from_score(score, has_fail, all_info)
        
        # Build scheme details for the response
        details = {
            "code": scheme.code,
            "name": scheme.name,
            "description": scheme.description,
            "implementing_agency": scheme.implementing_agency,
            "scheme_url": scheme.scheme_url,
            "scheme_type": scheme.scheme_type,
            "min_project_cost": float(scheme.min_project_cost) if scheme.min_project_cost is not None else None,
            "max_project_cost": float(scheme.max_project_cost) if scheme.max_project_cost is not None else None,
            "max_loan_amount": float(scheme.max_loan_amount) if scheme.max_loan_amount is not None else None,
            "interest_rate": scheme.interest_rate,
            "tenure_years": scheme.tenure_years,
            "moratorium_months": scheme.moratorium_months,
            "margin_pct": scheme.margin_pct,
            "beneficiary_contribution_pct": float(scheme.beneficiary_contribution_pct) if scheme.beneficiary_contribution_pct is not None else None,
            "subsidy_pct": float(scheme.subsidy_pct) if scheme.subsidy_pct is not None else None,
            "required_documents": scheme.required_documents,
            "application_authority": scheme.application_authority,
            "application_process": scheme.application_process,
            "source_url": scheme.scheme_url,
            "confidence_level": scheme.confidence_level,
        }
        
        results.append(EligibilityResult(
            scheme_code=scheme.code,
            scheme_name=scheme.name,
            match_score=score,
            status=status,
            matching_reasons=matching,
            mismatch_reasons=mismatching,
            missing_information=missing,
            scheme_details=details,
        ))
    
    results.sort(key=lambda r: r.match_score, reverse=True)
    return results


def to_dict(result: EligibilityResult) -> dict:
    """Serialize EligibilityResult to a JSON-safe dict."""
    return {
        "scheme_code": result.scheme_code,
        "scheme_name": result.scheme_name,
        "match_score": result.match_score,
        "status": result.status,
        "matching_reasons": result.matching_reasons,
        "mismatch_reasons": result.mismatch_reasons,
        "missing_information": result.missing_information,
        "scheme_details": result.scheme_details,
    }
