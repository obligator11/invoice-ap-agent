from __future__ import annotations

import json
import re

from config.settings import settings
from schemas.models import ExtractedInvoice
from services.llm_clients import call_lmstudio, LLMUnavailableError

_SYSTEM_PROMPT = """You are an invoice data extraction engine. Given raw text
extracted from an invoice (via OCR or PDF parsing, so it may contain noise,
line breaks in odd places, or minor OCR errors), extract structured data.

Respond with ONLY a JSON object, no markdown fences, no commentary, matching
exactly this shape:

{
  "vendor_name": string,
  "invoice_number": string,
  "invoice_date": "YYYY-MM-DD",
  "due_date": "YYYY-MM-DD" or null,
  "line_items": [
    {"description": string, "quantity": number, "unit_price": number, "line_total": number}
  ],
  "subtotal": number,
  "tax": number,
  "total": number,
  "currency": "USD" (3-letter code),
  "po_number": string or null
}

If a field is genuinely not present in the text, use null (or 0 for tax if
no tax line exists). Do not invent values. Ensure quantity * unit_price is
approximately equal to line_total for each item, and subtotal + tax is
approximately equal to total."""


def _strip_code_fences(text: str) -> str:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    return match.group(0) if match else text


def extract_invoice(raw_text: str) -> tuple[ExtractedInvoice | None, str]:
    """Returns (extracted_invoice_or_None, raw_model_output_for_audit_log)."""
    prompt = f"Raw invoice text:\n\n{raw_text}"
    last_raw_output = ""
    last_error = ""

    for attempt in range(settings.max_llm_retries + 1):
        try:
            if attempt == 0:
                raw_output = call_lmstudio(
                    settings.lmstudio_extractor_model, prompt, system=_SYSTEM_PROMPT
                )
            else:
                fix_prompt = (
                    f"Your previous JSON output failed validation with this error:\n"
                    f"{last_error}\n\n"
                    f"Your previous output was:\n{last_raw_output}\n\n"
                    f"Fix it and return ONLY the corrected JSON object."
                )
                raw_output = call_lmstudio(
                    settings.lmstudio_extractor_model, fix_prompt, system=_SYSTEM_PROMPT
                )

            last_raw_output = raw_output
            json_str = _strip_code_fences(raw_output)
            parsed = json.loads(json_str)
            invoice = ExtractedInvoice.model_validate(parsed)
            return invoice, raw_output

        except LLMUnavailableError:
            raise  # let the pipeline handle server-down separately from bad-output
        except (json.JSONDecodeError, ValueError) as e:
            last_error = str(e)
            continue

    return None, last_raw_output
