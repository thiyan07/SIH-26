"""Working capital / survival analysis (Phase 5).

Uses existing cost/profit/repayment engines to estimate the minimum operating
buffer needed. All results are labelled as modelled business estimates.
"""
from __future__ import annotations


def working_capital_requirement(
    *,
    cost_breakdown: dict | None = None,
    monthly_economics: dict | None = None,
    repayment: dict | None = None,
    seasonal: dict | None = None,
    scale: str = "micro",
) -> dict:
    """Estimate working-capital / survival buffer.

    Components (all from deterministic engines):
        startup requirement (capex + infrastructure + licensing)
        + initial inventory (first batch / stock)
        + first-month operating costs (opex)
        + debt service (EMI for 1-2 months if loan exists)
        + seasonal/low-revenue buffer (seasonal buffer factor)

    Returns a dict with breakdown and a plain explanation.
    """
    # Extract from cost_breakdown (already computed by cost_templates).
    startup = 0.0
    initial_inventory = 0.0
    infra_lic = 0.0
    if cost_breakdown:
        capex = sum((cost_breakdown.get("capital_expenditure") or {}).values()) if isinstance(cost_breakdown.get("capital_expenditure"), dict) else 0
        wc_items = cost_breakdown.get("working_capital") or {}
        if isinstance(wc_items, dict):
            # First-month working capital items are the operating buffer proxy.
            initial_inventory = sum(v for k, v in wc_items.items() if "stock" in k.lower() or "inventory" in k.lower() or "feed" in k.lower() or "fabric" in k.lower() or "raw" in k.lower())
            if initial_inventory == 0:
                initial_inventory = sum(wc_items.values()) * 0.6  # heuristic: 60% of WC is inventory-like
        infra = cost_breakdown.get("infrastructure") or {}
        lic = cost_breakdown.get("licensing_compliance") or {}
        if isinstance(infra, dict):
            infra_lic += sum(infra.values())
        if isinstance(lic, dict):
            infra_lic += sum(lic.values())
        contingency = cost_breakdown.get("contingency_amount") or 0
        startup = capex + infra_lic + contingency

    # Opex + EMI from monthly economics / repayment.
    opex = 0.0
    emi = 0.0
    if monthly_economics:
        opex = float(monthly_economics.get("opex") or 0)
        emi = float(monthly_economics.get("emi") or 0)
    if repayment and emi == 0:
        emi = float(repayment.get("monthly_emi") or repayment.get("monthly_emi_effective") or 0)

    # Seasonal buffer: extra months of opex+emi to survive low season.
    buffer_factor = 1.0
    buffer_months = 1
    if seasonal:
        buffer_factor = float(seasonal.get("stock_buffer_factor") or 1.0)
        # High seasonal risk -> hold 2 months, medium -> 1.5, low ->1.
        risk = seasonal.get("cash_flow_risk")
        if risk == "HIGH":
            buffer_months = 2
        elif risk == "MEDIUM":
            buffer_months = 1
        else:
            buffer_months = 1
        # Apply factor to the buffer.
        buffer_factor = max(1.0, buffer_factor)

    # The survival estimate: startup + inventory + opex*buffer_months + emi*buffer_months + seasonal extra.
    # Seasonal extra is (buffer_factor -1) * opex as safety stock.
    seasonal_buffer = (buffer_factor - 1) * opex if buffer_factor > 1 else 0
    operating_buffer = (opex + emi) * buffer_months
    total_requirement = startup + initial_inventory + operating_buffer + seasonal_buffer
    # Minimum floor: at least 1 month opex+emi even if cost breakdown missing.
    if total_requirement < (opex + emi) * 1.5 and (opex + emi) > 0:
        total_requirement = (opex + emi) * 1.5

    # Explain why.
    reasons = []
    reasons.append(f"Startup (equipment/infra/licensing+contingency): ₹{startup:,.0f}")
    reasons.append(f"Initial inventory/stock: ₹{initial_inventory:,.0f}")
    reasons.append(f"First {buffer_months} month(s) operating costs: ₹{opex * buffer_months:,.0f}")
    if emi > 0:
        reasons.append(f"Debt service for {buffer_months} month(s): ₹{emi * buffer_months:,.0f}")
    if seasonal_buffer > 0:
        reasons.append(f"Seasonal buffer (stock factor {buffer_factor:.2f}x): ₹{seasonal_buffer:,.0f}")

    return {
        "estimated_working_capital_requirement": round(total_requirement, 2),
        "breakdown": {
            "startup_requirement": round(startup, 2),
            "initial_inventory": round(initial_inventory, 2),
            "operating_buffer": round(operating_buffer, 2),
            "seasonal_buffer": round(seasonal_buffer, 2),
            "buffer_months": buffer_months,
            "buffer_factor": round(buffer_factor, 2),
            "opex_per_month": round(opex, 2),
            "emi_per_month": round(emi, 2),
        },
        "explanation": "Estimated working-capital requirement covers initial setup, stock, and the cash needed to survive the first months including debt service and seasonal dips. This is a modelled business estimate, not an official requirement.",
        "reasons": reasons,
        "is_estimate": True,
        "disclaimer": "Modelled estimate based on category cost templates and operating assumptions. Verify against actual quotes.",
    }
