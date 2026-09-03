"""NLP parser multilingual extraction tests (audit §nlp scenarios)."""
from __future__ import annotations

from app.engines.nlp_parser import parse_free_text


def test_tamil_dairy_bhavani():
    p = parse_free_text(
        "எனக்கு பவானியில் 5 லட்சம் ரூபாயில் ஒரு பால் பண்ணை ஆரம்பிக்கணும்."
    )
    assert p.detected_language == "ta"
    assert p.business_type == "dairy"
    assert p.location["block"] == "Bhavani"
    assert p.project_cost == 500000.0


def test_tanglish_tailoring_perundurai():
    p = parse_free_text("Perundurai la 3 lakh budget-la tailoring shop start panna mudiyuma?")
    assert p.business_type == "textile"
    assert p.location["block"] == "Perundurai"
    assert p.project_cost == 300000.0


def test_english_dairy_five_lakh_words():
    p = parse_free_text("Can I start a dairy farm in Bhavani with a budget of five lakh rupees?")
    assert p.business_type == "dairy"
    assert p.location["block"] == "Bhavani"
    assert p.project_cost == 500000.0


def test_hindi_dairy_bhavani():
    p = parse_free_text("क्या मैं भवानी में 5 लाख रुपये में डेयरी फार्म शुरू कर सकता हूं?")
    assert p.detected_language == "hi"
    assert p.business_type == "dairy"
    assert p.location["block"] == "Bhavani"
    assert p.project_cost == 500000.0


def test_tamil_transliterated_dairy_word():
    # "டெய்ரி" (transliterated "dairy") should be recognised.
    p = parse_free_text("எனக்கு ஈரோட்டில் ஒரு டெய்ரி பிசினஸ் ஆரம்பிக்கணும்")
    assert p.business_type == "dairy"
    assert p.location["district"] == "Erode"


def test_inflected_tamil_district():
    # "ஈரோட்டில்" is the oblique/locative stem of "ஈரோடு".
    p = parse_free_text("ஈரோட்டில் ஒரு கடை ஆரம்பிக்கணும்")
    assert p.location["district"] == "Erode"


def test_vague_input_reports_missing_without_inventing():
    p = parse_free_text("I want to start a business.")
    assert p.business_type is None
    assert p.project_cost is None
    for field in ("state", "district", "business_type", "budget"):
        assert field in p.missing_fields
