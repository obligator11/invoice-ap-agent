from __future__ import annotations

import json
import re

from config.settings import settings
from schemas.models import ExtractedInvoice, RoutingDecision
from services.llm_clients import call_ollama, LLMUnavailableError

_SYSTEM_PROMPT = """You route approved invoices to the right department for
final processing. Given the vendor name, invoice line items, and total
amount, decide which department this most likely belongs to (e.g.
"Engineering", "Marketing", "Facilities", "Office Ops", "Finance", "IT") and
suggest a plausible approver email in the form firstname.lastname@company.com
using the department name as a best guess (e.g. it.approver@company.com).

Respond with ONLY JSON, no markdown fences:
{"department": string, "approver_email": string, "rationale": short string}"""

_FALLBACK_DEPARTMENT = "Finance"
_FALLBACK_EMAIL = "ap-review@company.com"


def _strip_code_fences(text: str) -> str:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    return match.group(0) if match else text


def route_invoice(invoice: ExtractedInvoice, vendor_default_department: str | None = None) -> RoutingDecision:
    # If we already know this vendor's department from prior invoices,
    # skip the model call entirely — cheaper and more consistent.
    if vendor_default_department:
        return RoutingDecision(
            department=vendor_default_department,
            approver_email=f"{vendor_default_department.lower().replace(' ', '.')}.approver@company.com",
            rationale=f"Vendor previously routed to {vendor_default_department}.",
        )

    prompt = (
        f"Vendor: {invoice.vendor_name}\n"
        f"Line items: {[li.description for li in invoice.line_items]}\n"
        f"Total: {invoice.total} {invoice.currency}"
    )
    try:
        raw_output = call_ollama(settings.ollama_router_model, prompt, system=_SYSTEM_PROMPT)
        parsed = json.loads(_strip_code_fences(raw_output))
        return RoutingDecision.model_validate(parsed)
    except (LLMUnavailableError, ValueError, json.JSONDecodeError):
        return RoutingDecision(
            department=_FALLBACK_DEPARTMENT,
            approver_email=_FALLBACK_EMAIL,
            rationale="Router model unavailable or returned invalid output — defaulted to Finance.",
        )
