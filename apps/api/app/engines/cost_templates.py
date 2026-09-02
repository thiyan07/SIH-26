"""Business cost templates for CAPEX/WC/infrastructure/licensing breakdowns.

Each category has cost templates at three scales: micro, small, medium.
All values are Indian Rupees and represent realistic Erode-district estimates.

These are demo estimates for advisory purposes — never guaranteed costs.
"""
from __future__ import annotations

from typing import Optional


# ──────────────────────────────────────────────────────────────────────
# Template structure:
# {
#   "capital_expenditure": [{"name": "...", "amount": float, "unit": "..."}],
#   "working_capital":     [{"name": "...", "amount": float, "unit": "..."}],
#   "infrastructure":      [{"name": "...", "amount": float, "unit": "..."}],
#   "licensing_compliance":[{"name": "...", "amount": float, "unit": "..."}],
#   "contingency_pct":     float,
# }
# ──────────────────────────────────────────────────────────────────────

TEMPLATES = {
    # ── DAIRY ────────────────────────────────────────────────────────
    "dairy": {
        "micro": {
            "capital_expenditure": [
                {"name": "Milking equipment (hand/manual)", "amount": 15000, "unit": "one-time"},
                {"name": "Milk cans & utensils", "amount": 5000, "unit": "one-time"},
                {"name": "Initial animal purchase (2 cows/buffaloes)", "amount": 80000, "unit": "per head"},
                {"name": "Animal shed basics (tarpaulin/ply)", "amount": 10000, "unit": "one-time"},
                {"name": "Cooling/refrigeration (small fridge)", "amount": 12000, "unit": "one-time"},
            ],
            "working_capital": [
                {"name": "Fodder & feed (1 month)", "amount": 8000, "unit": "/month"},
                {"name": "Veterinary care reserve (1 month)", "amount": 1500, "unit": "/month"},
                {"name": "Transportation (milk collection/delivery)", "amount": 3000, "unit": "/month"},
                {"name": "Labour (1 helper)", "amount": 4000, "unit": "/month"},
                {"name": "Electricity & misc", "amount": 2000, "unit": "/month"},
            ],
            "infrastructure": [
                {"name": "Shed flooring & fencing", "amount": 8000, "unit": "one-time"},
                {"name": "Water supply connection", "amount": 3000, "unit": "one-time"},
            ],
            "licensing_compliance": [
                {"name": "FSSAI basic registration", "amount": 1000, "unit": "one-time"},
                {"name": "Shop & Establishment license", "amount": 500, "unit": "one-time"},
                {"name": "Udyam/MSME registration", "amount": 0, "unit": "free"},
            ],
            "contingency_pct": 10.0,
        },
        "small": {
            "capital_expenditure": [
                {"name": "Milking machine (electric)", "amount": 35000, "unit": "one-time"},
                {"name": "Milk cans, coolers, utensils", "amount": 15000, "unit": "one-time"},
                {"name": "Initial animal purchase (5 cows)", "amount": 200000, "unit": "per head"},
                {"name": "Animal shed construction", "amount": 40000, "unit": "one-time"},
                {"name": "Bulk milk cooler", "amount": 25000, "unit": "one-time"},
            ],
            "working_capital": [
                {"name": "Fodder & feed (1 month)", "amount": 20000, "unit": "/month"},
                {"name": "Veterinary care reserve (1 month)", "amount": 3000, "unit": "/month"},
                {"name": "Transportation (1 mini-van share)", "amount": 8000, "unit": "/month"},
                {"name": "Labour (2 helpers)", "amount": 10000, "unit": "/month"},
                {"name": "Electricity & misc", "amount": 4000, "unit": "/month"},
            ],
            "infrastructure": [
                {"name": "Shed with concrete floor & roof", "amount": 25000, "unit": "one-time"},
                {"name": "Bore-well / water supply", "amount": 10000, "unit": "one-time"},
                {"name": "Manure pit", "amount": 5000, "unit": "one-time"},
            ],
            "licensing_compliance": [
                {"name": "FSSAI state license", "amount": 2000, "unit": "one-time"},
                {"name": "Shop & Establishment license", "amount": 500, "unit": "one-time"},
                {"name": "Trade license", "amount": 500, "unit": "one-time"},
            ],
            "contingency_pct": 10.0,
        },
        "medium": {
            "capital_expenditure": [
                {"name": "Automated milking system", "amount": 80000, "unit": "one-time"},
                {"name": "Bulk milk cooler (500L)", "amount": 60000, "unit": "one-time"},
                {"name": "Initial animal purchase (10 cows)", "amount": 400000, "unit": "per head"},
                {"name": "Shed with roofing & drainage", "amount": 80000, "unit": "one-time"},
                {"name": "Delivery vehicle", "amount": 50000, "unit": "one-time"},
            ],
            "working_capital": [
                {"name": "Fodder & feed (1 month)", "amount": 40000, "unit": "/month"},
                {"name": "Veterinary care (1 month)", "amount": 5000, "unit": "/month"},
                {"name": "Transportation & logistics", "amount": 15000, "unit": "/month"},
                {"name": "Labour (4 staff)", "amount": 24000, "unit": "/month"},
                {"name": "Electricity & misc", "amount": 8000, "unit": "/month"},
            ],
            "infrastructure": [
                {"name": "Full shed with silos", "amount": 60000, "unit": "one-time"},
                {"name": "Water supply + storage tank", "amount": 20000, "unit": "one-time"},
                {"name": "Manure/biogas setup", "amount": 15000, "unit": "one-time"},
            ],
            "licensing_compliance": [
                {"name": "FSSAI central license", "amount": 5000, "unit": "one-time"},
                {"name": "Pollution board NOC", "amount": 3000, "unit": "one-time"},
                {"name": "Trade license + fire NOC", "amount": 2000, "unit": "one-time"},
            ],
            "contingency_pct": 10.0,
        },
    },

    # ── POULTRY ──────────────────────────────────────────────────────
    "poultry": {
        "micro": {
            "capital_expenditure": [
                {"name": "Chick purchase (200 birds)", "amount": 10000, "unit": "batch"},
                {"name": "Feeders & drinkers", "amount": 3000, "unit": "one-time"},
                {"name": "Brooder setup (heat lamp, guard)", "amount": 2000, "unit": "one-time"},
                {"name": "Basic coop/shed material", "amount": 8000, "unit": "one-time"},
            ],
            "working_capital": [
                {"name": "Poultry feed (1 batch cycle ~6 weeks)", "amount": 12000, "unit": "/cycle"},
                {"name": "Vaccination & medicine", "amount": 2000, "unit": "/cycle"},
                {"name": "Labour", "amount": 3000, "unit": "/cycle"},
                {"name": "Utilities", "amount": 1000, "unit": "/cycle"},
            ],
            "infrastructure": [
                {"name": "Coop flooring & fencing", "amount": 5000, "unit": "one-time"},
            ],
            "licensing_compliance": [
                {"name": "Poultry farm registration", "amount": 500, "unit": "one-time"},
                {"name": "Udyam/MSME registration", "amount": 0, "unit": "free"},
            ],
            "contingency_pct": 8.0,
        },
        "small": {
            "capital_expenditure": [
                {"name": "Chick purchase (500 birds)", "amount": 25000, "unit": "batch"},
                {"name": "Feeders, drinkers, perches", "amount": 8000, "unit": "one-time"},
                {"name": "Automated waterer", "amount": 5000, "unit": "one-time"},
                {"name": "Shed construction (tinned roof)", "amount": 25000, "unit": "one-time"},
            ],
            "working_capital": [
                {"name": "Poultry feed (1 cycle)", "amount": 30000, "unit": "/cycle"},
                {"name": "Vaccination & medicine", "amount": 5000, "unit": "/cycle"},
                {"name": "Labour (1 helper)", "amount": 5000, "unit": "/cycle"},
                {"name": "Electricity & water", "amount": 2000, "unit": "/cycle"},
            ],
            "infrastructure": [
                {"name": "Shed with proper ventilation", "amount": 15000, "unit": "one-time"},
                {"name": "Waste disposal pit", "amount": 3000, "unit": "one-time"},
            ],
            "licensing_compliance": [
                {"name": "Poultry farm license", "amount": 1000, "unit": "one-time"},
                {"name": "Trade license", "amount": 500, "unit": "one-time"},
            ],
            "contingency_pct": 8.0,
        },
        "medium": {
            "capital_expenditure": [
                {"name": "Chick purchase (2000 birds)", "amount": 100000, "unit": "batch"},
                {"name": "Automated feeders & drinkers", "amount": 30000, "unit": "one-time"},
                {"name": "Ventilation fans (10 units)", "amount": 25000, "unit": "one-time"},
                {"name": "Shed construction (500 sq ft)", "amount": 60000, "unit": "one-time"},
                {"name": "Egg tray collector", "amount": 8000, "unit": "one-time"},
            ],
            "working_capital": [
                {"name": "Poultry feed (1 cycle)", "amount": 120000, "unit": "/cycle"},
                {"name": "Vaccination & medicine", "amount": 15000, "unit": "/cycle"},
                {"name": "Labour (3 workers)", "amount": 18000, "unit": "/cycle"},
                {"name": "Electricity & water", "amount": 6000, "unit": "/cycle"},
                {"name": "Transportation", "amount": 5000, "unit": "/cycle"},
            ],
            "infrastructure": [
                {"name": "Shed with automated systems", "amount": 40000, "unit": "one-time"},
                {"name": "Waste management system", "amount": 10000, "unit": "one-time"},
                {"name": "Cold storage unit", "amount": 20000, "unit": "one-time"},
            ],
            "licensing_compliance": [
                {"name": "FSSAI registration (if selling eggs)", "amount": 2000, "unit": "one-time"},
                {"name": "Pollution NOC", "amount": 3000, "unit": "one-time"},
                {"name": "Trade license", "amount": 1000, "unit": "one-time"},
            ],
            "contingency_pct": 8.0,
        },
    },

    # ── GROCERY / RETAIL ─────────────────────────────────────────────
    "grocery": {
        "micro": {
            "capital_expenditure": [
                {"name": "Shop racks & shelves", "amount": 8000, "unit": "one-time"},
                {"name": "Counter & cash box", "amount": 3000, "unit": "one-time"},
                {"name": "Initial stock purchase", "amount": 30000, "unit": "one-time"},
                {"name": "Weighing scale", "amount": 2000, "unit": "one-time"},
                {"name": "Signboard", "amount": 1500, "unit": "one-time"},
            ],
            "working_capital": [
                {"name": "Stock replenishment (1 month)", "amount": 25000, "unit": "/month"},
                {"name": "Rent", "amount": 3000, "unit": "/month"},
                {"name": "Electricity", "amount": 800, "unit": "/month"},
                {"name": "Labour (self + 1 helper)", "amount": 4000, "unit": "/month"},
            ],
            "infrastructure": [
                {"name": "Shop painting & minor repairs", "amount": 3000, "unit": "one-time"},
                {"name": "Lighting fixtures", "amount": 2000, "unit": "one-time"},
            ],
            "licensing_compliance": [
                {"name": "Shop & Establishment license", "amount": 500, "unit": "one-time"},
                {"name": "Trade license", "amount": 500, "unit": "one-time"},
                {"name": "Udyam registration", "amount": 0, "unit": "free"},
            ],
            "contingency_pct": 10.0,
        },
        "small": {
            "capital_expenditure": [
                {"name": "Shop racks, shelves, display units", "amount": 20000, "unit": "one-time"},
                {"name": "Billing system (POS + printer)", "amount": 15000, "unit": "one-time"},
                {"name": "Initial stock purchase", "amount": 80000, "unit": "one-time"},
                {"name": "Refrigerator (beverages)", "amount": 12000, "unit": "one-time"},
                {"name": "Signboard (backlit)", "amount": 5000, "unit": "one-time"},
            ],
            "working_capital": [
                {"name": "Stock replenishment (1 month)", "amount": 60000, "unit": "/month"},
                {"name": "Rent", "amount": 6000, "unit": "/month"},
                {"name": "Electricity & internet", "amount": 1500, "unit": "/month"},
                {"name": "Labour (2 staff)", "amount": 10000, "unit": "/month"},
            ],
            "infrastructure": [
                {"name": "Shop interior fit-out", "amount": 10000, "unit": "one-time"},
                {"name": "CCTV (2 cameras)", "amount": 5000, "unit": "one-time"},
            ],
            "licensing_compliance": [
                {"name": "Shop & Establishment license", "amount": 1000, "unit": "one-time"},
                {"name": "Trade license", "amount": 500, "unit": "one-time"},
                {"name": "FSSAI (if selling food items)", "amount": 1000, "unit": "one-time"},
            ],
            "contingency_pct": 10.0,
        },
        "medium": {
            "capital_expenditure": [
                {"name": "Complete shelving & display system", "amount": 50000, "unit": "one-time"},
                {"name": "POS system with inventory mgmt", "amount": 25000, "unit": "one-time"},
                {"name": "Initial stock (diverse)", "amount": 200000, "unit": "one-time"},
                {"name": "Walk-in cooler (if needed)", "amount": 40000, "unit": "one-time"},
                {"name": "Signage & branding", "amount": 15000, "unit": "one-time"},
            ],
            "working_capital": [
                {"name": "Stock replenishment (1 month)", "amount": 150000, "unit": "/month"},
                {"name": "Rent (larger space)", "amount": 12000, "unit": "/month"},
                {"name": "Electricity, internet, misc", "amount": 4000, "unit": "/month"},
                {"name": "Labour (4 staff)", "amount": 24000, "unit": "/month"},
            ],
            "infrastructure": [
                {"name": "Full interior fit-out", "amount": 30000, "unit": "one-time"},
                {"name": "CCTV + security system", "amount": 15000, "unit": "one-time"},
                {"name": "Generator backup", "amount": 20000, "unit": "one-time"},
            ],
            "licensing_compliance": [
                {"name": "Shop & Establishment license", "amount": 2000, "unit": "one-time"},
                {"name": "FSSAI state license", "amount": 2000, "unit": "one-time"},
                {"name": "Trade license + fire NOC", "amount": 2000, "unit": "one-time"},
            ],
            "contingency_pct": 10.0,
        },
    },

    # ── TEXTILE / TAILORING ──────────────────────────────────────────
    "textile": {
        "micro": {
            "capital_expenditure": [
                {"name": "Sewing machine (1)", "amount": 10000, "unit": "one-time"},
                {"name": "Cutting table & scissors", "amount": 3000, "unit": "one-time"},
                {"name": "Initial fabric & materials", "amount": 10000, "unit": "one-time"},
                {"name": "Measuring tools & accessories", "amount": 2000, "unit": "one-time"},
            ],
            "working_capital": [
                {"name": "Fabric & materials (1 month)", "amount": 8000, "unit": "/month"},
                {"name": "Thread, buttons, zippers", "amount": 2000, "unit": "/month"},
                {"name": "Electricity", "amount": 800, "unit": "/month"},
            ],
            "infrastructure": [
                {"name": "Shop setup (small room)", "amount": 5000, "unit": "one-time"},
            ],
            "licensing_compliance": [
                {"name": "Trade license", "amount": 500, "unit": "one-time"},
                {"name": "Udyam registration", "amount": 0, "unit": "free"},
            ],
            "contingency_pct": 8.0,
        },
        "small": {
            "capital_expenditure": [
                {"name": "Sewing machines (3 industrial)", "amount": 45000, "unit": "one-time"},
                {"name": "Overlock machine", "amount": 12000, "unit": "one-time"},
                {"name": "Cutting table & tools", "amount": 5000, "unit": "one-time"},
                {"name": "Initial fabric stock", "amount": 30000, "unit": "one-time"},
                {"name": "Mannequin & display", "amount": 3000, "unit": "one-time"},
            ],
            "working_capital": [
                {"name": "Fabric & materials (1 month)", "amount": 20000, "unit": "/month"},
                {"name": "Thread, accessories", "amount": 5000, "unit": "/month"},
                {"name": "Rent", "amount": 4000, "unit": "/month"},
                {"name": "Labour (2 tailors)", "amount": 12000, "unit": "/month"},
                {"name": "Electricity", "amount": 2000, "unit": "/month"},
            ],
            "infrastructure": [
                {"name": "Tailoring workshop setup", "amount": 10000, "unit": "one-time"},
                {"name": "Power backup (inverter)", "amount": 8000, "unit": "one-time"},
            ],
            "licensing_compliance": [
                {"name": "Trade license", "amount": 500, "unit": "one-time"},
                {"name": "GST registration (if > threshold)", "amount": 1000, "unit": "one-time"},
            ],
            "contingency_pct": 8.0,
        },
        "medium": {
            "capital_expenditure": [
                {"name": "Industrial sewing machines (8)", "amount": 120000, "unit": "one-time"},
                {"name": "Embroidery machine", "amount": 35000, "unit": "one-time"},
                {"name": "Cutting & pressing equipment", "amount": 20000, "unit": "one-time"},
                {"name": "Initial fabric inventory", "amount": 80000, "unit": "one-time"},
                {"name": "Display & packaging", "amount": 10000, "unit": "one-time"},
            ],
            "working_capital": [
                {"name": "Fabric & materials (1 month)", "amount": 50000, "unit": "/month"},
                {"name": "Thread, accessories, packaging", "amount": 10000, "unit": "/month"},
                {"name": "Rent (workshop + showroom)", "amount": 10000, "unit": "/month"},
                {"name": "Labour (5 tailors + 1 helper)", "amount": 35000, "unit": "/month"},
                {"name": "Electricity & misc", "amount": 5000, "unit": "/month"},
            ],
            "infrastructure": [
                {"name": "Workshop with proper layout", "amount": 25000, "unit": "one-time"},
                {"name": "Generator backup", "amount": 25000, "unit": "one-time"},
                {"name": "Showroom fit-out", "amount": 15000, "unit": "one-time"},
            ],
            "licensing_compliance": [
                {"name": "Trade license + fire NOC", "amount": 2000, "unit": "one-time"},
                {"name": "GST registration", "amount": 1500, "unit": "one-time"},
                {"name": "Pollution NOC (if dyeing)", "amount": 3000, "unit": "one-time"},
            ],
            "contingency_pct": 8.0,
        },
    },

    # ── FOOD PROCESSING ──────────────────────────────────────────────
    "food_processing": {
        "micro": {
            "capital_expenditure": [
                {"name": "Grinding/mixing machine", "amount": 15000, "unit": "one-time"},
                {"name": "Packaging equipment (sealer, bags)", "amount": 5000, "unit": "one-time"},
                {"name": "Storage containers", "amount": 3000, "unit": "one-time"},
                {"name": "Initial raw materials", "amount": 10000, "unit": "one-time"},
            ],
            "working_capital": [
                {"name": "Raw materials (1 month)", "amount": 15000, "unit": "/month"},
                {"name": "Packaging materials", "amount": 3000, "unit": "/month"},
                {"name": "Electricity", "amount": 2000, "unit": "/month"},
                {"name": "Labour (1 person)", "amount": 5000, "unit": "/month"},
                {"name": "Transportation", "amount": 2000, "unit": "/month"},
            ],
            "infrastructure": [
                {"name": "Processing room setup", "amount": 8000, "unit": "one-time"},
            ],
            "licensing_compliance": [
                {"name": "FSSAI basic registration", "amount": 1000, "unit": "one-time"},
                {"name": "Trade license", "amount": 500, "unit": "one-time"},
            ],
            "contingency_pct": 10.0,
        },
        "small": {
            "capital_expenditure": [
                {"name": "Processing machinery (multi-purpose)", "amount": 50000, "unit": "one-time"},
                {"name": "Packaging machine (semi-auto)", "amount": 20000, "unit": "one-time"},
                {"name": "Storage drums & racks", "amount": 10000, "unit": "one-time"},
                {"name": "Initial raw materials stock", "amount": 30000, "unit": "one-time"},
                {"name": "Quality testing kit", "amount": 8000, "unit": "one-time"},
            ],
            "working_capital": [
                {"name": "Raw materials (1 month)", "amount": 40000, "unit": "/month"},
                {"name": "Packaging materials", "amount": 8000, "unit": "/month"},
                {"name": "Rent", "amount": 5000, "unit": "/month"},
                {"name": "Labour (3 workers)", "amount": 15000, "unit": "/month"},
                {"name": "Electricity & fuel", "amount": 5000, "unit": "/month"},
                {"name": "Transportation & distribution", "amount": 5000, "unit": "/month"},
            ],
            "infrastructure": [
                {"name": "Processing unit with ventilation", "amount": 20000, "unit": "one-time"},
                {"name": "Wash area & drainage", "amount": 8000, "unit": "one-time"},
            ],
            "licensing_compliance": [
                {"name": "FSSAI state license", "amount": 2000, "unit": "one-time"},
                {"name": "Trade license", "amount": 1000, "unit": "one-time"},
                {"name": "Pollution NOC", "amount": 3000, "unit": "one-time"},
            ],
            "contingency_pct": 10.0,
        },
        "medium": {
            "capital_expenditure": [
                {"name": "Automated processing line", "amount": 150000, "unit": "one-time"},
                {"name": "Packaging machine (auto)", "amount": 50000, "unit": "one-time"},
                {"name": "Cold storage unit", "amount": 40000, "unit": "one-time"},
                {"name": "Quality lab equipment", "amount": 20000, "unit": "one-time"},
                {"name": "Initial raw materials", "amount": 80000, "unit": "one-time"},
            ],
            "working_capital": [
                {"name": "Raw materials (1 month)", "amount": 100000, "unit": "/month"},
                {"name": "Packaging & labels", "amount": 20000, "unit": "/month"},
                {"name": "Rent (industrial shed)", "amount": 15000, "unit": "/month"},
                {"name": "Labour (8 workers + 1 supervisor)", "amount": 50000, "unit": "/month"},
                {"name": "Utilities (power + water)", "amount": 12000, "unit": "/month"},
                {"name": "Distribution & logistics", "amount": 15000, "unit": "/month"},
            ],
            "infrastructure": [
                {"name": "Industrial shed with facilities", "amount": 60000, "unit": "one-time"},
                {"name": "Effluent treatment", "amount": 30000, "unit": "one-time"},
                {"name": "Generator backup", "amount": 30000, "unit": "one-time"},
            ],
            "licensing_compliance": [
                {"name": "FSSAI central license", "amount": 5000, "unit": "one-time"},
                {"name": "Pollution board consent", "amount": 5000, "unit": "one-time"},
                {"name": "GST registration", "amount": 1500, "unit": "one-time"},
                {"name": "BIS certification (if applicable)", "amount": 10000, "unit": "one-time"},
            ],
            "contingency_pct": 10.0,
        },
    },

    # ── RESTAURANT / FOOD SERVICE ────────────────────────────────────
    "restaurant": {
        "micro": {
            "capital_expenditure": [
                {"name": "Cooking equipment (stove, utensils)", "amount": 15000, "unit": "one-time"},
                {"name": "Tables & chairs (4 sets)", "amount": 8000, "unit": "one-time"},
                {"name": "Utensils & serving ware", "amount": 5000, "unit": "one-time"},
                {"name": "Gas connection & stove", "amount": 5000, "unit": "one-time"},
            ],
            "working_capital": [
                {"name": "Raw ingredients (1 month)", "amount": 15000, "unit": "/month"},
                {"name": "Gas & fuel", "amount": 3000, "unit": "/month"},
                {"name": "Rent (small shop)", "amount": 4000, "unit": "/month"},
                {"name": "Labour (1 helper)", "amount": 4000, "unit": "/month"},
                {"name": "Packaging (disposable)", "amount": 2000, "unit": "/month"},
            ],
            "infrastructure": [
                {"name": "Kitchen setup & ventilation", "amount": 10000, "unit": "one-time"},
                {"name": "Wash area", "amount": 3000, "unit": "one-time"},
            ],
            "licensing_compliance": [
                {"name": "FSSAI basic registration", "amount": 1000, "unit": "one-time"},
                {"name": "Shop & Establishment license", "amount": 500, "unit": "one-time"},
                {"name": "Fire NOC", "amount": 500, "unit": "one-time"},
            ],
            "contingency_pct": 10.0,
        },
        "small": {
            "capital_expenditure": [
                {"name": "Commercial kitchen equipment", "amount": 50000, "unit": "one-time"},
                {"name": "Furniture (10 tables)", "amount": 25000, "unit": "one-time"},
                {"name": "Refrigerator & freezer", "amount": 15000, "unit": "one-time"},
                {"name": "Utensils, crockery, cutlery", "amount": 10000, "unit": "one-time"},
                {"name": "Signage & menu board", "amount": 5000, "unit": "one-time"},
            ],
            "working_capital": [
                {"name": "Raw ingredients (1 month)", "amount": 40000, "unit": "/month"},
                {"name": "Gas & fuel", "amount": 6000, "unit": "/month"},
                {"name": "Rent", "amount": 8000, "unit": "/month"},
                {"name": "Labour (cook + 2 servers)", "amount": 18000, "unit": "/month"},
                {"name": "Utilities & misc", "amount": 3000, "unit": "/month"},
            ],
            "infrastructure": [
                {"name": "Kitchen with exhaust & ventilation", "amount": 20000, "unit": "one-time"},
                {"name": "Dining area setup", "amount": 10000, "unit": "one-time"},
            ],
            "licensing_compliance": [
                {"name": "FSSAI state license", "amount": 2000, "unit": "one-time"},
                {"name": "Shop & Establishment license", "amount": 1000, "unit": "one-time"},
                {"name": "Fire NOC", "amount": 1000, "unit": "one-time"},
                {"name": "Trade license", "amount": 500, "unit": "one-time"},
            ],
            "contingency_pct": 10.0,
        },
        "medium": {
            "capital_expenditure": [
                {"name": "Full commercial kitchen setup", "amount": 150000, "unit": "one-time"},
                {"name": "Furniture (20 covers)", "amount": 50000, "unit": "one-time"},
                {"name": "Walk-in cooler + freezer", "amount": 40000, "unit": "one-time"},
                {"name": "POS & billing system", "amount": 15000, "unit": "one-time"},
                {"name": "Interior design & decor", "amount": 30000, "unit": "one-time"},
            ],
            "working_capital": [
                {"name": "Raw ingredients (1 month)", "amount": 100000, "unit": "/month"},
                {"name": "Gas, fuel, utilities", "amount": 15000, "unit": "/month"},
                {"name": "Rent (larger space)", "amount": 15000, "unit": "/month"},
                {"name": "Staff (cook + 4 service)", "amount": 40000, "unit": "/month"},
                {"name": "Packaging & disposables", "amount": 5000, "unit": "/month"},
            ],
            "infrastructure": [
                {"name": "Kitchen with commercial exhaust", "amount": 40000, "unit": "one-time"},
                {"name": "Dining hall fit-out", "amount": 25000, "unit": "one-time"},
                {"name": "Generator backup", "amount": 25000, "unit": "one-time"},
            ],
            "licensing_compliance": [
                {"name": "FSSAI central license", "amount": 5000, "unit": "one-time"},
                {"name": "Shop & Establishment + Trade license", "amount": 2000, "unit": "one-time"},
                {"name": "Fire NOC + health license", "amount": 3000, "unit": "one-time"},
                {"name": "GST registration", "amount": 1500, "unit": "one-time"},
            ],
            "contingency_pct": 10.0,
        },
    },

    # ── AGRICULTURE ──────────────────────────────────────────────────
    "agriculture": {
        "micro": {
            "capital_expenditure": [
                {"name": "Seeds & saplings", "amount": 5000, "unit": "/season"},
                {"name": "Basic tools (hoe, rake, etc.)", "amount": 3000, "unit": "one-time"},
                {"name": "Drip irrigation starter kit", "amount": 8000, "unit": "one-time"},
            ],
            "working_capital": [
                {"name": "Fertilizers & pesticides (1 season)", "amount": 8000, "unit": "/season"},
                {"name": "Labour (seasonal)", "amount": 10000, "unit": "/season"},
                {"name": "Water/pump charges", "amount": 3000, "unit": "/season"},
                {"name": "Transportation to mandi", "amount": 2000, "unit": "/season"},
            ],
            "infrastructure": [
                {"name": "Small storage shed", "amount": 5000, "unit": "one-time"},
            ],
            "licensing_compliance": [
                {"name": "Land records (Pahani)", "amount": 200, "unit": "one-time"},
                {"name": "Aadhaar-linked farmer registration", "amount": 0, "unit": "free"},
            ],
            "contingency_pct": 8.0,
        },
        "small": {
            "capital_expenditure": [
                {"name": "Quality seeds & saplings", "amount": 15000, "unit": "/season"},
                {"name": "Tool kit (complete set)", "amount": 8000, "unit": "one-time"},
                {"name": "Drip/sprinkler irrigation system", "amount": 25000, "unit": "one-time"},
                {"name": "Small power tiller (shared)", "amount": 30000, "unit": "one-time"},
            ],
            "working_capital": [
                {"name": "Fertilizers & pesticides", "amount": 20000, "unit": "/season"},
                {"name": "Labour (2-3 workers, seasonal)", "amount": 30000, "unit": "/season"},
                {"name": "Water & pump charges", "amount": 8000, "unit": "/season"},
                {"name": "Transportation & mandi fees", "amount": 5000, "unit": "/season"},
            ],
            "infrastructure": [
                {"name": "Storage godown", "amount": 15000, "unit": "one-time"},
                {"name": "Pump & motor set", "amount": 12000, "unit": "one-time"},
            ],
            "licensing_compliance": [
                {"name": "Land records", "amount": 500, "unit": "one-time"},
                {"name": "Farmer registration", "amount": 0, "unit": "free"},
                {"name": "Crop insurance enrollment", "amount": 500, "unit": "/season"},
            ],
            "contingency_pct": 8.0,
        },
        "medium": {
            "capital_expenditure": [
                {"name": "Seeds, saplings, sapling nursery", "amount": 40000, "unit": "/season"},
                {"name": "Complete tool & equipment set", "amount": 20000, "unit": "one-time"},
                {"name": "Drip irrigation (full field)", "amount": 60000, "unit": "one-time"},
                {"name": "Tractor (shared/partial ownership)", "amount": 100000, "unit": "one-time"},
                {"name": "Sprayer equipment", "amount": 10000, "unit": "one-time"},
            ],
            "working_capital": [
                {"name": "Fertilizers, pesticides, micronutrients", "amount": 50000, "unit": "/season"},
                {"name": "Labour (5-8 workers)", "amount": 80000, "unit": "/season"},
                {"name": "Water, pump, electricity", "amount": 20000, "unit": "/season"},
                {"name": "Transportation & logistics", "amount": 15000, "unit": "/season"},
            ],
            "infrastructure": [
                {"name": "Storage godown (larger)", "amount": 30000, "unit": "one-time"},
                {"name": "Pump house + bore-well", "amount": 25000, "unit": "one-time"},
                {"name": "Protective fencing", "amount": 15000, "unit": "one-time"},
            ],
            "licensing_compliance": [
                {"name": "Land records & registration", "amount": 2000, "unit": "one-time"},
                {"name": "Farmer registration + soil test", "amount": 1000, "unit": "one-time"},
                {"name": "Crop insurance", "amount": 2000, "unit": "/season"},
            ],
            "contingency_pct": 8.0,
        },
    },

    # ── MANUFACTURING ────────────────────────────────────────────────
    "manufacturing": {
        "micro": {
            "capital_expenditure": [
                {"name": "Basic machinery (1 unit)", "amount": 30000, "unit": "one-time"},
                {"name": "Raw material stock", "amount": 15000, "unit": "one-time"},
                {"name": "Hand tools & accessories", "amount": 5000, "unit": "one-time"},
                {"name": "Safety equipment", "amount": 3000, "unit": "one-time"},
            ],
            "working_capital": [
                {"name": "Raw materials (1 month)", "amount": 20000, "unit": "/month"},
                {"name": "Electricity", "amount": 5000, "unit": "/month"},
                {"name": "Labour (1-2 workers)", "amount": 10000, "unit": "/month"},
                {"name": "Transportation", "amount": 3000, "unit": "/month"},
            ],
            "infrastructure": [
                {"name": "Workshop space setup", "amount": 10000, "unit": "one-time"},
            ],
            "licensing_compliance": [
                {"name": "Trade license", "amount": 500, "unit": "one-time"},
                {"name": "Udyam registration", "amount": 0, "unit": "free"},
            ],
            "contingency_pct": 10.0,
        },
        "small": {
            "capital_expenditure": [
                {"name": "Machinery (2-3 units)", "amount": 80000, "unit": "one-time"},
                {"name": "Raw material stock (1 month)", "amount": 40000, "unit": "one-time"},
                {"name": "Power tools & accessories", "amount": 15000, "unit": "one-time"},
                {"name": "Safety & quality equipment", "amount": 10000, "unit": "one-time"},
            ],
            "working_capital": [
                {"name": "Raw materials (1 month)", "amount": 50000, "unit": "/month"},
                {"name": "Electricity", "amount": 10000, "unit": "/month"},
                {"name": "Labour (4-5 workers)", "amount": 25000, "unit": "/month"},
                {"name": "Transportation & logistics", "amount": 8000, "unit": "/month"},
                {"name": "Maintenance reserve", "amount": 3000, "unit": "/month"},
            ],
            "infrastructure": [
                {"name": "Workshop with power supply", "amount": 25000, "unit": "one-time"},
                {"name": "Generator backup", "amount": 20000, "unit": "one-time"},
            ],
            "licensing_compliance": [
                {"name": "Trade license + pollution NOC", "amount": 3000, "unit": "one-time"},
                {"name": "GST registration", "amount": 1500, "unit": "one-time"},
                {"name": "Factory license (if >10 workers)", "amount": 2000, "unit": "one-time"},
            ],
            "contingency_pct": 10.0,
        },
        "medium": {
            "capital_expenditure": [
                {"name": "Production line machinery", "amount": 200000, "unit": "one-time"},
                {"name": "Raw material inventory", "amount": 100000, "unit": "one-time"},
                {"name": "Quality control equipment", "amount": 30000, "unit": "one-time"},
                {"name": "Safety systems", "amount": 15000, "unit": "one-time"},
                {"name": "Delivery vehicle", "amount": 40000, "unit": "one-time"},
            ],
            "working_capital": [
                {"name": "Raw materials (1 month)", "amount": 120000, "unit": "/month"},
                {"name": "Electricity & utilities", "amount": 20000, "unit": "/month"},
                {"name": "Labour (10-12 workers)", "amount": 60000, "unit": "/month"},
                {"name": "Logistics & distribution", "amount": 15000, "unit": "/month"},
                {"name": "Maintenance & consumables", "amount": 8000, "unit": "/month"},
            ],
            "infrastructure": [
                {"name": "Industrial shed", "amount": 60000, "unit": "one-time"},
                {"name": "3-phase power connection", "amount": 20000, "unit": "one-time"},
                {"name": "Generator (25 kVA)", "amount": 40000, "unit": "one-time"},
                {"name": "Waste management system", "amount": 15000, "unit": "one-time"},
            ],
            "licensing_compliance": [
                {"name": "Factory license + plans approval", "amount": 5000, "unit": "one-time"},
                {"name": "Pollution board consent (CTO)", "amount": 5000, "unit": "one-time"},
                {"name": "GST + trade license", "amount": 3000, "unit": "one-time"},
                {"name": "Labour law registrations", "amount": 3000, "unit": "one-time"},
            ],
            "contingency_pct": 10.0,
        },
    },

    # ── HANDICRAFTS ──────────────────────────────────────────────────
    "handicrafts": {
        "micro": {
            "capital_expenditure": [
                {"name": "Raw materials (wood/clay/fabric)", "amount": 5000, "unit": "one-time"},
                {"name": "Basic hand tools", "amount": 3000, "unit": "one-time"},
                {"name": "Display rack (roadside)", "amount": 2000, "unit": "one-time"},
            ],
            "working_capital": [
                {"name": "Raw materials (1 month)", "amount": 5000, "unit": "/month"},
                {"name": "Display & selling space", "amount": 2000, "unit": "/month"},
                {"name": "Transportation to market", "amount": 1500, "unit": "/month"},
            ],
            "infrastructure": [
                {"name": "Work area at home", "amount": 3000, "unit": "one-time"},
            ],
            "licensing_compliance": [
                {"name": "Udyam registration", "amount": 0, "unit": "free"},
            ],
            "contingency_pct": 8.0,
        },
        "small": {
            "capital_expenditure": [
                {"name": "Specialized tools & equipment", "amount": 15000, "unit": "one-time"},
                {"name": "Raw material stock", "amount": 10000, "unit": "one-time"},
                {"name": "Display units & packaging", "amount": 5000, "unit": "one-time"},
                {"name": "Small workshop setup", "amount": 8000, "unit": "one-time"},
            ],
            "working_capital": [
                {"name": "Raw materials (1 month)", "amount": 12000, "unit": "/month"},
                {"name": "Workshop rent", "amount": 3000, "unit": "/month"},
                {"name": "Packaging & labelling", "amount": 2000, "unit": "/month"},
                {"name": "Marketing & selling", "amount": 3000, "unit": "/month"},
            ],
            "infrastructure": [
                {"name": "Workshop with storage", "amount": 10000, "unit": "one-time"},
            ],
            "licensing_compliance": [
                {"name": "Trade license", "amount": 500, "unit": "one-time"},
                {"name": "GST (if applicable)", "amount": 1000, "unit": "one-time"},
            ],
            "contingency_pct": 8.0,
        },
        "medium": {
            "capital_expenditure": [
                {"name": "Advanced tools & machinery", "amount": 40000, "unit": "one-time"},
                {"name": "Raw material inventory", "amount": 30000, "unit": "one-time"},
                {"name": "Showroom & display setup", "amount": 20000, "unit": "one-time"},
                {"name": "E-commerce setup", "amount": 10000, "unit": "one-time"},
                {"name": "Packaging & branding", "amount": 10000, "unit": "one-time"},
            ],
            "working_capital": [
                {"name": "Raw materials (1 month)", "amount": 30000, "unit": "/month"},
                {"name": "Workshop rent", "amount": 6000, "unit": "/month"},
                {"name": "Artisan wages (3-4)", "amount": 20000, "unit": "/month"},
                {"name": "Marketing & online fees", "amount": 5000, "unit": "/month"},
                {"name": "Transportation & logistics", "amount": 5000, "unit": "/month"},
            ],
            "infrastructure": [
                {"name": "Workshop + showroom", "amount": 25000, "unit": "one-time"},
                {"name": "Storage & packing area", "amount": 10000, "unit": "one-time"},
            ],
            "licensing_compliance": [
                {"name": "Trade license + GST", "amount": 2000, "unit": "one-time"},
                {"name": "Artisan certification (if applicable)", "amount": 1000, "unit": "one-time"},
            ],
            "contingency_pct": 8.0,
        },
    },

    # ── OTHER (generic) ─────────────────────────────────────────────
    "other": {
        "micro": {
            "capital_expenditure": [
                {"name": "Basic equipment", "amount": 15000, "unit": "one-time"},
                {"name": "Initial stock / materials", "amount": 10000, "unit": "one-time"},
            ],
            "working_capital": [
                {"name": "Operating costs (1 month)", "amount": 10000, "unit": "/month"},
                {"name": "Rent", "amount": 3000, "unit": "/month"},
                {"name": "Utilities", "amount": 1500, "unit": "/month"},
            ],
            "infrastructure": [
                {"name": "Basic shop setup", "amount": 5000, "unit": "one-time"},
            ],
            "licensing_compliance": [
                {"name": "Trade license", "amount": 500, "unit": "one-time"},
                {"name": "Udyam registration", "amount": 0, "unit": "free"},
            ],
            "contingency_pct": 10.0,
        },
        "small": {
            "capital_expenditure": [
                {"name": "Equipment & tools", "amount": 40000, "unit": "one-time"},
                {"name": "Initial stock", "amount": 25000, "unit": "one-time"},
                {"name": "Signage & branding", "amount": 5000, "unit": "one-time"},
            ],
            "working_capital": [
                {"name": "Operating costs (1 month)", "amount": 30000, "unit": "/month"},
                {"name": "Rent", "amount": 6000, "unit": "/month"},
                {"name": "Labour (2 staff)", "amount": 10000, "unit": "/month"},
                {"name": "Utilities & misc", "amount": 3000, "unit": "/month"},
            ],
            "infrastructure": [
                {"name": "Shop fit-out", "amount": 10000, "unit": "one-time"},
            ],
            "licensing_compliance": [
                {"name": "Trade license + registrations", "amount": 2000, "unit": "one-time"},
            ],
            "contingency_pct": 10.0,
        },
        "medium": {
            "capital_expenditure": [
                {"name": "Full equipment suite", "amount": 100000, "unit": "one-time"},
                {"name": "Initial inventory", "amount": 60000, "unit": "one-time"},
                {"name": "Interior & branding", "amount": 20000, "unit": "one-time"},
            ],
            "working_capital": [
                {"name": "Operating costs (1 month)", "amount": 70000, "unit": "/month"},
                {"name": "Rent (larger space)", "amount": 12000, "unit": "/month"},
                {"name": "Labour (5+ staff)", "amount": 30000, "unit": "/month"},
                {"name": "Utilities & insurance", "amount": 8000, "unit": "/month"},
            ],
            "infrastructure": [
                {"name": "Full shop/office setup", "amount": 25000, "unit": "one-time"},
                {"name": "Generator backup", "amount": 20000, "unit": "one-time"},
            ],
            "licensing_compliance": [
                {"name": "All applicable licenses", "amount": 5000, "unit": "one-time"},
                {"name": "GST registration", "amount": 1500, "unit": "one-time"},
            ],
            "contingency_pct": 10.0,
        },
    },
}

