"""End-to-end advisory report orchestrator.

Takes a parsed NLP input (or structured form data) and produces:
1. Scheme eligibility matches
2. Cost breakdown (CAPEX/WC/infra/licensing)
3. Loan structure with EMI schedule
4. SWOT / risk analysis
5. Recommended action plan
6. Full advisory report

This is the main SIH26091 advisory pipeline — all deterministic, no LLM.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy.orm import Session

from app.ai.extractor import parse_multilingual_free_text
from app.engines.cost_templates import LOCATION_FACTORS
from app.engines.financial_structuring import (
    FinancialStructure,
    structure_financials,
)
from app.engines.financial_structuring import (
    to_dict as financial_to_dict,
)
from app.engines.nlp_parser import ParsedInput
from app.engines.nlp_parser import to_dict as nlp_to_dict
from app.engines.profit import simulate_model
from app.engines.scheme_eligibility import (
    BeneficiaryProfile,
    EligibilityResult,
    match_schemes,
)
from app.engines.scheme_eligibility import (
    to_dict as eligibility_to_dict,
)


@dataclass
class AdvisoryReport:
    """Complete advisory output combining all engines."""
    parsed_input: Optional[ParsedInput] = None
    beneficiary_profile: Optional[BeneficiaryProfile] = None
    scheme_eligibility: list[EligibilityResult] = field(default_factory=list)
    financial_structure: Optional[FinancialStructure] = None
    profit_model: Optional[dict] = None
    market_context: Optional[dict] = None
    business_intelligence: Optional[dict] = None
    suggested_businesses: list[dict] = field(default_factory=list)
    risks: list[dict] = field(default_factory=list)
    action_plan: list[str] = field(default_factory=list)
    key_documents: list[str] = field(default_factory=list)
    summary: str = ""
    disclaimer: str = (
        "This advisory is based on estimated models and publicly available scheme "
        "information. Actual eligibility, costs, and terms depend on lender appraisal, "
        "scheme sanction, and market conditions. Always verify with the implementing "
        "agency before making financial commitments."
    )


def _get_location_factor(location: dict) -> float:
    """Map location to cost factor."""
    block = (location.get("block") or "").lower().strip()
    if block in LOCATION_FACTORS:
        return LOCATION_FACTORS[block]
    village = (location.get("village") or "").lower().strip()
    if village in LOCATION_FACTORS:
        return LOCATION_FACTORS[village]
    if (location.get("district") or "").lower() == "erode":
        return 1.0
    return 1.0


def _build_beneficiary_profile(parsed: ParsedInput) -> BeneficiaryProfile:
    """Convert parsed NLP input to beneficiary profile."""
    # Defaults for new rural entrepreneurs (avoid INSUFFICIENT_INFO on required fields)
    loc_state = parsed.location.get("state") or "Tamil Nadu"
    return BeneficiaryProfile(
        state=loc_state,
        district=parsed.location.get("district") or "Erode",
        block=parsed.location.get("block"),
        village=parsed.location.get("village"),
        business_type=parsed.business_type,
        project_cost=parsed.project_cost,
        capital_available=parsed.capital_available,
        age=parsed.age or 30,
        annual_income=parsed.annual_income,
        beneficiary_category=parsed.beneficiary_category or "general",
        has_existing_business=False,
        is_domicile=True if loc_state == "Tamil Nadu" else None,
        preferred_scale=parsed.scale or "micro",
    )


def _assess_risks(business_type: str, profit_model: dict, financial: FinancialStructure) -> list[dict]:
    """Generate risk assessment based on all available data."""
    risks = []
    ls = financial.loan_structure

    # Seasonal cash-flow risk (from the seasonal intelligence engine).
    from app.engines.business_intelligence import seasonal_intelligence
    seasonal = seasonal_intelligence(business_type or "other")
    risks.append({
        "category": "Seasonal",
        "risk": f"Seasonal cash-flow risk is {seasonal['cash_flow_risk'].lower()}",
        "level": seasonal["cash_flow_risk"].lower(),
        "detail": (f"{seasonal['cash_flow_risk_reason']} Peak in month "
                   f"{seasonal['peak_month']}, low in month {seasonal['low_month']} "
                   f"(index {seasonal['low_index']:.2f})."),
        "mitigation": seasonal["inventory_implication"],
        "seasonal_intelligence": seasonal,
    })

    # Financial risk
    if ls.repayment_health:
        health = ls.repayment_health
        if health["label"] == "High Risk":
            risks.append({
                "category": "Financial",
                "risk": "Debt service coverage is below 1.0",
                "level": "high",
                "detail": f"Monthly profit ₹{health['monthly_profit']:,.0f} vs EMI ₹{health['monthly_debt_service']:,.0f}. "
                          f"Coverage ratio: {health['coverage_ratio']}.",
                "mitigation": "Consider smaller loan, higher contribution, or scheme with lower interest.",
            })
        elif health["label"] == "Moderate":
            risks.append({
                "category": "Financial",
                "risk": "Debt service coverage is tight",
                "level": "medium",
                "detail": f"Coverage ratio: {health['coverage_ratio']}. Limited buffer for downturns.",
                "mitigation": "Maintain 3-month EMI reserve. Consider working capital line.",
            })

    # Operating margin risk
    if profit_model:
        margin = profit_model.get("operating_margin_pct", 0)
        if margin < 15:
            risks.append({
                "category": "Operational",
                "risk": "Low operating margin",
                "level": "medium",
                "detail": f"Estimated margin {margin}% leaves limited room for cost increases.",
                "mitigation": "Negotiate better supplier terms, optimize operations, diversify revenue.",
            })

    # Market risk based on category
    category_risks = {
        "dairy": ("Milk price volatility and feed cost increases can erode margins quickly.",
                  "Secure dairy cooperative membership. Lock in feed supply contracts."),
        "poultry": ("Disease outbreaks (bird flu) can cause total flock loss within days.",
                    "Implement biosecurity protocols. Get poultry insurance."),
        "grocery": ("Thin margins (8-15%) make volume essential. Credit sales strain cash flow.",
                    "Limit credit to regulars. Track inventory weekly."),
        "food_processing": ("Raw material seasonality and shelf-life limits distribution range.",
                            "Build storage for peak season. Source from multiple suppliers."),
        "restaurant": ("High fixed costs (rent, staff) with variable footfall create leverage risk.",
                       "Start with takeaway/cloud kitchen. Control portion costs."),
        "textile": ("Fashion cycle risk — unsold inventory becomes dead stock quickly.",
                    "Focus on made-to-order for bulk. Keep ready stock minimal."),
        "agriculture": ("Weather and price realisation risk concentrated around harvest.",
                        "Get crop insurance. Consider value-addition to reduce raw sale."),
        "manufacturing": ("Working-capital intensive with receivable delays from buyers.",
                          "Maintain 60-day WC buffer. Invoice factoring if needed."),
        "handicrafts": ("Niche demand, slow inventory turnover, tourism dependence.",
                        "Sell online (Amazon/Flipkart craft). Attend trade fairs."),
    }

    if business_type in category_risks:
        detail, mitigation = category_risks[business_type]
        risks.append({
            "category": "Market",
            "risk": f"{business_type.title()} sector risk",
            "level": "medium",
            "detail": detail,
            "mitigation": mitigation,
        })

    # Scheme-related risk
    eligible_count = sum(1 for e in financial.alternatives if e.get("status") == "ELIGIBLE") if financial.alternatives else 0
    if eligible_count == 0 and ls.scheme_code is None:
        risks.append({
            "category": "Scheme",
            "risk": "No eligible government scheme identified",
            "level": "medium",
            "detail": "Project may need full self-financing or private lending.",
            "mitigation": "Consult District Industries Centre (DIC) for updated schemes.",
        })

    return risks


def _build_action_plan(
    parsed: ParsedInput,
    eligibility: list[EligibilityResult],
    financial: FinancialStructure,
    profit_model: Optional[dict],
) -> list[str]:
    """Generate recommended action items."""
    plan = []
    ls = financial.loan_structure

    plan.append("1. Verify all cost estimates with local suppliers and contractors.")
    plan.append("2. Prepare required documents (see documents list below).")

    # Scheme application
    if ls.scheme_code:
        plan.append(
            f"3. Apply for {ls.scheme_name} scheme. "
            f"Loan amount: ₹{ls.loan_amount:,.0f}, "
            f"Your contribution: ₹{ls.beneficiary_contribution:,.0f}."
        )
        if ls.shortfall > 0:
            plan.append(
                f"3a. Address contribution shortfall of ₹{ls.shortfall:,.0f} — "
                f"arrange additional own capital or confirm scheme flexibility."
            )
    else:
        plan.append("3. No eligible scheme found — arrange financing through bank or self-funding.")

    plan.append("4. Register business: Udyam/MSME registration (free online).")
    plan.append("5. Open business bank account for scheme disbursement.")

    # Category-specific
    category_actions = {
        "dairy": "6. Source animals from verified breeders. Get veterinary check before purchase. Register with local dairy cooperative.",
        "poultry": "6. Set up coop with proper ventilation. Start with vaccinated chicks from hatchery. Get poultry insurance.",
        "grocery": "6. Negotiate wholesale terms with 2-3 distributors. Install POS system from day one.",
        "textile": "6. Source fabric from Erode textile market. Build portfolio of designs before launch.",
        "food_processing": "6. Get FSSAI license BEFORE starting production. Source raw materials during harvest for best prices.",
        "restaurant": "6. Finalize menu with 8-12 items. Source from local mandi. Set up online ordering (Zomato/Swiggy).",
        "agriculture": "6. Get soil test done. Plan crop calendar with agricultural officer. Enroll in crop insurance (PMFBY).",
        "manufacturing": "6. Set up quality checks. Get factory license if >10 workers. Maintain safety protocols.",
        "handicrafts": "6. Set up online store (Amazon/Flipkart). Attend local craft exhibitions. Build brand identity.",
    }
    if parsed.business_type in category_actions:
        plan.append(category_actions[parsed.business_type])

    plan.append("7. Maintain books of accounts from day one (use free tools like Vyapar/Zoho).")
    plan.append("8. Review repayment health quarterly. Build 3-month EMI emergency reserve.")

    return plan


def _build_documents_list(
    parsed: ParsedInput,
    eligibility: list[EligibilityResult],
) -> list[str]:
    """Compile required documents from eligible schemes."""
    docs = {
        "Aadhaar Card",
        "PAN Card (or Form 60)",
        "Address proof (utility bill / rent agreement)",
        "Passport-size photographs (4 copies)",
        "Bank account statements (last 6 months)",
    }

    # Add scheme-specific documents
    for e in eligibility:
        if e.status == "ELIGIBLE" and e.scheme_details.get("required_documents"):
            for doc in e.scheme_details["required_documents"]:
                docs.add(doc)

    # Common scheme requirements
    docs.add("Business project report / DPR")
    docs.add("Udyam/MSME registration certificate")
    docs.add("Quotations for equipment/machinery")

    # Location-specific
    if parsed.location.get("state") == "Tamil Nadu":
        docs.add("Tamil Nadu land records (Pahani / Chitta)")
        docs.add("Community certificate (if applicable)")

    # Category-specific
    if parsed.business_type == "dairy":
        docs.add("Veterinary fitness certificate for animals")
        docs.add("FSSAI registration (for milk sales)")
    elif parsed.business_type == "poultry":
        docs.add("Poultry farm registration")
        docs.add("Vaccination records")
    elif parsed.business_type in ("grocery", "restaurant"):
        docs.add("FSSAI license")
        docs.add("Shop & Establishment license")
    elif parsed.business_type == "food_processing":
        docs.add("FSSAI state/central license")
        docs.add("Pollution board NOC")

    return sorted(docs)


def _recommend_businesses(
    db: Session,
    parsed: ParsedInput,
    profile: BeneficiaryProfile,
) -> list[dict]:
    """When user gives details but no business_type, rank all categories.

    Deterministic scoring (no LLM) using existing engines:
    - Affordability: project_cost vs capital (lower shortfall = higher)
    - Profitability: estimated_monthly_operating_profit
    - Competition: count of similar businesses within 5km (lower = higher)
    - Scheme fit: eligible schemes count for that category
    Returns top 5 with reasons and full financial_structure for the best.
    """
    from app.catalog.business_categories import all_codes
    from app.db.models import Location
    from app.engines.competition import analyze as analyze_competition
    from app.engines.cost_templates import get_total_template_cost
    from app.engines.profit import simulate_model
    from app.engines.scheme_eligibility import BeneficiaryProfile as BP
    from app.engines.scheme_eligibility import match_schemes

    capital = parsed.capital_available or 0
    scale = parsed.scale or "micro"
    location = parsed.location or {}

    # Find location coords for competition check (best effort)
    lat = lon = None
    try:
        if location.get("block") or location.get("village"):
            q = db.query(Location).filter(
                Location.state == (location.get("state") or "Tamil Nadu"),
                Location.district == (location.get("district") or "Erode"),
            )
            if location.get("block"):
                q = q.filter(Location.block.ilike(location["block"]))
            if location.get("village"):
                q = q.filter(Location.village.ilike(location["village"]))
            loc = q.first()
            if loc and loc.latitude and loc.longitude:
                lat, lon = loc.latitude, loc.longitude
    except Exception:
        pass

    candidates = []
    for code in all_codes():
        # Only categories with a cost template are financially modellable
        try:
            total_cost = get_total_template_cost(code, scale)
        except Exception:
            continue
        # Affordability score: 0-100, higher if capital covers cost
        shortfall = max(0, total_cost * 0.1 - capital) if total_cost else 0  # 10% margin rule
        affordability = 100 if capital >= total_cost else max(0, 100 - (shortfall / total_cost * 100) * 2) if total_cost else 50
        if capital == 0:
            affordability = 60  # neutral when no capital given

        # Profit score
        try:
            profit = simulate_model(code)
            monthly_profit = profit.outputs.get("estimated_monthly_operating_profit", 0) or 0
            profit_score = min(100, max(0, (monthly_profit / 50000) * 100))  # normalize 50k = 100
        except Exception:
            monthly_profit = 0
            profit_score = 30

        # Competition score (if coords available, else neutral 50)
        comp_score = 50
        comp_count = None
        if lat and lon:
            try:
                comp = analyze_competition(db, lat, lon, code, radius_km=5)
                comp_count = comp.direct_count if hasattr(comp, 'direct_count') else comp.competitors_5km if hasattr(comp, 'competitors_5km') else 0
                # comp_score already 0-100 in engine (higher = less competition)
                comp_score = getattr(comp, 'competition_score', 50) or 50
            except Exception:
                pass

        # Scheme fit
        try:
            prof = BP(
                state=profile.state, district=profile.district, block=profile.block,
                village=profile.village, business_type=code,
                project_cost=total_cost, capital_available=capital,
                age=profile.age or 30, annual_income=profile.annual_income,
                beneficiary_category=profile.beneficiary_category or "general",
                has_existing_business=False, is_domicile=True,
                preferred_scale=scale,
            )
            schemes = match_schemes(db, prof)
            eligible = sum(1 for s in schemes if s.status == "ELIGIBLE")
            scheme_score = min(100, eligible * 40)  # 1 eligible =40, 2=80
        except Exception:
            eligible = 0
            scheme_score = 40

        # Composite: affordability 30%, profit 30%, competition 20%, scheme 20%
        overall = round(affordability * 0.30 + profit_score * 0.30 + comp_score * 0.20 + scheme_score * 0.20, 1)

        # Reason
        reasons = []
        if affordability >= 80:
            reasons.append(f"Fits your capital ₹{capital:,.0f} (cost ₹{total_cost:,.0f})")
        elif affordability < 50:
            reasons.append(f"Needs higher capital (cost ₹{total_cost:,.0f} vs ₹{capital:,.0f} available)")
        if monthly_profit > 20000:
            reasons.append(f"High profit ~₹{monthly_profit:,.0f}/mo")
        if comp_count is not None and comp_count < 3:
            reasons.append(f"Low competition ({comp_count} nearby)")
        if eligible > 0:
            reasons.append(f"{eligible} eligible scheme(s)")

        candidates.append({
            "business_type": code,
            "label": code.replace("_", " ").title(),
            "scale": scale,
            "total_project_cost": total_cost,
            "capital_available": capital,
            "shortfall": max(0, total_cost * 0.1 - capital),
            "estimated_monthly_profit": monthly_profit,
            "competitors_5km": comp_count,
            "eligible_schemes": eligible,
            "scores": {"affordability": round(affordability,1), "profit": round(profit_score,1), "competition": round(comp_score,1), "scheme": scheme_score, "overall": overall},
            "overall_score": overall,
            "reasons": reasons or ["Balanced opportunity"],
        })

    candidates.sort(key=lambda x: x["overall_score"], reverse=True)
    return candidates[:5]


def _generate_summary(
    parsed: ParsedInput,
    eligibility: list[EligibilityResult],
    financial: FinancialStructure,
    risks: list[dict],
) -> str:
    """Generate a human-readable summary."""
    ls = financial.loan_structure
    cb = financial.cost_breakdown

    district = parsed.location.get('district') or parsed.location.get('state') and 'Erode' or 'Erode'
    # Fallback chain: parsed district → Tamil Nadu implies Erode → Unknown
    district = parsed.location.get('district') or 'Erode'
    if not district or district == 'None':
        district = 'Erode'
    lines = []
    lines.append(f"Business Advisory Report — {district} District")
    lines.append("")

    # Business overview
    biz_name = parsed.business_type.replace("_", " ").title() if parsed.business_type else "Business"
    scale = parsed.scale or "micro"
    lines.append(f"Proposed venture: {biz_name} ({scale} scale)")
    block = parsed.location.get("block") or parsed.location.get("village") or "Perundurai"
    district = parsed.location.get("district") or "Erode"
    if block or district:
        lines.append(f"Location: {block}, {district}")
    lines.append("")

    # Cost overview
    lines.append(f"Estimated Project Cost: ₹{cb.total_project_cost:,.0f}")
    lines.append(f"  Capital Expenditure: ₹{sum(cb.capital_expenditure.values()):,.0f}")
    lines.append(f"  Working Capital:     ₹{sum(cb.working_capital.values()):,.0f}")
    lines.append(f"  Infrastructure:      ₹{sum(cb.infrastructure.values()):,.0f}")
    lines.append(f"  Licensing/Compliance:₹{sum(cb.licensing_compliance.values()):,.0f}")
    lines.append(f"  Contingency ({cb.contingency_pct}%): ₹{cb.contingency_amount:,.0f}")
    lines.append("")

    # Funding
    lines.append(f"Your Contribution: ₹{ls.beneficiary_contribution:,.0f} ({ls.beneficiary_contribution_pct}%)")
    lines.append(f"Required Financing: ₹{ls.required_financing:,.0f}")
    lines.append(f"Loan Amount: ₹{ls.loan_amount:,.0f}")
    if ls.shortfall > 0:
        lines.append(f"Contribution Shortfall: ₹{ls.shortfall:,.0f} (add own capital to qualify for full financing)")
    if ls.subsidy_amount > 0:
        lines.append(f"Subsidy ({ls.subsidy_pct}%): ₹{ls.subsidy_amount:,.0f}")
    lines.append("")

    # Scheme
    if ls.scheme_code:
        lines.append(f"Recommended Scheme: {ls.scheme_name}")
        lines.append(f"  Interest Rate: {ls.interest_rate}%")
        lines.append(f"  Tenure: {ls.tenure_years} years")
        lines.append(f"  Moratorium: {ls.moratorium_months} months")
        lines.append(f"  Monthly EMI: ₹{ls.monthly_emi_after_moratorium:,.0f}")
        lines.append(f"  Total Repayment: ₹{ls.total_repayment:,.0f}")
    else:
        lines.append("No eligible government scheme found. Self-financing or bank loan required.")
    lines.append("")

    # Profitability
    if parsed.business_type:
        try:
            profit = simulate_model(parsed.business_type)
            mp = profit.outputs.get("estimated_monthly_operating_profit", 0)
            lines.append(f"Estimated Monthly Operating Profit: ₹{mp:,.0f}")
            if ls.monthly_emi_after_moratorium > 0:
                ratio = mp / ls.monthly_emi_after_moratorium if ls.monthly_emi_after_moratorium else 0
                lines.append(f"EMI Coverage Ratio: {ratio:.1f}x")
        except (ValueError, KeyError):
            pass
    lines.append("")

    # Top risks
    high_risks = [r for r in risks if r.get("level") == "high"]
    if high_risks:
        lines.append("KEY RISKS:")
        for r in high_risks[:3]:
            lines.append(f"  [{r['category']}] {r['risk']}")
    lines.append("")

    lines.append("Next steps: See full report for detailed action plan and document checklist.")

    return "\n".join(lines)


def _overlay_structured(parsed: ParsedInput, structured_input: dict) -> None:
    """Overlay explicitly provided structured fields onto an NLP-parsed input.

    Only non-None values from the caller override the parse, so an explicitly
    provided figure (e.g. a capital amount the parser could not infer) is never
    silently discarded while also never clobbering a confident NLP result.
    """
    if structured_input.get("state") is not None:
        parsed.location["state"] = structured_input.get("state")
    if structured_input.get("district") is not None:
        parsed.location["district"] = structured_input.get("district")
    if structured_input.get("block") is not None:
        parsed.location["block"] = structured_input.get("block")
    if structured_input.get("village") is not None:
        parsed.location["village"] = structured_input.get("village")
    for key, attr in (
        ("business_type", "business_type"),
        ("scale", "scale"),
        ("project_cost", "project_cost"),
        ("capital_available", "capital_available"),
        ("annual_income", "annual_income"),
        ("age", "age"),
        ("beneficiary_category", "beneficiary_category"),
    ):
        value = structured_input.get(key)
        if value is not None:
            setattr(parsed, attr, value)


def run_advisory(
    db: Session,
    free_text: Optional[str] = None,
    parsed: Optional[ParsedInput] = None,
    structured_input: Optional[dict] = None,
) -> AdvisoryReport:
    """Main entry point: run the full advisory pipeline.

    Accepts either free text (NLP parsing) or pre-structured input dict. When
    both are supplied, structured fields are overlaid onto the NLP parse so no
    explicitly provided values are discarded. Returns a complete AdvisoryReport.
    """
    # Step 1: Parse input
    if parsed is None:
        if free_text:
            parsed = parse_multilingual_free_text(free_text)
        elif structured_input:
            # Build ParsedInput from structured dict
            parsed = ParsedInput(
                raw_text=structured_input.get("free_text", ""),
                detected_language=structured_input.get("language", "en"),
                location={
                    "state": structured_input.get("state"),
                    "district": structured_input.get("district"),
                    "block": structured_input.get("block"),
                    "village": structured_input.get("village"),
                },
                business_type=structured_input.get("business_type"),
                scale=structured_input.get("scale", "micro"),
                project_cost=structured_input.get("project_cost"),
                capital_available=structured_input.get("capital_available"),
                annual_income=structured_input.get("annual_income"),
                age=structured_input.get("age"),
                beneficiary_category=structured_input.get("beneficiary_category"),
            )
        else:
            raise ValueError("Provide free_text, parsed, or structured_input")

    # When free text was parsed but the caller also supplied structured fields,
    # overlay them onto the parsed result so explicitly provided values are never
    # discarded (e.g. a capital figure the NLP parser could not infer).
    if structured_input and free_text:
        _overlay_structured(parsed, structured_input)

    # Step 2: Build beneficiary profile (with project_cost from template if not provided)
    profile = _build_beneficiary_profile(parsed)
    # If business_type is known but project_cost not given, derive from cost template for accurate scheme matching
    if parsed.business_type and not profile.project_cost:
        try:
            from app.engines.cost_templates import get_total_template_cost
            profile.project_cost = get_total_template_cost(parsed.business_type, parsed.scale or "micro")
        except Exception:
            pass

    # Step 3: Scheme eligibility
    eligibility = match_schemes(db, profile)

    # Step 4: Business recommendation (when no business_type given)
    suggested_businesses = []
    effective_business_type = parsed.business_type
    if not parsed.business_type:
        suggested_businesses = _recommend_businesses(db, parsed, profile)
        if suggested_businesses:
            effective_business_type = suggested_businesses[0]["business_type"]
            # Recompute eligibility for the top suggested business so financials/schemes are meaningful
            profile.business_type = effective_business_type
            try:
                eligibility = match_schemes(db, profile)
            except Exception:
                pass

    # Step 4b: Financial structure (use effective type)
    location_factor = _get_location_factor(parsed.location)
    financial = structure_financials(
        profile=profile,
        category_code=effective_business_type or "other",
        scale=parsed.scale or "micro",
        capital_available=parsed.capital_available or 0.0,
        eligible_schemes=eligibility,
        location_factor=location_factor,
        beneficiary_contribution_pct=None,
        preferred_scheme_code=None,
    )

    # Step 5: Profit model
    profit_model = None
    if effective_business_type:
        try:
            result = simulate_model(effective_business_type)
            profit_model = result.outputs
        except (ValueError, KeyError):
            pass

    # Step 6: Risks
    risks = _assess_risks(effective_business_type or "other", profit_model, financial)

    # Step 6b: Business-intelligence layer (deterministic, labelled ESTIMATED):
    # seasonal intelligence, product recommendations, monthly economics and
    # weather relevance for the report.
    from app.engines.business_intelligence import (
        monthly_economics,
        monthly_economics_to_dict,
        recommend_products,
        seasonal_intelligence,
    )
    biz_type = effective_business_type or "other"
    avg_revenue = (profit_model or {}).get("monthly_revenue")
    economics = monthly_economics(biz_type, monthly_revenue=avg_revenue, emi=financial.loan_structure.monthly_emi_after_moratorium)
    business_intelligence = {
        "seasonal": seasonal_intelligence(biz_type),
        "product_recommendations": recommend_products(biz_type),
        "monthly_economics": monthly_economics_to_dict(economics),
    }

    # Step 7: Action plan
    action_plan = _build_action_plan(parsed, eligibility, financial, profit_model)

    # Step 8: Documents
    documents = _build_documents_list(parsed, eligibility)

    # Step 9: Summary
    summary = _generate_summary(parsed, eligibility, financial, risks)

    return AdvisoryReport(
        parsed_input=parsed,
        beneficiary_profile=profile,
        scheme_eligibility=eligibility,
        financial_structure=financial,
        profit_model=profit_model,
        business_intelligence=business_intelligence,
        suggested_businesses=suggested_businesses,
        risks=risks,
        action_plan=action_plan,
        key_documents=documents,
        summary=summary,
    )


def report_to_dict(report: AdvisoryReport) -> dict:
    """Serialize full report to JSON-safe dict."""
    return {
        "parsed_input": nlp_to_dict(report.parsed_input) if report.parsed_input else None,
        "scheme_eligibility": [eligibility_to_dict(e) for e in report.scheme_eligibility],
        "financial_structure": financial_to_dict(report.financial_structure) if report.financial_structure else None,
        "profit_model": report.profit_model,
        "business_intelligence": report.business_intelligence,
        "suggested_businesses": report.suggested_businesses,
        "risks": report.risks,
        "action_plan": report.action_plan,
        "key_documents": report.key_documents,
        "summary": report.summary,
        "disclaimer": report.disclaimer,
    }
