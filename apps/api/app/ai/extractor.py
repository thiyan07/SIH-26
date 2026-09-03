"""AI-powered multilingual input extractor.

Enhances the deterministic regex parser (`app.engines.nlp_parser`) with an
LLM-backed extraction layer so free-text business descriptions in English,
Tamil, Hindi and mixed "Tanglish"/transliterated input parse more reliably
(arbitrary place names, informal phrasing, synonyms).

Design principles (mirroring the rest of the app):
  * All *facts* are extracted from the user's free text only — the LLM is
    asked for a structured JSON payload, never to invent statistics.
  * Every numeric value is sanity-clamped to a plausible business range so a
    misbehaving model can never inject absurd figures.
  * When no LLM is configured (mock provider) or the LLM call fails, the
    module transparently falls back to the deterministic regex parser.
  * The output always has the same shape as `paarse_free_text`, so callers and
    API consumers are unaffected.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Optional

from app.ai.llm import SYSTEM_INSTRUCTIONS, get_provider
from app.config import settings
from app.engines.nlp_parser import ParsedInput, parse_free_text

logger = logging.getLogger("grambiz.ai.extractor")

# Canonical business-type codes understood by the financial engines.
BUSINESS_TYPES = [
    "dairy", "poultry", "grocery", "textile", "food_processing",
    "restaurant", "agriculture", "manufacturing", "handicrafts", "other",
]

SCALES = ["micro", "small", "medium"]

# Reasonable absolute bounds so the LLM can never fabricate absurd numbers.
# Project cost / capital rarely exceeds a few crores for rural micro/small units.
MAX_COST = 5_000_000
MAX_INCOME = 100_000_000
MAX_AGE = 100


def _is_llm_available() -> bool:
    """Whether a real LLM (not the deterministic mock) is configured."""
    prov = settings.llm_provider or "mock"
    return prov.lower() in ("openai", "nvidia") and bool(settings.llm_api_key)


def _coerce_int(value, lo: int = 0, hi: int = 100) -> Optional[int]:
    """Safely coerce a value to an int within [lo, hi], else None."""
    if value is None or value == "":
        return None
    try:
        n = int(float(value))
    except (TypeError, ValueError):
        return None
    if n < lo or n > hi:
        return None
    return n


def _coerce_float(value, lo: float = 0.0, hi: float = MAX_COST) -> Optional[float]:
    """Safely coerce a value to a float within [lo, hi], else None."""
    if value is None or value == "":
        return None
    try:
        n = float(value)
    except (TypeError, ValueError):
        return None
    if n < lo or n > hi:
        return None
    return round(n, 2)


def _map_business_type(value) -> Optional[str]:
    """Map an LLM-provided category (label or code) to a canonical code."""
    if not value:
        return None
    text = str(value).strip().lower().replace(" ", "_").replace("-", "_")
    if text in BUSINESS_TYPES:
        return text
    # Map common human labels to canonical codes.
    aliases = {
        "dairy_farm": "dairy", "dairy_farming": "dairy", "milk": "dairy",
        "poultry_farm": "poultry", "chicken": "poultry", "eggs": "poultry",
        "grocery_store": "grocery", "groceries": "grocery", "retail": "grocery",
        "kirana": "grocery", "shop": "grocery", "store": "grocery",
        "tailoring": "textile", "tailor": "textile", "garments": "textile",
        "textile_tailoring": "textile", "sewing": "textile",
        "food_processing_unit": "food_processing", "food_processing_plant": "food_processing",
        "flour_mill": "food_processing", "rice_mill": "food_processing",
        "restaurant": "restaurant", "food_service": "restaurant", "hotel": "restaurant",
        "food_stall": "restaurant", "cafe": "restaurant",
        "agriculture": "agriculture", "farming": "agriculture", "agri": "agriculture",
        "manufacturing": "manufacturing", "factory": "manufacturing", "workshop": "manufacturing",
        "handicrafts": "handicrafts", "handicraft": "handicrafts", "craft": "handicrafts",
    }
    if text in aliases:
        return aliases[text]
    return None


def _map_scale(value) -> Optional[str]:
    if not value:
        return None
    text = str(value).strip().lower()
    if text in SCALES:
        return text
    return None


def _map_category(value) -> Optional[str]:
    if not value:
        return None
    text = str(value).strip().lower()
    categories = {
        "sc": "sc_st", "st": "sc_st", "sc/st": "sc_st", "sc_st": "sc_st",
        "scheduled_caste": "sc_st", "scheduled_tribe": "sc_st",
        "obc": "obc", "other_backward_class": "obc",
        "general": "general", "open": "general",
        "women": "women", "woman": "women", "female": "women",
        "minority": "minority",
        "ews": "ews", "economically_weaker": "ews", "bpl": "ews",
    }
    return categories.get(text)


def _clean(text: str) -> str:
    return (text or "").strip()


def _build_prompt(raw_text: str, language: str) -> str:
    types = ", ".join(BUSINESS_TYPES)
    return (
        "You are GramBiz AI's multilingual business-intake extractor. Extract the "
        "beneficiary's business details from their free-text description, which may be "
        "in English, Tamil, Hindi, or a mix (including transliterated 'Tanglish').\n\n"
        "INPUT:\n"
        f"{raw_text}\n\n"
        "Return a STRICT JSON object (no markdown, no commentary) with ONLY these keys:\n"
        f'{{"business_type": one of [{types}] or null, '
        '"scale": "micro", "small", or "medium" or null, '
        '"project_cost": number or null (the stated project cost/budget in rupees), '
        '"capital_available": number or null (stated available capital/savings in rupees), '
        '"annual_income": number or null (stated annual income in rupees), '
        '"age": integer or null, '
        '"beneficiary_category": one of [sc_st, obc, general, women, minority, ews] or null, '
        '"state": string or null, '
        '"district": string or null, '
        '"block": string or null, '
        '"village": string or null}\n\n'
        "Rules:\n"
        "- Only fill a field if the user actually stated it. Otherwise use null. "
        "Never invent values.\n"
        "- Convert lakhs/crores to absolute rupees (1 lakh = 100000, 1 crore = 10000000).\n"
        "- Output place names in standard English form; recognise transliterated "
        "Indian place names (e.g. 'Perundurai la', 'Erode-u', 'Bengaluru'). "
        "Keep the canonical spelling (Iroda -> Erode, Perundurai).\n"
        "- Recognise mixed 'Tanglish' text (Tamil words romanised with English): "
        "e.g. 'pal pannai' = dairy, 'kadai' = shop/grocery.\n"
        f"- Requested language tag: {language}"
    )


def _parse_llm_json(content: str) -> Optional[dict]:
    """Extract a JSON object from an LLM response, tolerating code fences."""
    text = (content or "").strip()
    if not text:
        return None
    # Strip markdown code fences if present.
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.MULTILINE).strip()
    text = re.sub(r"\s*```$", "", text).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # Find the first { ... } block as a last resort.
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if not m:
            return None
        try:
            data = json.loads(m.group(0))
        except json.JSONDecodeError:
            return None
    return data if isinstance(data, dict) else None


def _confidence_from_parse(parsed: ParsedInput) -> dict:
    """Compute the four-indicator opportunity confidence from a parsed result."""
    location = parsed.location or {}
    confidence = {
        "location": 1.0 if location.get("district") else (0.5 if location.get("state") else 0.0),
        "business_type": 1.0 if parsed.business_type else 0.0,
        "scale": 1.0 if parsed.scale else 0.3,
        "budget": 1.0 if (parsed.project_cost or parsed.capital_available) else 0.0,
        "overall": 0.0,
    }
    confidence["overall"] = round(
        sum(confidence.values()) / max(len(confidence) - 1, 1), 2
    )
    return confidence


def parse_with_llm(raw_text: str, lang_override: Optional[str] = None) -> Optional[ParsedInput]:
    """Run LLM extraction against the free text, or return None on failure/absence.

    Returns a fully-validated `ParsedInput` on success, else None so callers
    can transparently fall back to the deterministic parser.
    """
    if not raw_text or not _is_llm_available():
        return None

    from app.engines.nlp_parser import detect_language

    language = lang_override or detect_language(raw_text)
    try:
        provider = get_provider()
        res = provider.complete(
            SYSTEM_INSTRUCTIONS,
            _build_prompt(raw_text, language),
            {"free_text": raw_text},
        )
        data = _parse_llm_json(res.get("content", ""))
    except Exception:  # noqa: BLE001 - LLM failures fall back to regex parser
        logger.warning("LLM extraction failed; falling back to regex parser", exc_info=True)
        return None

    if data is None:
        # The (mock) provider returned non-JSON; fall back to the regex parser.
        return None

    location = {
        "state": _clean(data.get("state")) or None,
        "district": _clean(data.get("district")) or None,
        "block": _clean(data.get("block")) or None,
        "village": _clean(data.get("village")) or None,
    }

    project_cost = _coerce_float(data.get("project_cost"))
    capital = _coerce_float(data.get("capital_available"))
    income = _coerce_float(data.get("annual_income"), hi=MAX_INCOME)
    age = _coerce_int(data.get("age"), lo=15, hi=MAX_AGE)

    business_type = _map_business_type(data.get("business_type"))
    scale = _map_scale(data.get("scale"))
    category = _map_category(data.get("beneficiary_category"))

    # Compute missing-fields and suggestions (consistent with the regex parser).
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

    parsed = ParsedInput(
        raw_text=raw_text,
        detected_language=language,
        location=location,
        business_type=business_type,
        scale=scale,
        project_cost=project_cost,
        capital_available=capital,
        annual_income=income,
        age=age,
        beneficiary_category=category,
        confidence={},
        missing_fields=missing,
        suggestions=suggestions,
    )
    parsed.confidence = _confidence_from_parse(parsed)
    return parsed


def parse_multilingual_free_text(raw_text: str, lang_override: Optional[str] = None) -> ParsedInput:
    """AI-powered multilingual parser with deterministic fallback.

    Tries the LLM first when available; falls back to the regex parser when the
    LLM is unavailable, the response is malformed, or the call errors. The fallback
    guarantees the API never breaks when the LLM is down.

    When the LLM runs, the deterministic parser's location extraction is also run
    and any location field the LLM missed is filled from it (the regex parser has a
    curated Erode village/block dictionary that is more reliable for known places).
    """
    if not raw_text or not raw_text.strip():
        return parse_free_text(raw_text, lang_override=lang_override)

    regex_parsed = parse_free_text(raw_text, lang_override=lang_override)
    llm_result = parse_with_llm(raw_text, lang_override)

    parsed = llm_result if llm_result is not None else regex_parsed

    # Merge deterministic location extraction into the result: known Erode
    # villages/blocks the regex parser recognises are more reliable for geography.
    if llm_result is not None:
        for key in ("state", "district", "block", "village"):
            if not parsed.location.get(key) and regex_parsed.location.get(key):
                parsed.location[key] = regex_parsed.location[key]
        # Recompute the opportunity-confidence now that merged geography may exist.
        # Score only the four numeric indicators, ignoring provenance flags.
        parsed.confidence = _confidence_from_parse(parsed)

    # Mark provenance so callers/API can report whether the parse was LLM-driven.
    parsed.confidence["engine"] = "llm" if llm_result is not None else "regex"
    parsed.confidence["llm_available"] = _is_llm_available()
    return parsed
