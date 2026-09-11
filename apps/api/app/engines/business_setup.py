"""Business Setup & Operating Plan — deterministic, category-aware.

Integrates existing engines (cost_templates, business_intelligence,
market_intelligence, finance, profit, repayment) without duplicating formulas.
All monetary values come from cost_templates / finance; LLM only explains.
"""
from __future__ import annotations

from typing import Optional

from app.engines.business_intelligence import (
    _OPERATING_DAYS,
    recommend_products,
)
from app.engines.cost_templates import get_cost_template, get_total_template_cost

# ── Business model abstraction (only where it materially changes cost/ops) ──
BUSINESS_MODELS: dict[str, list[dict]] = {
    "dairy": [
        {"code": "milk_production", "label": "Milk Production", "description": "Own animals, produce and sell milk"},
        {"code": "dairy_retail", "label": "Dairy Retail", "description": "Buy and resell milk/products (no animals)"},
    ],
    "restaurant": [
        {"code": "takeaway", "label": "Takeaway / Small Eatery", "description": "Limited seating, focus on parcel"},
        {"code": "dine_in", "label": "Dine-in", "description": "Seated service, larger area"},
    ],
    "grocery": [
        {"code": "village_shop", "label": "Village Shop", "description": "Very small, essentials only"},
        {"code": "retail_shop", "label": "Retail Shop", "description": "Larger assortment, branded goods"},
    ],
}

def available_models(category_code: str) -> list[dict]:
    return BUSINESS_MODELS.get(category_code, [{"code": "standard", "label": "Standard", "description": "Default operating model"}])

def resolve_model(category_code: str, requested: Optional[str]) -> str:
    models = available_models(category_code)
    codes = [m["code"] for m in models]
    if requested and requested in codes:
        return requested
    return codes[0]

# ── Priority classification helpers ──
def _classify_item(name: str, category: str, section: str) -> str:
    n = name.lower()
    # RECOMMENDED first — so billing/POS is not misclassified as OPTIONAL via
    # the broader optional pattern "pos system with inventory".
    recommended_keywords = ["billing", "pos", "refrigerator", "refrigeration", "signboard", "lighting", "painting", "overlock", "embroidery", "manure pit", "bore-well", "power backup", "inverter", "quality testing", "storage drums", "packaging machine", "shed with proper", "waste disposal", "cameras", "signage & menu"]
    if any(k in n for k in recommended_keywords):
        return "RECOMMENDED"
    # OPTIONAL patterns (checked after RECOMMENDED so POS billing is not removed in lean)
    optional_keywords = ["cctv", "generator", "branding", "display system", "packaging & branding", "e-commerce", "premium", "walk-in cooler (if", "cold storage unit", "delivery vehicle", "mannequin", "interior design", "decor", "security system", "factory license (if", "bis certification"]
    if any(k in n for k in optional_keywords):
        return "OPTIONAL"
    return "REQUIRED"

def _provenance_for(category: str, district: str | None = None, location_factor: float = 1.0) -> dict:
    if district and district.lower() == "erode" and location_factor != 1.0:
        return {"status": "ESTIMATED", "source": f"cost_templates (Erode district estimate, factor {location_factor}x)", "note": "District-adjusted estimate — verify with local quotes"}
    if location_factor != 1.0:
        return {"status": "ESTIMATED", "source": f"cost_templates (Tamil Nadu regional estimate, factor {location_factor}x)", "note": "Regional estimate — verify with local quotes"}
    return {"status": "ESTIMATED", "source": "cost_templates (Tamil Nadu state-level estimate)", "note": "State-level estimate — verify with local quotes"}

