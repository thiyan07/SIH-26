"""Simple Loan Explainer — translates the financial engine's numbers into plain
language for a rural/semi-urban entrepreneur.

The financial engine (``derive_financial_plan`` + ``build_schedule``) remains
the single source of truth for every numeric value. This module makes NO
independent financial calculations: it consumes the already-computed loan
amount, rate, tenure, moratorium and the authoritative amortization schedule
and explains them.

Everything here is deterministic. The LLM/advisory layer may re-word the
plain-language strings, but can never change the numeric fields.
"""
from __future__ import annotations

from typing import Any, Optional


# Deterministic affordability thresholds (documented here and in tests).
# Based on the ratio of estimated monthly operating surplus remaining AFTER
# the loan payment to the loan payment itself, plus an absolute minimum.
#
#   surplus_after_payment = operating_profit - payment_amount
#
#   manageable   : surplus_after_payment >= payment  (leaves at least a full
#                  payment of headroom) OR no loan at all
#   pressure     : 0 <= surplus_after_payment < payment
#   difficult    : surplus_after_payment < 0  (business surplus cannot cover EMI)
#
# 90%/100% borders are intentionally avoided so a user is never nudged toward
# borrowing more than their actual funding gap.
AFFORDABLE_RATIO = 1.0


# Terminology dictionary: technical term -> simple human explanation.
# Keyed by language so the frontend can render the same pair everywhere.
TERMINOLOGY = {
    "principal": {
        "en": "The amount you borrowed.",
        "ta": "நீங்கள் கடன் வாங்கிய தொகை.",
        "hi": "आपने उधार ली गई राशि।",
    },
    "interest_rate": {
        "en": "Extra charge for borrowing the money.",
        "ta": "கடன் வாங்குவதற்கான கூடுதல் கட்டணம்.",
        "hi": "पैसा उधार लेने के लिए अतिरिक्त शुल्क।",
    },
    "emi": {
        "en": "Monthly payment.",
        "ta": "மாதாந்திர தவணை.",
        "hi": "मासिक किस्त।",
    },
    "tenure": {
        "en": "The time you have to repay the loan.",
        "ta": "கடனை திருப்பிச் செலுத்த உங்களுக்கு உள்ள காலம்.",
        "hi": "ऋण चुकाने के लिए आपके पास समय।",
    },
    "moratorium": {
        "en": "The initial period before regular repayment starts.",
        "ta": "வழக்கமான தவணை தொடங்குவதற்கு முந்தைய ஆரம்ப காலம்.",
        "hi": "नियमित भुगतान शुरू होने से पहले की प्रारंभिक अवधि।",
    },
    "outstanding_principal": {
        "en": "The loan amount still left to repay.",
        "ta": "இன்னும் திருப்பிச் செலுத்த வேண்டிய கடன் தொகை.",
        "hi": "अभी भी चुकाने को बाकी ऋण राशि।",
    },
    "total_interest": {
        "en": "Extra money paid for the loan.",
        "ta": "கடனுக்காக செலுத்தப்படும் கூடுதல் பணம்.",
        "hi": "ऋण के लिए चुकाया गया अतिरिक्त पैसा।",
    },
    "total_repayment": {
        "en": "Total money you will pay back.",
        "ta": "நீங்கள் திருப்பிச் செலுத்தும் மொத்த பணம்.",
        "hi": "आपके द्वारा चुकाई जाने वाली कुल राशि।",
    },
    "payment_frequency": {
        "en": "How often you make a payment.",
        "ta": "எத்தனை முறை தவணை செலுத்துகிறீர்கள்.",
        "hi": "आप कितनी बार भुगतान करते हैं।",
    },
}


def _inr(v: Optional[float]) -> Optional[float]:
    """Round a monetary value consistently with the engine."""
    return round(v, 2) if v is not None else None


def classify_affordability(
    operating_profit: Optional[float],
    payment_amount: float,
) -> dict:
    """Deterministic affordability classification.

    Thresholds (documented in the module docstring):
      manageable : surplus_after_payment >= payment_amount
      pressure   : 0 <= surplus_after_payment < payment_amount
      difficult  : surplus_after_payment < 0
    """
    op = float(operating_profit or 0.0)
    surplus = op - payment_amount
    if payment_amount <= 0:
        status = "manageable"
    elif surplus >= payment_amount:
        status = "manageable"
    elif surplus >= 0:
        status = "pressure"
    else:
        status = "difficult"
    return {
        "monthly_operating_profit": round(op, 2),
        "payment_amount": round(payment_amount, 2),
        "surplus_after_payment": round(surplus, 2),
        "status": status,
        "method": (
            "Deterministic: surplus_after_payment = operating_profit - payment. "
            "manageable if surplus >= payment; pressure if 0 <= surplus < payment; "
            "difficult if surplus < 0."
        ),
    }