# Scale descriptions
SCALE_DESCRIPTIONS = {
    "micro": "1-2 person operation, home-based or small stall, minimal equipment",
    "small": "3-5 person operation, dedicated shop/workshop, basic equipment",
    "medium": "6-12 person operation, established premises, professional equipment",
}

# Location cost multipliers for Erode district
LOCATION_FACTORS = {
    "erode_town": 1.0,
    "gobichettipalayam": 0.85,
    "bhavani": 0.80,
    "perundurai": 0.82,
    "sathyamangalam": 0.78,
    "nambiyur": 0.75,
    "anthiyur": 0.77,
    "modakkurichi": 0.80,
    "village_average": 0.72,
    "default": 1.0,
}


def get_cost_template(category_code: str, scale: str = "micro") -> dict:
    """Get cost template for a category at a given scale.

    Falls back to 'micro' if scale not found, falls back to 'other'
    if category not found.
    """
    cat_templates = TEMPLATES.get(category_code, TEMPLATES.get("other", {}))
    if scale in cat_templates:
        return cat_templates[scale]
    # Fallback: try micro, then first available
    if "micro" in cat_templates:
        return cat_templates["micro"]
    if cat_templates:
        return next(iter(cat_templates.values()))
    return TEMPLATES["other"]["micro"]


def get_total_template_cost(category_code: str, scale: str = "micro", location_factor: float = 1.0) -> float:
    """Quick helper: total project cost from template (before contingency)."""
    t = get_cost_template(category_code, scale)
    subtotal = 0.0
    for section in ("capital_expenditure", "working_capital", "infrastructure", "licensing_compliance"):
        for item in t.get(section, []):
            subtotal += item["amount"] * location_factor
    contingency = subtotal * t.get("contingency_pct", 10.0) / 100.0
    return round(subtotal + contingency, 2)


def list_categories() -> list[dict]:
    """List all categories with their available scales."""
    result = []
    for code, scales in TEMPLATES.items():
        result.append({
            "code": code,
            "scales": list(scales.keys()),
            "scale_descriptions": SCALE_DESCRIPTIONS,
            "total_micro": get_total_template_cost(code, "micro"),
            "total_small": get_total_template_cost(code, "small"),
            "total_medium": get_total_template_cost(code, "medium"),
        })
    return result
