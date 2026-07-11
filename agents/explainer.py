from __future__ import annotations

from config.settings import settings
from schemas.models import AgentVerdict, PlainExplanation
from services.llm_clients import call_ollama, LLMUnavailableError

_SYSTEM_PROMPT = """You rewrite AP-analyst reasoning into one short, plain
English paragraph (2-4 sentences max) for a non-technical finance person.
No jargon, no bullet points, no restating that you're an AI. Just say
plainly what's going on and why. If the verdict was auto_approve, say so
briefly and positively. If needs_review or reject, be clear about the
specific concern(s) without being alarmist."""


def explain_verdict(verdict: AgentVerdict) -> PlainExplanation:
    prompt = (
        f"Verdict: {verdict.verdict.value}\n"
        f"Risk flags: {', '.join(verdict.risk_flags) or 'none'}\n\n"
        f"Full reasoning:\n{verdict.reasoning_chain}"
    )
    try:
        summary = call_ollama(settings.ollama_explainer_model, prompt, system=_SYSTEM_PROMPT)
    except LLMUnavailableError:
        # Explainer failing shouldn't block the pipeline — fall back to a
        # blunt but honest auto-generated note rather than losing the verdict.
        summary = (
            f"Verdict: {verdict.verdict.value}. "
            f"(Plain-English explainer model unavailable — showing raw flags: "
            f"{', '.join(verdict.risk_flags) or 'none'}.)"
        )

    return PlainExplanation(summary=summary.strip(), based_on_verdict=verdict.verdict)
