"""Deterministic SWOT, risk and report composition.

SWOT/risks are derived from evidence arrays (not invented), then optionally
run through the LLM for natural-language polish in the requested language.
"""
from __future__ import annotations

TRANSLATIONS = {
    "en": {
        "strengths": "Strengths",
        "weaknesses": "Weaknesses",
        "opportunities": "Opportunities",
        "threats": "Threats",
        "exec_summary": "Executive Summary",
        "limitations": "Limitations",
        "insufficient_evidence": "Evidence is insufficient for a definitive assessment.",
    },
    "ta": {
        "strengths": "பலம்",
        "weaknesses": "பலவீனங்கள்",
        "opportunities": "வாய்ப்புகள்",
        "threats": "அச்சுறுத்தல்கள்",
        "exec_summary": "சுருக்கம்",
        "limitations": "வரம்புகள்",
        "insufficient_evidence": "தீர்மானமான மதிப்பீட்டிற்கு ஆதாரம் போதுமானதாக இல்லை.",
    },
    "hi": {
        "strengths": "ताकत",
        "weaknesses": "कमजोरियाँ",
        "opportunities": "अवसर",
        "threats": "खतरे",
        "exec_summary": "कार्यकारी सारांश",
        "limitations": "सीमाएँ",
        "insufficient_evidence": "निश्चित मूल्यांकन के लिए साक्ष्य पर्याप्त नहीं हैं।",
    },
}


def build_swot(evidence: dict, language: str = "en") -> dict:
    """Derive SWOT from the deterministic evidence only."""
    t = TRANSLATIONS.get(language, TRANSLATIONS["en"])
    pop = evidence.get("population", {})
    comp = evidence.get("business_competition", {})
    infra = evidence.get("infrastructure", {})
    score = evidence.get("opportunity_score", {})

    strengths = []
    if infra.get("nearest_market_km") is not None and infra["nearest_market_km"] <= 10:
        strengths.append(f"Market accessible within {infra['nearest_market_km']} km")
    if (comp.get("mapped_competitors_5km") or 0) < 3:
        strengths.append("Few mapped competitors within 5 km")
    if pop.get("available"):
        strengths.append(f"Baseline population available (Census {pop.get('census_year')})")

    weaknesses = []
    if not pop.get("available"):
        weaknesses.append("Population data not available (Census baseline missing)")
    if pop.get("available") and pop.get("census_year") and pop["census_year"] < 2015:
        weaknesses.append("Demographic data is a historical Census baseline, not current")

    opportunities = []
    if score.get("demand_score") and score["demand_score"] >= 60:
        opportunities.append("Demand indicators are comparatively favourable")
    if infra.get("nearest_market_km") is not None and infra["nearest_market_km"] <= 10:
        opportunities.append("Proximity to market supports sales/distribution")

    threats = []
    if (comp.get("mapped_competitors_5km") or 0) >= 5:
        threats.append("Multiple mapped competitors within 5 km")
    if (score.get("risk_score") or 0) >= 60:
        threats.append("Elevated risk from competition/access factors")

    if not strengths:
        strengths.append(t["insufficient_evidence"])

    return {
        "strengths": strengths,
        "weaknesses": weaknesses,
        "opportunities": opportunities,
        "threats": threats,
        "labels": {k: t[k] for k in ("strengths", "weaknesses", "opportunities", "threats")},
    }


