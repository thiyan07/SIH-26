"""Multilingual NLP input parser for advisory intake.

Extracts structured beneficiary information from free-text in English,
Tamil, and Hindi. Pure regex + keyword matching — no LLM dependency for
the extraction step.

Supports:
  - Location extraction (district, block, village names)
  - Business type detection
  - Budget/cost range extraction
  - Scale inference (micro/small/medium)
  - Age, income, beneficiary category extraction
  - Language detection (basic keyword heuristic)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


ERODE_BLOCKS = [
    "erode", "gobichettipalayam", "bhavani", "perundurai",
    "sathyamangalam", "sathy", "nambiyur", "anthiyur",
    "modakkurichi", "kadathur", "tally", "palladam",
]

ERODE_VILLAGES = [
    "surampatti", "lakkapuram", "nanjanad", "kasipalayam",
    "veerachola", "kavindapadi", "nallampalli", "arachalur",
    "chennimalai", "uloor", "pudur", "ponnur",
]

BUSINESS_KEYWORDS_EN = {
    "dairy": ["dairy", "milk", "cow", "buffalo", "milking", "curd", "paneer", "ghee"],
    "poultry": ["poultry", "chicken", "eggs", "broiler", "layer", "hen", "bird"],
    "grocery": ["grocery", "shop", "store", "retail", "kirana", "general store", "supermarket"],
    "textile": ["textile", "tailoring", "tailor", "sewing", "stitching", "cloth", "garment", "dress"],
    "food_processing": ["food processing", "flour mill", "rice mill", "spice", "pickle", "packaging", "food manufacturing"],
    "restaurant": ["restaurant", "hotel", "food stall", "tea shop", "mess", "canteen", "food court"],
    "agriculture": ["agriculture", "farming", "crop", "field", "cultivation", "irrigation", "paddy", "turmeric"],
    "manufacturing": ["manufacturing", "workshop", "factory", "production", "machine", "fabrication"],
    "handicrafts": ["handicraft", "craft", "pottery", "weaving", "bamboo", "art work", "handmade"],
}

BUSINESS_KEYWORDS_TA = {
    "dairy": ["பால்", "ஆடு", "எருமை", "தயிர்", "வெண்ணெய்", "பால் பண்ணை"],
    "poultry": ["கோழி", "முட்டை", "கோழிப் பண்ணை", "கலப்பு கோழி"],
    "grocery": ["கடை", "மளிகை", "சில்லறை", "பொருள் கடை"],
    "textile": ["துணி", "தையல்", "ஆடை", "நெசவு"],
    "food_processing": ["உணவு பதப்படுத்தல்", "அரைக்கும் ஆலை", "மசாலா"],
    "restaurant": ["உணவகம்", "ஹோட்டல்", "தேநீர் கடை", "சாப்பாட்டுக் கடை"],
    "agriculture": ["விவசாயம்", "பயிர்", "நெல்", "மஞ்சள்", "காய்கறி"],
    "manufacturing": ["உற்பத்தி", "ஆலை", "தொழிற்சாலை", "இயந்திரம்"],
    "handicrafts": ["கைவினை", "மட்பாண்டம்", "நெசவு", "பொம்மலாட்டம்"],
}

BUSINESS_KEYWORDS_HI = {
    "dairy": ["दूध", "गाय", "भैंस", "दही", "मक्खन", "डेयरी"],
    "poultry": ["मुर्गी", "अंडा", "पोल्ट्री", "ब्रॉयलर"],
    "grocery": ["दुकान", "किराना", "स्टोर", "सब्ज़ी"],
    "textile": ["कपड़ा", "सिलाई", "वस्त्र", "बुनाई"],
    "food_processing": ["खाद्य प्रसंस्करण", "चक्की", "मसाला"],
    "restaurant": ["रेस्तरां", "होटल", "चाय की दुकान", "भोजनालय"],
    "agriculture": ["खेती", "फसल", "धान", "हल्दी", "कृषि"],
    "manufacturing": ["उत्पादन", "कारखाना", "मशीन"],
    "handicrafts": ["हस्तशिल्प", "कला", "बर्तन"],
}

SCALE_KEYWORDS = {
    "micro": ["micro", "small", "single", "home", "solo", "2-3", "one person", "small scale",
              "சிறிய", "ஒரு நபर்", "छोटा", "घर"],
    "small": ["small", "3-5", "few", "team", "shop", "மிதமான", "दुकान"],
    "medium": ["medium", "6-12", "team", "workshop", "factory", "large",
               "நடுத்தர", "பெரிய", "मध्यम"],
}

INCOME_KEYWORDS = {
    "en": [r"income\s*(?:of|is|:)?\s*₹?\s*([\d,]+)", r"earn(?:s|ing)?\s*₹?\s*([\d,]+)",
           r"salary\s*(?:of|is|:)?\s*₹?\s*([\d,]+)", r"annual\s+(?:income|earning)s?\s*(?:of|is|:)?\s*₹?\s*([\d,]+)"],
    "ta": [r"வருமானம்\s*₹?\s*([\d,]+)", r"சம்பளம்\s*₹?\s*([\d,]+)"],
    "hi": [r"आय\s*₹?\s*([\d,]+)", r"वेतन\s*₹?\s*([\d,]+)"],
}

AGE_KEYWORDS = {
    "en": [r"age\s*(?:of|is|:)?\s*(\d{1,3})", r"(\d{1,3})\s*years?\s*old"],
    "ta": [r"வயது\s*(\d{1,3})", r"(\d{1,3})\s*வயது"],
    "hi": [r"उम्र\s*(\d{1,3})", r"(\d{1,3})\s*साल"],
}

COST_KEYWORDS = {
    "en": [r"(?:cost|budget|price|project)\s*(?:of|is|:)?\s*₹?\s*([\d,]+(?:\.\d+)?)\s*(?:lakh|lac)?",
           r"₹\s*([\d,]+(?:\.\d+)?)\s*(?:lakh|lac)", r"([\d,]+(?:\.\d+)?)\s*lakh"],
    "ta": [r"செலவு\s*₹?\s*([\d,]+(?:\.\d+)?)\s*(?:லட்சம்|இலட்சம்)?",
           r"முதலீடு\s*₹?\s*([\d,]+(?:\.\d+)?)\s*(?:லட்சம்|இலட்சம்)?",
           r"([\d,]+(?:\.\d+)?)\s*லட்சம்", r"([\d,]+(?:\.\d+)?)\s*இலட்சம்",
           r"(?:பட்ஜெட்|பட்ஜெட்டு)\s*₹?\s*([\d,]+(?:\.\d+)?)\s*(?:லட்சம்|இலட்சம்)?"],
    "hi": [r"खर्चा?\s*₹?\s*([\d,]+(?:\.\d+)?)\s*(?:लाख)?",
           r"बजट\s*₹?\s*([\d,]+(?:\.\d+)?)\s*(?:लाख)?", r"([\d,]+(?:\.\d+)?)\s*लाख"],
}

CAPITAL_KEYWORDS = {
    "en": [r"(?:have|with|available)\s*₹?\s*([\d,]+(?:\.\d+)?)\s*(?:lakh|lac)?",
           r"capital\s*(?:of|is|:)?\s*₹?\s*([\d,]+)", r"savings?\s*(?:of|is|:)?\s*₹?\s*([\d,]+)"],
    "ta": [r"முதலீடு\s*₹?\s*([\d,]+(?:\.\d+)?)\s*(?:லட்சம்|இலட்சம்)?",
           r"சேமிப்பு\s*₹?\s*([\d,]+(?:\.\d+)?)\s*(?:லட்சம்|இலட்சம்)?",
           r"([\d,]+(?:\.\d+)?)\s*லட்சம்", r"([\d,]+(?:\.\d+)?)\s*இலட்சம்"],
    "hi": [r"पूँजी\s*₹?\s*([\d,]+(?:\.\d+)?)\s*(?:लाख)?",
           r"बचत\s*₹?\s*([\d,]+(?:\.\d+)?)\s*(?:लाख)?", r"([\d,]+(?:\.\d+)?)\s*लाख"],
}

CATEGORY_KEYWORDS = {
    "en": {
        "sc_st": ["sc", "st", "scheduled caste", "scheduled tribe", "dalit", "adivasi"],
        "obc": ["obc", "other backward class", "backward class"],
        "general": ["general", "open category", "general category"],
        "women": ["women", "woman", "female", "girl", "widow"],
        "minority": ["minority", "muslim", "christian", "sikh"],
        "ews": ["ews", "economically weaker", "bpl", "below poverty"],
    },
    "ta": {
        "sc_st": ["தலித்", "பழங்குடி", "ஆதிதிராவிடர்", "பட்டியல் சாதி"],
        "obc": ["பிற்படுத்தப்பட்டோர்", "ஓபிசி"],
        "women": ["பெண்", "பெண்கள்", "விதவை"],
    },
    "hi": {
        "sc_st": ["अनुसूचित जाति", "अनुसूचित जनजाति", "दलित"],
        "obc": ["पिछड़ा वर्ग", "ओबीसी"],
        "women": ["महिला", "स्त्री", "विधवा"],
    },
}


def detect_language(text: str) -> str:
    """Basic language detection based on character ranges and keywords."""
    text_lower = text.lower()
    # Check for Tamil script (Unicode range \u0B80-\u0BFF)
    tamil_chars = len(re.findall(r'[\u0B80-\u0BFF]', text))
    # Check for Devanagari (Hindi) - Unicode range \u0900-\u097F)
    hindi_chars = len(re.findall(r'[\u0900-\u097F]', text))
    total_alpha = len(re.findall(r'[a-zA-Z\u0B80-\u0BFF\u0900-\u097F]', text))

    if total_alpha == 0:
        return "en"
    if tamil_chars / max(total_alpha, 1) > 0.3:
        return "ta"
    if hindi_chars / max(total_alpha, 1) > 0.3:
        return "hi"
    return "en"


def _parse_number(s: str) -> Optional[float]:
    """Parse a number string, handling commas and lakh notation."""
    s = s.strip().replace(",", "")
    try:
        val = float(s)
        return val
    except ValueError:
        return None


def _extract_with_keywords(text: str, keyword_map: dict) -> Optional[str]:
    """Extract a value using keyword patterns."""
    text_lower = text.lower()
    for lang, patterns in keyword_map.items():
        for pattern in patterns:
            match = re.search(pattern, text_lower)
            if match:
                return match.group(1)
    return None


def extract_location(text: str) -> dict:
    """Extract location information from free text."""
    text_lower = text.lower()
    result = {"state": None, "district": None, "block": None, "village": None}

    # State
    if any(w in text_lower for w in ["tamil nadu", "tamilnadu", "தமிழ்நாडு", "तमिलनाडु"]):
        result["state"] = "Tamil Nadu"

    # District
    if "erode" in text_lower or "ஈரோடு" in text_lower or "ईरोड" in text_lower:
        result["district"] = "Erode"

    # Block
    for block in ERODE_BLOCKS:
        if block in text_lower:
            result["block"] = block.title()
            break

    # Village
    for village in ERODE_VILLAGES:
        if village in text_lower:
            result["village"] = village.title()
            break

    return result


def extract_business_type(text: str, lang: str = "en") -> Optional[str]:
    """Detect business type from free text."""
    text_lower = text.lower()

    keyword_map = {
        "en": BUSINESS_KEYWORDS_EN,
        "ta": BUSINESS_KEYWORDS_TA,
        "hi": BUSINESS_KEYWORDS_HI,
    }

    scores = {}
    for category, keywords in keyword_map.get(lang, BUSINESS_KEYWORDS_EN).items():
        count = sum(1 for kw in keywords if kw.lower() in text_lower)
        if count > 0:
            scores[category] = count

    # Also check English keywords as fallback
    if lang != "en":
        for category, keywords in BUSINESS_KEYWORDS_EN.items():
            count = sum(1 for kw in keywords if kw.lower() in text_lower)
            if count > 0:
                scores[category] = scores.get(category, 0) + count

    if not scores:
        return None
    return max(scores, key=scores.get)


def extract_scale(text: str) -> Optional[str]:
    """Infer business scale from text."""
    text_lower = text.lower()
    scores = {}
    for scale, keywords in SCALE_KEYWORDS.items():
        count = sum(1 for kw in keywords if kw.lower() in text_lower)
        if count > 0:
            scores[scale] = count
    if not scores:
        return None
    return max(scores, key=scores.get)


def _apply_lakh_multiplier(val: float, text_lower: str, start: int, end: int) -> float:
    """Apply the 1 lakh = 100000 multiplier if a lakh word/code appears near the number."""
    window = text_lower[max(0, start - 5):end + 15]
    if any(w in window for w in ("lakh", "lac", "லட்சம்", "இலட்சம்", "लाख")):
        if val < 1000:
            val *= 100000
    return val


def extract_cost(text: str) -> Optional[float]:
    """Extract project cost / budget from text."""
    text_lower = text.lower()
    for lang, patterns in COST_KEYWORDS.items():
        for pattern in patterns:
            match = re.search(pattern, text_lower)
            if match:
                val = _parse_number(match.group(1))
                if val is not None:
                    val = _apply_lakh_multiplier(val, text_lower, match.start(), match.end())
                    return val
    return None


def extract_capital(text: str) -> Optional[float]:
    """Extract available capital / savings from text."""
    text_lower = text.lower()
    for lang, patterns in CAPITAL_KEYWORDS.items():
        for pattern in patterns:
            match = re.search(pattern, text_lower)
            if match:
                val = _parse_number(match.group(1))
                if val is not None:
                    val = _apply_lakh_multiplier(val, text_lower, match.start(), match.end())
                    return val
    return None


def extract_income(text: str) -> Optional[float]:
    """Extract annual income from text."""
    text_lower = text.lower()
    for lang, patterns in INCOME_KEYWORDS.items():
        for pattern in patterns:
            match = re.search(pattern, text_lower)
            if match:
                val = _parse_number(match.group(1))
                if val is not None:
                    val = _apply_lakh_multiplier(val, text_lower, match.start(), match.end())
                    return val
    return None


def extract_age(text: str) -> Optional[int]:
    """Extract age from text."""
    text_lower = text.lower()
    for lang, patterns in AGE_KEYWORDS.items():
        for pattern in patterns:
            match = re.search(pattern, text_lower)
            if match:
                val = _parse_number(match.group(1))
                if val is not None and 15 <= val <= 100:
                    return int(val)
    return None


def extract_beneficiary_category(text: str, lang: str = "en") -> Optional[str]:
    """Extract beneficiary category (SC/ST/OBC/Women/Minority/EWS)."""
    text_lower = text.lower()
    keyword_map = CATEGORY_KEYWORDS.get(lang, CATEGORY_KEYWORDS["en"])
    for category, keywords in keyword_map.items():
        if any(kw.lower() in text_lower for kw in keywords):
            return category
    # Also check English as fallback
    if lang != "en":
        for category, keywords in CATEGORY_KEYWORDS["en"].items():
            if any(kw.lower() in text_lower for kw in keywords):
                return category
    return None


@dataclass
class ParsedInput:
    """Structured output from NLP parsing."""
    raw_text: str
    detected_language: str = "en"
    location: dict = field(default_factory=dict)
    business_type: Optional[str] = None
    scale: Optional[str] = None
    project_cost: Optional[float] = None
    capital_available: Optional[float] = None
    annual_income: Optional[float] = None
    age: Optional[int] = None
    beneficiary_category: Optional[str] = None
    confidence: dict = field(default_factory=dict)
    missing_fields: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)


def parse_free_text(text: str, lang_override: Optional[str] = None) -> ParsedInput:
    """Main entry point: extract structured data from free text in any supported language.

    Returns a ParsedInput with all fields that could be extracted, plus
    missing_fields list showing what still needs to be provided.
    """
    if not text or not text.strip():
        return ParsedInput(
            raw_text="",
            missing_fields=["All fields required"],
            suggestions=["Please describe your business idea, location, and budget."],
        )

    lang = lang_override or detect_language(text)
    location = extract_location(text)
    business_type = extract_business_type(text, lang)
    scale = extract_scale(text)
    project_cost = extract_cost(text)
    capital = extract_capital(text)
    income = extract_income(text)
    age = extract_age(text)
    beneficiary_cat = extract_beneficiary_category(text, lang)

    missing = []
    suggestions = []

    if not location.get("state"):
        missing.append("state")
        suggestions.append("Which state are you in? (e.g., Tamil Nadu)")
    if not location.get("district"):
        missing.append("district")
        suggestions.append("Which district? (e.g., Erode)")
    if not business_type:
        missing.append("business_type")
        suggestions.append("What type of business? (dairy, poultry, grocery, textile, etc.)")
    if project_cost is None and capital is None:
        missing.append("budget")
        suggestions.append("What is your estimated project cost or available capital?")

    confidence = {
        "location": 1.0 if location.get("district") else (0.5 if location.get("state") else 0.0),
        "business_type": 1.0 if business_type else 0.0,
        "scale": 1.0 if scale else 0.3,
        "budget": 1.0 if project_cost or capital else 0.0,
        "overall": 0.0,
    }
    confidence["overall"] = round(
        sum(confidence.values()) / max(len(confidence) - 1, 1), 2
    )

    return ParsedInput(
        raw_text=text,
        detected_language=lang,
        location=location,
        business_type=business_type,
        scale=scale,
        project_cost=project_cost,
        capital_available=capital,
        annual_income=income,
        age=age,
        beneficiary_category=beneficiary_cat,
        confidence=confidence,
        missing_fields=missing,
        suggestions=suggestions,
    )


def to_dict(parsed: ParsedInput) -> dict:
    """Serialize ParsedInput to JSON-safe dict."""
    return {
        "raw_text": parsed.raw_text,
        "detected_language": parsed.detected_language,
        "location": parsed.location,
        "business_type": parsed.business_type,
        "scale": parsed.scale,
        "project_cost": parsed.project_cost,
        "capital_available": parsed.capital_available,
        "annual_income": parsed.annual_income,
        "age": parsed.age,
        "beneficiary_category": parsed.beneficiary_category,
        "confidence": parsed.confidence,
        "missing_fields": parsed.missing_fields,
        "suggestions": parsed.suggestions,
    }
