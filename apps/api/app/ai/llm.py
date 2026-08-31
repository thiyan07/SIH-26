"""LLM abstraction - provider-agnostic.

A clean interface decouples the rest of the app from a specific vendor.
Providers: a deterministic in-memory mock (default, no key needed), plus an
OpenAI-compatible client gated by LLM_PROVIDER + LLM_API_KEY.

The mock returns responses that never invent statistics: it restates the
supplied evidence only.
"""
from __future__ import annotations

import json

from app.config import settings

SYSTEM_INSTRUCTIONS = (
    "You are GramBiz AI, an evidence-driven rural business advisor. "
    "Use ONLY the supplied structured evidence. Do NOT invent statistics, "
    "prices, population, competitor counts, scheme rules, or loan terms. "
    "If evidence is insufficient, explicitly say that evidence is insufficient. "
    "Financial values shown must match the supplied evidence exactly. "
    "Respond in the requested language."
)


class LLMProvider:
    name = "base"

    def complete(self, system: str, user: str, evidence: dict) -> dict:
        raise NotImplementedError


class MockLLMProvider(LLMProvider):
    """Deterministic provider used when no API key is set.

    Produces a safe summary that only echoes evidence — never fabricates.
    """

    name = "mock"

    def complete(self, system: str, user: str, evidence: dict) -> dict:
        if "rag_citations" in evidence:
            lines = ["GramBiz AI RAG answer (deterministic evidence):"]
            for c in evidence["rag_citations"]:
                lines.append(f"- Source: {c.get('title')}")
                if c.get("url"):
                    lines.append(f"  URL: {c.get('url')}")
                excerpt = (c.get("excerpt") or "").strip()
                if excerpt:
                    lines.append(f"  Excerpt: {excerpt[:300]}")
            lines.append(
                "  The above is quoted directly from the retrieved documents; "
                "nothing was added."
            )
            return {"content": "\n".join(lines)}
        score = evidence.get("opportunity_score", {})
        rec = evidence.get("recommendation", {})
        lines = [
            "GramBiz AI analysis summary (deterministic evidence):",
            f"- Overall opportunity (Prototype Index): {score.get('overall_score')}/100",
            f"- Confidence: {score.get('confidence_label')}",
            f"- Recommendation: {rec.get('label') if 'label' in rec else ''}",
            "- All figures above are taken directly from the deterministic engine; no extra statistics were generated.",
        ]
        return {"content": "\n".join(lines)}


class OpenAILikeProvider(LLMProvider):
    """OpenAI-compatible client. Configure via env (LLM_API_KEY, LLM_MODEL)."""

    name = "openai"

    def complete(self, system: str, user: str, evidence: dict) -> dict:
        try:
            from openai import OpenAI
        except ImportError as e:  # pragma: no cover
            return {"content": f"OpenAI client unavailable: {e}"}
        kwargs = {"api_key": settings.llm_api_key}
        if settings.llm_base_url:
            kwargs["base_url"] = settings.llm_base_url
        client = OpenAI(**kwargs)
        resp = client.chat.completions.create(
            model=settings.llm_model or "gpt-4o-mini",
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.2,
        )
        return {"content": resp.choices[0].message.content}


def get_provider() -> LLMProvider:
    prov = settings.llm_provider
    if prov.lower() in ("openai", "nvidia"):
        return OpenAILikeProvider()
    return MockLLMProvider()


def build_evidence_prompt(evidence: dict, mode: str, language: str) -> str:
    """Serialize evidence (the deterministic context) into the prompt."""
    relevant = {}
    keys = ["location", "population", "business_competition", "infrastructure",
            "weather", "opportunity_score", "financial_plan", "repayment",
            "profit_model", "recommendation", "data_sources"]
    for k in keys:
        if k in evidence:
            relevant[k] = evidence[k]

    prompt = f"Requested mode: {mode}\nLanguage: {language}\n\n"
    prompt += "EVIDENCE (use only this; do not invent):\n"
    prompt += json.dumps(relevant, default=str, ensure_ascii=False, indent=2)
    prompt += "\n\nProduce the requested output grounded strictly in this evidence."
    return prompt


def get_provider_for_testing() -> LLMProvider:
    return MockLLMProvider()