def build_risks(evidence: dict) -> list[dict]:
    risks = []
    comp = evidence.get("business_competition", {})
    record = comp.get("data_completeness", "medium")
    risks.append({
        "factor": "Data completeness",
        "level": record,
        "note": "OSM mapped business data may be incomplete; competitor counts are minimums.",
    })
    if comp.get("nearest_competitor_km") is not None and comp["nearest_competitor_km"] <= 1:
        risks.append({"factor": "Immediate competition", "level": "medium",
                      "note": f"Nearest mapped competitor within {comp['nearest_competitor_km']} km"})
    infra = evidence.get("infrastructure", {})
    if infra.get("nearest_market_km") is not None and infra["nearest_market_km"] > 15:
        risks.append({"factor": "Market distance", "level": "high",
                      "note": f"Nearest market is {infra['nearest_market_km']} km away"})
    profile = evidence.get("category_profile") or {}
    for rf in profile.get("risk_factors", []):
        risks.append({
            "factor": rf.get("factor", "Category risk"),
            "level": rf.get("level", "medium"),
            "note": rf.get("note", ""),
        })
    seasonality = profile.get("seasonality")
    if seasonality and seasonality.get("note"):
        risks.append({"factor": "Seasonality", "level": "medium", "note": seasonality["note"]})
    if not risks:
        risks.append({"factor": "Seasonality / supply chain", "level": "unknown",
                      "note": "Not assessed due to insufficient evidence."})
    return risks


def section_headers(language: str) -> dict:
    return TRANSLATIONS.get(language, TRANSLATIONS["en"])


def _inr(v) -> str:
    try:
        return f"₹{float(v):,.0f}"
    except (TypeError, ValueError):
        return "—"


