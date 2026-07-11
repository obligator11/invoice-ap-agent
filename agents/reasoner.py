from __future__ import annotations

import json
import re

from config.settings import settings
from db.models import Invoice
from schemas.models import AgentVerdict, ExtractedInvoice, MatchResult, Verdict
from services.llm_clients import call_lmstudio, LLMUnavailableError

_SYSTEM_PROMPT = """You are an accounts-payable fraud and anomaly analyst.
Given an extracted invoice, its PO match result, and this vendor's recent
invoice history, reason step by step about whether this invoice is safe to
auto-approve. Specifically check for:
- duplicate invoice numbers (same number seen before for this vendor)
- unusual amount compared to this vendor's typical invoice amounts
- mismatched or missing PO
- suspicious new bank/routing details mentioned in the invoice text
- round-number invoices (e.g. exactly $5,000.00) which are a common fraud pattern
- invoices priced just under a known approval threshold, as if deliberately
  structured to avoid review
- low-confidence OCR extraction (treat this as a reason to lean toward review,
  since a misread digit is exactly what this step exists to catch)

Respond with ONLY a JSON object, no markdown fences:
{
  "verdict": "auto_approve" | "needs_review" | "reject",
  "reasoning_chain": "your full step-by-step reasoning, in your own words",
  "risk_flags": ["short_snake_case_flag", ...],
  "confidence": 0.0-1.0
}"""


def _strip_code_fences(text: str) -> str:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    return match.group(0) if match else text


def _build_prompt(
    invoice: ExtractedInvoice,
    match_result: MatchResult,
    vendor_history: list[Invoice],
    low_confidence_ocr: bool,
    auto_approve_threshold: float,
) -> str:
    history_lines = [
        f"- Invoice #{h.invoice_number}: {h.total} {h.currency} on {h.invoice_date}"
        for h in vendor_history
    ] or ["(no prior invoices on file for this vendor)"]

    return f"""Extracted invoice:
{invoice.model_dump_json(indent=2)}

PO match result:
{match_result.model_dump_json(indent=2)}

This vendor's recent invoice history:
{chr(10).join(history_lines)}

OCR confidence flag: {"LOW - this was a scanned/photographed document with low OCR confidence" if low_confidence_ocr else "N/A or high confidence"}

Current auto-approve ceiling (company policy): {auto_approve_threshold}
"""


def assess_invoice(
    invoice: ExtractedInvoice,
    match_result: MatchResult,
    vendor_history: list[Invoice],
    low_confidence_ocr: bool = False,
) -> tuple[AgentVerdict | None, str]:
    """Returns (verdict_or_None, raw_model_output_for_audit_log)."""
    prompt = _build_prompt(
        invoice, match_result, vendor_history, low_confidence_ocr, settings.auto_approve_max_amount
    )

    last_raw_output = ""
    last_error = ""

    for attempt in range(settings.max_llm_retries + 1):
        try:
            if attempt == 0:
                raw_output = call_lmstudio(
                    settings.lmstudio_reasoner_model, prompt, system=_SYSTEM_PROMPT
                )
            else:
                fix_prompt = (
                    f"Your previous JSON output failed validation: {last_error}\n\n"
                    f"Previous output:\n{last_raw_output}\n\n"
                    f"Return corrected JSON only."
                )
                raw_output = call_lmstudio(
                    settings.lmstudio_reasoner_model, fix_prompt, system=_SYSTEM_PROMPT
                )

            last_raw_output = raw_output
            json_str = _strip_code_fences(raw_output)
            parsed = json.loads(json_str)
            verdict = AgentVerdict.model_validate(parsed)
            # NOTE: the auto-approve $ ceiling is enforced later, in the
            # HITL Gate (agents/hitl_gate.py) — deliberately not here.
            # This agent's job is only to produce its best-guess verdict;
            # policy enforcement is a separate, deterministic concern.
            return verdict, raw_output

        except LLMUnavailableError:
            raise
        except (json.JSONDecodeError, ValueError) as e:
            last_error = str(e)
            continue

    return None, last_raw_output