def build_loan_explainer(
    financial_plan: dict,
    schedule: Any,
    monthly_economics: Optional[dict] = None,
) -> dict:
    """Build the structured, deterministic loan explanation.

    Args:
        financial_plan: the existing fin.plan dict (project_cost, own_contribution,
            required_financing, shortfall, loan_amount, scheme fields).
        schedule: a repayment.RepaymentSchedule (or None) already produced by
            the financial engine. Pass None when no loan is required.
        monthly_economics: the existing monthly economics dict (operating_profit,
            cash_surplus) for the affordability block.
    """
    project_cost = financial_plan.get("project_cost")
    own_contribution = financial_plan.get("own_contribution") or 0.0
    required_financing = financial_plan.get("required_financing") or 0.0
    loan_amount = financial_plan.get("loan_amount") or 0.0
    shortfall = financial_plan.get("shortfall") or 0.0
    max_loan = financial_plan.get("max_loan")
    interest_rate = financial_plan.get("interest_rate")
    tenure_years = financial_plan.get("tenure_years")
    moratorium_months = financial_plan.get("moratorium_months")
    moratorium_mode = financial_plan.get("moratorium_mode") or "interest_only_during_moratorium"
    scheme_name = financial_plan.get("scheme_name")
    scheme_code = financial_plan.get("scheme_code")
    is_estimated = bool(financial_plan.get("notes"))

    # No-loan condition: own capital covers the estimated project cost.
    no_loan_required = (project_cost is not None
                        and own_contribution is not None
                        and own_contribution >= project_cost)

    # ---- funding summary (always available, cost-driven) ----
    funding_summary = {
        "project_cost": _inr(project_cost),
        "own_capital": _inr(own_contribution),
        "required_financing": _inr(required_financing),
        "no_loan_required": bool(no_loan_required or required_financing <= 0),
        "shortfall": _inr(shortfall),
        "shortfall_reason": financial_plan.get("shortfall_reason"),
    }

    # ---- loan summary ----
    payment_frequency = "monthly"
    schedule_rows = []
    loan_summary = {
        "loan_amount": _inr(loan_amount),
        "interest_rate": interest_rate,
        "tenure_years": tenure_years,
        "tenure_months": int(round(tenure_years * 12)) if tenure_years is not None else None,
        "moratorium_months": moratorium_months,
        "moratorium_mode": moratorium_mode,
        "payment_frequency": payment_frequency,
        "scheme_code": scheme_code,
        "scheme_name": scheme_name,
        "max_loan_allowed": _inr(max_loan),
    }

    has_schedule = schedule is not None and loan_amount > 0
    if has_schedule and getattr(schedule, "months", None):
        mor_m = moratorium_months or 0
        for row in schedule.months:
            schedule_rows.append({
                "month": row.month,
                "payment": round(row.total_payment, 2),
                "interest": round(row.interest_payment, 2),
                "principal": round(row.principal_payment, 2),
                "balance": round(row.principal_outstanding, 2),
                "during_moratorium": row.month <= mor_m,
            })
        loan_summary["payment_amount"] = round(schedule.monthly_emi_effective, 2)
        loan_summary["payment_during_moratorium"] = round(
            schedule.monthly_emi_during_moratorium, 2)
        loan_summary["total_interest"] = round(schedule.total_interest, 2)
        loan_summary["total_repayment"] = round(schedule.total_repayment, 2)
        loan_summary["number_of_payments"] = len(schedule.months)

    # Moratorium treatment text: drives whether we say "you pay nothing" vs
    # "interest may accrue". Drawn from the actual mode chosen by the engine.
    moratorium_summary = None
    if (moratorium_months or 0) > 0:
        if moratorium_mode == "deferred_interest":
            treatment = (
                "No regular EMI during the initial period, but interest is added to "
                "your loan during this time."
            )
        elif moratorium_mode == "principal_deferred":
            treatment = (
                "You pay interest during the initial period; the loan amount itself "
                "is repaid only after it ends."
            )
        else:  # interest_only_during_moratorium (default)
            treatment = (
                "You pay only a small amount towards interest during the initial "
                "period; the loan amount itself is repaid only after it ends."
            )
        moratorium_summary = {
            "months": moratorium_months,
            "mode": moratorium_mode,
            "treatment": treatment,
        }

    # ---- repayment schedule + journey ----
    # The "first regular payment" is the first row where principal amortization
    # actually starts (i.e. the ongoing EMI after any moratorium). Interest-only
    # moratorium payments are recorded but not treated as the regular payment.
    first_payment_row = None
    last_payment_row = None
    first_moratorium_payment = None
    moratorium_start_payment = False
    if has_schedule and schedule_rows:
        regular = [r for r in schedule_rows if r["principal"] > 0]
        moratorium_rows = [r for r in schedule_rows if r["during_moratorium"]]
        active = regular or [r for r in schedule_rows if r["payment"] > 0]
        if moratorium_rows and moratorium_rows[0]["payment"] > 0:
            first_moratorium_payment = moratorium_rows[0]
            moratorium_start_payment = True
        if active:
            first_payment_row = active[0]
            last_payment_row = active[-1]

    repayment_schedule = {
        "available": has_schedule,
        "rows": schedule_rows[:60],  # cap display rows; totals still authoritative
        "month_count": len(schedule_rows),
        "first_payment_month": first_payment_row["month"] if first_payment_row else None,
        "last_payment_month": last_payment_row["month"] if last_payment_row else None,
        "first_payment_amount": round(first_payment_row["payment"], 2) if first_payment_row else None,
        "last_payment_amount": round(last_payment_row["payment"], 2) if last_payment_row else None,
        "first_regular_month": first_payment_row["month"] if first_payment_row else None,
        "first_regular_payment": round(first_payment_row["payment"], 2) if first_payment_row else None,
        "first_moratorium_payment": (
            round(first_moratorium_payment["payment"], 2) if first_moratorium_payment else None
        ),
        "moratorium_start_payment": moratorium_start_payment,
    }

    # ---- affordability (connect loan to business model) ----
    payment_amount = loan_summary.get("payment_amount", 0.0)
    operating_profit = None
    cash_surplus = None
    if monthly_economics:
        operating_profit = monthly_economics.get("operating_profit")
        cash_surplus = monthly_economics.get("cash_surplus")
    affordability = classify_affordability(operating_profit, payment_amount)
    affordability["monthly_operating_profit"] = round(float(operating_profit or 0.0), 2)
    affordability["cash_surplus_after_payment"] = _inr(cash_surplus)
    # Refine affordability using the engine's actual cash surplus (which already
    # subtracts EMI) when available, so the shown "money remaining" is canonical.
    if cash_surplus is not None:
        affordability["surplus_after_payment"] = round(float(cash_surplus), 2)

    # ---- safety warning (mirrors GO/MODIFY/AVOID) ----
    safety = None
    if payment_amount > 0 and affordability["surplus_after_payment"] < 0:
        safety = {
            "level": "warn",
            "business_surplus": round(float(operating_profit or 0.0), 2),
            "loan_payment": round(payment_amount, 2),
            "gap": round(abs(affordability["surplus_after_payment"]), 2),
        }
    elif payment_amount > 0 and 0 <= affordability["surplus_after_payment"] < payment_amount:
        safety = {
            "level": "caution",
            "business_surplus": round(float(operating_profit or 0.0), 2),
            "loan_payment": round(payment_amount, 2),
            "gap": round(payment_amount - affordability["surplus_after_payment"], 2),
        }

    return {
        "funding_summary": funding_summary,
        "loan_summary": loan_summary,
        "moratorium_summary": moratorium_summary,
        "repayment_schedule": repayment_schedule,
        "affordability": affordability,
        "safety": safety,
        "terminology": TERMINOLOGY,
        "data_status": _data_status(financial_plan, has_schedule, loan_amount),
    }


def _data_status(financial_plan: dict, has_schedule: bool, loan_amount: float) -> dict:
    is_estimated = bool(financial_plan.get("notes"))
    project_label = "ESTIMATED" if is_estimated else "REAL"
    emi_label = "ESTIMATED" if is_estimated else "CALCULATED"
    schedule_label = "ESTIMATED" if has_schedule else "UNAVAILABLE"
    return {
        "project_cost_status": project_label,
        "project_cost_label": (
            "Estimated business requirement" if is_estimated
            else "Verified business requirement"
        ),
        "emi_status": emi_label,
        "schedule_status": schedule_label,
        "schedule_note": (
            "Calculated estimate — confirm final schedule with lender."
            if has_schedule else
            "Exact lender repayment schedule is not available yet."
        ),
        "no_loan": loan_amount <= 0,
    }