def build_report(evidence: dict, language: str = "en") -> list[dict]:
    """Deterministic 14-section report (plan §23).

    Every quantitative statement is taken directly from `evidence`; missing
    fields are reported as unavailable, never invented. Returns a list of
    {section, items:[{label, value}], notes} blocks.
    """
    s = evidence.get("opportunity_score", {})
    fp = evidence.get("financial_plan", {})
    rep = evidence.get("repayment", {})
    pm = evidence.get("profit_model", {})
    comp = evidence.get("business_competition", {})
    pop = evidence.get("population", {})
    mr = (evidence.get("market") or {}).get("market_reach", {})
    infra = evidence.get("infrastructure", {})
    location = evidence.get("location", {})
    rec = evidence.get("recommendation", {})
    swot = build_swot(evidence, language)
    risks = build_risks(evidence)

    sections = [
        {
            "section": "Executive Summary",
            "items": [
                ("Location", f"{location.get('village') or location.get('block') or '—'}, "
                             f"{location.get('district')}, {location.get('state')}"),
                ("Opportunity (Prototype Index)", f"{s.get('overall_score')}/100"),
                ("Confidence", s.get("confidence_label")),
                ("Recommendation", rec.get("label")),
            ],
            "notes": [rec.get("reason")] if rec.get("reason") else [],
        },
        {
            "section": "Market Reach",
            "items": [
                ("Population baseline (Census 2011)", pop.get("population") if pop.get("available") else "Unavailable (historical only)"),
                ("Households", mr.get("households") or pop.get("households")),
                ("Nearest market (km)", mr.get("market_accessibility", {}).get("nearest_market_km") or infra.get("nearest_market_km")),
                ("Nearest transport (km)", mr.get("market_accessibility", {}).get("nearest_transport_km") or infra.get("nearest_transport_km")),
            ],
            "notes": ["Population is the historical Census baseline, not current population."],
        },
        {
            "section": "Competition",
            "items": [
                ("Mapped competitors (5 km)", comp.get("mapped_competitors_5km")),
                ("Mapped competitors (10 km)", comp.get("mapped_competitors_10km")),
                ("Nearest competitor (km)", comp.get("nearest_competitor_km")),
                ("Data completeness", comp.get("data_completeness")),
            ],
            "notes": ["Mapped business data may be incomplete; counts are minimums."],
        },
        {
            "section": "Opportunity",
            "items": [
                ("Demand", s.get("demand_score")),
                ("Competition advantage", s.get("competition_score")),
                ("Accessibility", s.get("accessibility_score")),
                ("Price/Margin", s.get("price_score")),
                ("Financial fit", s.get("financial_fit_score")),
                ("Risk", s.get("risk_score")),
            ],
            "notes": ["Prototype Opportunity Index — an analytical estimate, not a success probability."],
        },
        {
            "section": "SWOT",
            "items": [
                ("Strengths", " · ".join(swot.get("strengths", []) or ["None recorded"])),
                ("Weaknesses", " · ".join(swot.get("weaknesses", []) or ["None recorded"])),
                ("Opportunities", " · ".join(swot.get("opportunities", []) or ["None recorded"])),
                ("Threats", " · ".join(swot.get("threats", []) or ["None recorded"])),
            ],
            "notes": [],
        },
        {
            "section": "Risks",
            "items": [(r.get("factor"), f"{r.get('level')} — {r.get('note')}") for r in risks],
            "notes": [],
        },
        {
            "section": "Pricing",
            "items": [
                ("Verified local price data", "Available" if evidence.get("prices") else "Unavailable"),
            ],
            "notes": ["No invented local prices. Where unavailable, the entrepreneur may enter a manual price."],
        },
        {
            "section": "Business Economics",
            "items": [
                ("Monthly revenue", _inr((pm.get("outputs") or {}).get("monthly_revenue"))),
                ("Monthly operating cost", _inr((pm.get("outputs") or {}).get("monthly_operating_cost"))),
                ("Estimated operating profit", _inr((pm.get("outputs") or {}).get("estimated_monthly_operating_profit"))),
                ("Operating margin (%)", (pm.get("outputs") or {}).get("operating_margin_pct")),
            ],
            "notes": pm.get("notes", []) or ["Estimated operating model; not actual accounts."],
        },
        {
            "section": "Financial Structure",
            "items": [
                ("Capital available", _inr(fp.get("capital_available"))),
                ("Project cost", _inr(fp.get("project_cost"))),
                ("Loan amount", _inr(fp.get("loan_amount"))),
                ("Margin (%)", fp.get("margin_pct")),
            ],
            "notes": [],
        },
        {
            "section": "Scheme",
            "items": [
                ("Scheme", fp.get("scheme_name") or "None"),
                ("Interest rate", f"{fp.get('interest_rate')}%" if fp.get("interest_rate") is not None else "—"),
                ("Tenure", f"{fp.get('tenure_years')} yr" if fp.get("tenure_years") else "—"),
                ("Moratorium", f"{fp.get('moratorium_months')} mo" if fp.get("moratorium_months") else "—"),
                ("Reference", fp.get("source_document") or "Problem-statement demo parameters"),
            ],
            "notes": ["Scheme parameters are problem-statement demo values; verify with the agency."],
        },
        {
            "section": "Repayment",
            "items": [
                ("Monthly EMI (est.)", _inr(rep.get("monthly_emi"))),
                ("Repayment health", rep.get("health_label")),
                ("Coverage ratio", rep.get("coverage_ratio")),
            ],
            "notes": [rep.get("disclaimer")] if rep.get("disclaimer") else [],
        },
        {
            "section": "Working Capital",
            "items": [
                ("Available", "Not separately modelled from evidence"),
            ],
            "notes": ["Working capital is part of the operating cost estimate; refine with user inputs."],
        },
        {
            "section": "Data Sources",
            "items": [(d.get("name") or d.get("source") or "—",
                       f"ref {d.get('reference_year') or d.get('reference') or '—'} · confidence {d.get('confidence') or '—'}")
                      for d in evidence.get("data_sources", [])],
            "notes": [],
        },
        {
            "section": "Limitations",
            "items": [
                ("Census baseline", "Population is the 2011 Census, not current 2026 data."),
                ("OSM coverage", "Business counts are mapped minimums and may be incomplete."),
                ("Prices", "Local prices are only shown if sourced; otherwise unavailable."),
            ],
            "notes": ["Distinction: FACT vs ESTIMATE vs USER INPUT vs DEMO DATA vs AI INTERPRETATION is preserved."],
        },
    ]
    return sections