# ── Inventory / raw material categories per business ──
INVENTORY_PLAN: dict[str, list[dict]] = {
    "grocery": [
        {"category": "Staple foods", "items": "rice, wheat, pulses, oil, sugar", "priority": "HIGH", "seasonality": "Festival peaks"},
        {"category": "Daily essentials", "items": "salt, tea, soap, biscuits", "priority": "HIGH", "seasonality": "Year-round"},
        {"category": "Fast-moving", "items": "milk, bread, snacks", "priority": "HIGH", "seasonality": "Daily"},
        {"category": "Snacks & beverages", "items": "packaged snacks, cold drinks", "priority": "MEDIUM", "seasonality": "Summer"},
        {"category": "Personal care", "items": "shampoo, toothpaste", "priority": "MEDIUM", "seasonality": "Year-round"},
        {"category": "Specialty / slow-moving", "items": "premium branded goods", "priority": "LOW", "seasonality": "Limit initial allocation"},
    ],
    "dairy": [
        {"category": "Feed & fodder", "items": "green fodder, concentrate, mineral mix", "priority": "HIGH", "seasonality": "Year-round, price volatile"},
        {"category": "Milk handling", "items": "cans, strainers, cleaning supplies", "priority": "HIGH", "seasonality": "Daily"},
        {"category": "Veterinary buffer", "items": "basic medicines, deworming", "priority": "MEDIUM", "seasonality": "Preventive"},
    ],
    "textile": [
        {"category": "Core fabrics", "items": "cotton, lining, basic colours", "priority": "HIGH", "seasonality": "Wedding/festival peaks"},
        {"category": "Threads & consumables", "items": "threads, buttons, zippers", "priority": "HIGH", "seasonality": "Year-round"},
        {"category": "Trendy fabrics", "items": "premium / fashion fabrics", "priority": "LOW", "seasonality": "Limit until orders confirm"},
    ],
    "restaurant": [
        {"category": "Staple ingredients", "items": "rice, oil, onions, potatoes, spices", "priority": "HIGH", "seasonality": "Daily"},
        {"category": "Perishables", "items": "vegetables, milk, paneer", "priority": "HIGH", "seasonality": "Buy short, reduce waste"},
        {"category": "Packaging", "items": "parcel boxes, bags", "priority": "MEDIUM", "seasonality": "Takeaway heavy"},
    ],
    "food_processing": [
        {"category": "Raw materials", "items": "grains/pulses/oilseeds per product", "priority": "HIGH", "seasonality": "Harvest-linked"},
        {"category": "Packaging", "items": "pouches, labels, seals", "priority": "HIGH", "seasonality": "Year-round"},
        {"category": "Storage", "items": "containers, drums", "priority": "MEDIUM", "seasonality": "Buffer harvest"},
    ],
}

# ── KPIs per category ──
KPI_DEFS: dict[str, list[dict]] = {
    "grocery": [
        {"kpi": "Daily sales", "unit": "₹/day", "why": "Core revenue signal"},
        {"kpi": "Gross margin", "unit": "%", "why": "Pricing vs input cost"},
        {"kpi": "Inventory turnover", "unit": "x/month", "why": "Stock efficiency"},
        {"kpi": "Stock-outs", "unit": "count/week", "why": "Lost sales"},
        {"kpi": "Slow-moving stock", "unit": "₹ tied up", "why": "Cash lock-in"},
    ],
    "dairy": [
        {"kpi": "Litres/day", "unit": "L/day", "why": "Yield"},
        {"kpi": "Feed cost", "unit": "₹/L", "why": "Main cost driver"},
        {"kpi": "Milk yield per animal", "unit": "L/animal/day", "why": "Productivity"},
        {"kpi": "Animal health events", "unit": "count/month", "why": "Risk"},
    ],
    "textile": [
        {"kpi": "Orders/week", "unit": "orders", "why": "Demand"},
        {"kpi": "Average order value", "unit": "₹", "why": "Ticket size"},
        {"kpi": "Turnaround time", "unit": "days", "why": "Service quality"},
        {"kpi": "Material cost %", "unit": "%", "why": "Margin control"},
    ],
    "restaurant": [
        {"kpi": "Daily customers", "unit": "count", "why": "Footfall"},
        {"kpi": "Average order value", "unit": "₹", "why": "Revenue per customer"},
        {"kpi": "Food cost %", "unit": "%", "why": "COGS control"},
        {"kpi": "Waste", "unit": "₹/day", "why": "Loss"},
    ],
    "food_processing": [
        {"kpi": "Output/day", "unit": "kg/day", "why": "Throughput"},
        {"kpi": "Raw material cost %", "unit": "%", "why": "Margin"},
        {"kpi": "Packaging cost", "unit": "₹/unit", "why": "Unit economics"},
        {"kpi": "Dispatches/week", "unit": "count", "why": "Sales velocity"},
    ],
}

