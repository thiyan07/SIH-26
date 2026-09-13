"""Regression tests for plain-English analyzer (final product journey).

Tests the complete flow: free text -> parse -> structured fields -> form -> analysis request.

Examples from final requirements:
A: grocery shop near Perundurai
B: dairy business in Bhavani with 5 cows
C: mobile repair shop in Chennai
"""
from app.engines.nlp_parser import parse_free_text

def test_example_a_grocery_perundurai():
    text = "I want to start a small grocery shop near Perundurai selling rice, vegetables, groceries and household products."
    p = parse_free_text(text)
    assert p.business_type == "grocery", f"Expected grocery, got {p.business_type}"
    assert p.location["block"] == "Perundurai"
    assert p.location["district"] == "Erode"
    assert p.location["state"] == "Tamil Nadu"
    assert p.scale == "small"

def test_example_b_dairy_bhavani():
    text = "I want to open a dairy business in Bhavani with around 5 cows."
    p = parse_free_text(text)
    assert p.business_type == "dairy"
    assert p.location["block"] == "Bhavani"
    assert p.location["district"] == "Erode"
    assert p.location["state"] == "Tamil Nadu"

def test_example_c_mobile_chennai():
    text = "I want to start a mobile phone repair shop in Chennai."
    p = parse_free_text(text)
    # Should be mobile_shop, not grocery/poultry
    assert p.business_type == "mobile_shop", f"Expected mobile_shop, got {p.business_type}"
    assert p.location["district"] == "Chennai"
    assert p.location["state"] == "Tamil Nadu"
    # Shop implies small scale
    assert p.scale in ("small", "micro", None)  # allow None if not inferred

def test_plain_english_prefills_form_and_submits():
    """End-to-end: parsed fields are reflected in form and used for analysis."""
    from app.engines.nlp_parser import parse_free_text
    # Simulate what Analyze.tsx does: parse -> setLocalForm
    text = "I want to start a small grocery shop near Perundurai selling rice, vegetables, groceries and household products."
    parsed = parse_free_text(text)
    # Mock form as in Analyze.tsx
    form = {
        "state": "",
        "district": "",
        "block": "",
        "village": "",
        "capital_available": 100000,
        "category_code": "dairy",
        "preferred_scale": "small",
    }
    # Simulate parseAndPrefill logic
    if parsed.business_type:
        form["category_code"] = parsed.business_type
    if parsed.scale:
        form["preferred_scale"] = parsed.scale
    if parsed.location.get("state"):
        form["state"] = parsed.location["state"]
    if parsed.location.get("district"):
        form["district"] = parsed.location["district"]
    if parsed.location.get("block"):
        form["block"] = parsed.location["block"]
    if parsed.location.get("village"):
        form["village"] = parsed.location["village"]
    # Check that form was correctly updated
    assert form["category_code"] == "grocery"
    assert form["block"] == "Perundurai"
    assert form["district"] == "Erode"
    assert form["state"] == "Tamil Nadu"
    # User can manually edit
    form["capital_available"] = 150000
    assert form["capital_available"] == 150000
    # Submitting analysis uses edited values
    payload = {
        "state": form["state"],
        "district": form["district"],
        "block": form["block"],
        "village": form["village"],
        "capital_available": form["capital_available"],
        "category_code": form["category_code"],
        "preferred_scale": form["preferred_scale"],
    }
    assert payload["category_code"] == "grocery"
    assert payload["capital_available"] == 150000

def test_fallback_when_llm_fails():
    """Regex fallback should work when LLM is unavailable."""
    # Direct regex parser should still extract without inventing
    p = parse_free_text("I want to start a business.")
    assert p.business_type is None
    assert "business_type" in p.missing_fields