DEFAULT_KPIS = [
    {"kpi": "Daily revenue", "unit": "₹/day", "why": "Top-line"},
    {"kpi": "Operating profit", "unit": "₹/month", "why": "Viability"},
    {"kpi": "Cash remaining after EMI", "unit": "₹/month", "why": "Survival"},
]

# ── Sourcing needs per category ──
SOURCING_NEEDS: dict[str, list[dict]] = {
    "grocery": [{"need": "Wholesale inventory", "type": "Wholesaler / mandi", "location": "Nearest wholesale market"}],
    "dairy": [{"need": "Feed & fodder", "type": "Feed supplier / cooperative", "location": "Local"}, {"need": "Veterinary", "type": "Vet / para-vet", "location": "Block level"}],
    "textile": [{"need": "Fabric", "type": "Fabric trader / mill agent", "location": "Nearest textile market"}],
    "restaurant": [{"need": "Vegetables & staples", "type": "Mandi / wholesale", "location": "Daily supply"}, {"need": "Gas", "type": "LPG distributor", "location": "Local"}],
    "food_processing": [{"need": "Raw material", "type": "Farmer / mandi / APMC", "location": "Harvest-linked"}],
}

def build_setup_plan(
    category_code: str,
    scale: str = "micro",
    model: Optional[str] = None,
    location_factor: float = 1.0,
    capital_available: float = 0,
    monthly_economics_dict: Optional[dict] = None,
    financial_plan: Optional[dict] = None,
    seasonal: Optional[dict] = None,
    infrastructure: Optional[dict] = None,
    market_evidence: Optional[dict] = None,
    district: str | None = None,
) -> dict:
    model_code = resolve_model(category_code, model)
    template = get_cost_template(category_code, scale)
    total = get_total_template_cost(category_code, scale, location_factor)

    # Build enriched items list
    items: list[dict] = []
    startup_cost = 0.0
    initial_inventory = 0.0
    working_capital = 0.0
    recurring_monthly = 0.0

    for section in ("capital_expenditure", "infrastructure", "licensing_compliance"):
        for it in template.get(section, []):
            cost = round(it["amount"] * location_factor, 2)
            priority = _classify_item(it["name"], category_code, section)
            status = priority  # REQUIRED/RECOMMENDED/OPTIONAL
            prov = _provenance_for(category_code, district=district, location_factor=location_factor)
            items.append({
                "name": it["name"],
                "category": section,
                "priority": priority,
                "status": status,
                "estimated_cost": cost,
                "recurring": False,
                "quantity_or_unit": it["unit"],
                "rationale": f"{section.replace('_',' ')} for {model_code}" if model_code != "standard" else f"{section.replace('_',' ')}",
                "provenance": prov,
            })
            startup_cost += cost

    for it in template.get("working_capital", []):
        cost = round(it["amount"] * location_factor, 2)
        # working capital items are recurring monthly
        name_lower = it["name"].lower()
        is_inventory = any(k in name_lower for k in ["stock", "inventory", "feed", "fabric", "raw", "replenishment"])
        priority = "REQUIRED" if is_inventory or "rent" in name_lower or "labour" in name_lower else "RECOMMENDED"
        prov = _provenance_for(category_code, district=district, location_factor=location_factor)
        items.append({
            "name": it["name"],
            "category": "working_capital",
            "priority": priority,
            "status": priority,
            "estimated_cost": cost,
            "recurring": True,
            "quantity_or_unit": it["unit"],
            "rationale": "Monthly operating need",
            "provenance": prov,
        })
        working_capital += cost
        if is_inventory:
            initial_inventory += cost
        recurring_monthly += cost

    contingency = round(total - (startup_cost + working_capital), 2)
    if contingency < 0:
        contingency = round(template.get("contingency_pct", 10) / 100 * (startup_cost + working_capital), 2)

    # Total initial requirement = startup + initial_inventory + working_capital buffer (first month) + contingency
    # But cost_templates total already = startup+working_capital+contingency. We expose breakdown as required.
    total_initial = round(total, 2)

    # Lean option when capital < total
    lean: Optional[dict] = None
    if capital_available and capital_available < total_initial:
        # Remove OPTIONAL items fully, reduce RECOMMENDED by 50%, reduce initial inventory by 30% where possible
        lean_startup = 0
        lean_inventory = 0
        lean_wc = 0
        removed: list[str] = []
        for it in items:
            if it["status"] == "OPTIONAL":
                removed.append(it["name"])
                continue
            cost = it["estimated_cost"]
            if it["status"] == "RECOMMENDED" and not it["recurring"]:
                cost = round(cost * 0.5, 2)
            if it["category"] == "working_capital" and any(k in it["name"].lower() for k in ["stock", "inventory", "feed", "fabric", "raw"]):
                cost = round(cost * 0.7, 2)
            if it["category"] in ("capital_expenditure", "infrastructure", "licensing_compliance"):
                lean_startup += cost
            else:
                lean_wc += cost
                if any(k in it["name"].lower() for k in ["stock", "inventory", "feed", "fabric", "raw"]):
                    lean_inventory += cost
        lean_contingency = round((lean_startup + lean_wc) * template.get("contingency_pct", 10) / 100, 2)
        lean_total = round(lean_startup + lean_wc + lean_contingency, 2)
        # Only recommend lean if it materially reduces and still viable (not removing required core)
        if lean_total < total_initial and lean_total > lean_startup:
            lean_gap = max(0, lean_total - capital_available)
            lean = {
                "lean_total": lean_total,
                "lean_startup": round(lean_startup, 2),
                "lean_inventory": round(lean_inventory, 2),
                "lean_working_capital": round(lean_wc, 2),
                "lean_contingency": lean_contingency,
                "financing_needed": round(lean_gap, 2),
                "removed_or_reduced": removed[:5],
                "note": "Lean start removes optional items, halves recommended one-time costs, and trims initial inventory by 30%. Verify still operable locally.",
                "is_estimate": True,
            }

    # Monthly operating requirements derived from working_capital items
    monthly_reqs = []
    for it in template.get("working_capital", []):
        monthly_reqs.append({"name": it["name"], "estimated_cost": round(it["amount"]*location_factor,2), "unit": it["unit"], "provenance": _provenance_for(category_code, district=district, location_factor=location_factor)})

    # Operating targets: convert monthly revenue into daily/weekly
    operating_targets: dict = {}
    if monthly_economics_dict:
        rev = monthly_economics_dict.get("monthly_revenue") or monthly_economics_dict.get("monthly_revenue") or 0
        days = _OPERATING_DAYS.get(category_code, 26)
        daily = round(rev / days, 2) if days and rev else None
        be = monthly_economics_dict.get("break_even_revenue")
        be_daily = round(be / days, 2) if be and days else None
        operating_targets = {
            "monthly_revenue": rev,
            "operating_days": days,
            "daily_sales_needed": daily,
            "break_even_revenue": be,
            "break_even_daily": be_daily,
            "is_estimate": monthly_economics_dict.get("is_estimate", True),
            "note": "Targets are modelled estimates, not guarantees.",
        }
        # Category-specific unit
        if category_code == "restaurant":
            # approx customers = daily / avg bill (use 80 as baseline)
            avg_bill = 80
            operating_targets["daily_customers_needed"] = round(daily/avg_bill, 1) if daily else None
            operating_targets["avg_bill_assumption"] = avg_bill
        elif category_code == "textile":
            avg_order = 180
            operating_targets["orders_per_week"] = round(daily*7/avg_order, 1) if daily else None
        elif category_code == "dairy":
            operating_targets["litres_per_day_needed"] = round(daily/40, 1) if daily else None  # ₹40/L

    # Product mix: reuse recommend_products + seasonal
    product_mix = recommend_products(category_code)
    # Attach seasonality relevance
    for p in product_mix:
        p["seasonality"] = seasonal.get("current_label") if seasonal else None

    # Inventory plan
    inventory_plan = INVENTORY_PLAN.get(category_code, [{"category": "Core inventory", "items": "As per template", "priority": "HIGH", "seasonality": seasonal.get("current_label") if seasonal else "Year-round"}])

    # Risks: convert constraints/risk factors into actions (reuse category_profiles risk_factors if available)
    risks = []
    # Add seasonal risk if HIGH/MEDIUM
    if seasonal and seasonal.get("cash_flow_risk") in ("HIGH", "MEDIUM"):
        level = seasonal["cash_flow_risk"]
        risks.append({"risk": f"Seasonal demand ({level})", "level": level, "action": seasonal.get("inventory_implication") or "Maintain buffer stock", "provenance": "ESTIMATED"})

    # Sourcing needs
    sourcing = SOURCING_NEEDS.get(category_code, [{"need": "General supplies", "type": "Local market", "location": "Nearest market"}])
    # Mark as UNAVAILABLE if no real supplier data — extensible hook
    for s in sourcing:
        s["status"] = "UNAVAILABLE"
        s["evidence"] = "Supplier discovery can be connected when verified supplier data is available."
        s["provenance"] = "UNAVAILABLE"

    # Location-aware note
    location_note = "Location-specific evidence unavailable."
    if infrastructure:
        parts = []
        if infrastructure.get("nearest_market_km") is not None:
            parts.append(f"Nearest market {infrastructure['nearest_market_km']} km")
        if infrastructure.get("nearest_transport_km") is not None:
            parts.append(f"Transport {infrastructure['nearest_transport_km']} km")
        if parts:
            location_note = "; ".join(parts) + ". Factor transport / rent locally; no rent invented."
        # if exact location is used, surface it
        if infrastructure.get("nearest_market_km") is None and infrastructure.get("markets_nearby") == 0:
            location_note = "No market points within 20 km in available infrastructure data."

    # KPIs
    kpis = KPI_DEFS.get(category_code, DEFAULT_KPIS)

    # Plan vs actual foundation: store planned values for future comparison
    planned = {}
    if monthly_economics_dict:
        planned = {
            "planned_revenue": monthly_economics_dict.get("monthly_revenue"),
            "planned_cogs": monthly_economics_dict.get("cogs"),
            "planned_opex": monthly_economics_dict.get("opex"),
            "planned_gross_margin": monthly_economics_dict.get("gross_margin_pct"),
            "planned_operating_profit": monthly_economics_dict.get("operating_profit"),
            "planned_cash_surplus": monthly_economics_dict.get("cash_surplus"),
            "planned_break_even": monthly_economics_dict.get("break_even_revenue"),
        }
    if financial_plan:
        planned.update({
            "planned_project_cost": financial_plan.get("project_cost"),
            "planned_financing": financial_plan.get("required_financing"),
            "planned_loan": financial_plan.get("loan_amount"),
            "planned_emi": monthly_economics_dict.get("emi") if monthly_economics_dict else None,
        })
    # working capital planned
    planned["planned_working_capital"] = working_capital

    # Overall confidence: medium if market evidence exists, otherwise low (items are always ESTIMATED demo)
    if market_evidence and market_evidence.get("available"):
        confidence = "medium"
    elif any(it["provenance"]["status"] == "ESTIMATED" for it in items):
        confidence = "low"
    else:
        confidence = "low"

    return {
        "category_code": category_code,
        "model": model_code,
        "available_models": available_models(category_code),
        "scale": scale,
        "location_factor": location_factor,
        "items": items,
        "startup_cost": round(startup_cost, 2),
        "initial_inventory": round(initial_inventory, 2),
        "working_capital": round(working_capital, 2),
        "contingency": contingency,
        "contingency_pct": template.get("contingency_pct", 10),
        "total_initial_requirement": total_initial,
        "monthly_operating_requirements": monthly_reqs,
        "operating_targets": operating_targets,
        "inventory_plan": inventory_plan,
        "product_mix": product_mix,
        "risks": risks,
        "kpis": kpis,
        "planned_values": planned,
        "sourcing_needs": sourcing,
        "location_note": location_note,
        "lean_option": lean,
        "confidence": confidence,
        "data_status": "ESTIMATED",
        "provenance": "cost_templates + business_intelligence (ESTIMATED demo)",
        "version": 1,
        "assumptions": ["All costs are regional demo estimates; verify with local quotes.", "Inventory and working capital are first-month / first-cycle estimates."],
    }
