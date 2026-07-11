from __future__ import annotations

from db.models import AuditLogEntry, Invoice, PurchaseOrder, Vendor
from db.session import get_session
from config.settings import settings
from schemas.models import InvoiceStatus, SourceMethod, Verdict

from agents.extractor import extract_invoice
from agents.matcher import match_invoice_to_po
from agents.reasoner import assess_invoice
from agents.explainer import explain_verdict
from agents.hitl_gate import run_hitl_gate
from agents.router import route_invoice
from services.llm_clients import LLMUnavailableError
from services import email_service


def _log(db, invoice_id: int, agent_name: str, model_used: str | None,
          input_summary: str, output_summary: str, raw_output: str | None = None) -> None:
    db.add(AuditLogEntry(
        invoice_id=invoice_id,
        agent_name=agent_name,
        model_used=model_used,
        input_summary=input_summary[:2000],
        output_summary=output_summary[:2000],
        raw_output=raw_output,
    ))
    db.commit()


def process_invoice(invoice_db_id: int) -> str:
    """Runs Extractor -> Matcher -> Reasoner -> Explainer -> HITL Gate,
    then Router if the gate clears immediately. Returns the invoice's
    resulting status string.

    Assumes the Invoice row already exists with raw_text + source_method
    populated (i.e. ingestion already ran — see ingestion/dispatch.py)."""
    with get_session() as db:
        invoice_row = db.get(Invoice, invoice_db_id)
        raw_text = invoice_row.raw_text
        low_confidence = invoice_row.source_method in (
            SourceMethod.OCR_SCAN.value, SourceMethod.OCR_PHOTO.value,
        )

    # --- 1. Extractor ---
    try:
        extracted, raw_output = extract_invoice(raw_text)
    except LLMUnavailableError as e:
        return _fail_to_manual_review(invoice_db_id, "extractor", str(e))

    with get_session() as db:
        invoice_row = db.get(Invoice, invoice_db_id)
        if extracted is None:
            invoice_row.status = InvoiceStatus.FAILED.value
            db.commit()
            _log(db, invoice_db_id, "extractor", settings.lmstudio_extractor_model,
                 raw_text[:500], "FAILED validation after retries", raw_output)
            return InvoiceStatus.FAILED.value

        vendor = db.query(Vendor).filter_by(name=extracted.vendor_name).one_or_none()
        if vendor is None:
            vendor = Vendor(name=extracted.vendor_name)
            db.add(vendor)
            db.flush()

        invoice_row.vendor_id = vendor.id
        invoice_row.vendor_name_raw = extracted.vendor_name
        invoice_row.invoice_number = extracted.invoice_number
        invoice_row.invoice_date = extracted.invoice_date
        invoice_row.due_date = extracted.due_date
        invoice_row.line_items_json = [li.model_dump(mode="json") for li in extracted.line_items]
        invoice_row.subtotal = extracted.subtotal
        invoice_row.tax = extracted.tax
        invoice_row.total = extracted.total
        invoice_row.currency = extracted.currency
        invoice_row.po_number = extracted.po_number
        invoice_row.status = InvoiceStatus.EXTRACTED.value
        db.commit()

        _log(db, invoice_db_id, "extractor", settings.lmstudio_extractor_model,
             raw_text[:500], extracted.model_dump_json(), raw_output)

    # --- 2. Matcher (deterministic) ---
    with get_session() as db:
        invoice_row = db.get(Invoice, invoice_db_id)
        po = None
        if extracted.po_number:
            po = db.query(PurchaseOrder).filter_by(po_number=extracted.po_number).one_or_none()

        match_result = match_invoice_to_po(extracted, po)
        invoice_row.match_status = match_result.status.value
        invoice_row.status = InvoiceStatus.MATCHED.value
        db.commit()

        _log(db, invoice_db_id, "matcher", None,
             f"po_number={extracted.po_number}", match_result.model_dump_json())

        # --- vendor history for the Reasoner ---
        vendor_history = (
            db.query(Invoice)
            .filter(Invoice.vendor_id == invoice_row.vendor_id, Invoice.id != invoice_db_id)
            .order_by(Invoice.created_at.desc())
            .limit(10)
            .all()
        )

    # --- 3. Anomaly Reasoner ---
    try:
        verdict, reasoner_raw = assess_invoice(extracted, match_result, vendor_history, low_confidence)
    except LLMUnavailableError as e:
        return _fail_to_manual_review(invoice_db_id, "reasoner", str(e))

    if verdict is None:
        return _fail_to_manual_review(invoice_db_id, "reasoner", "failed schema validation after retries")

    with get_session() as db:
        _log(db, invoice_db_id, "reasoner", settings.lmstudio_reasoner_model,
             f"invoice_total={extracted.total}, match_status={match_result.status.value}",
             f"verdict={verdict.verdict.value}, flags={verdict.risk_flags}", reasoner_raw)

    # --- 4. Explainer ---
    explanation = explain_verdict(verdict)
    with get_session() as db:
        _log(db, invoice_db_id, "explainer", settings.ollama_explainer_model,
             f"verdict={verdict.verdict.value}", explanation.summary)

    # --- 5. HITL Gate (deterministic) ---
    cleared = run_hitl_gate(invoice_db_id, float(extracted.total), verdict, explanation)
    with get_session() as db:
        _log(db, invoice_db_id, "hitl_gate", None,
             f"pre-gate verdict={verdict.verdict.value}",
             "cleared -> auto_approved" if cleared else "paused -> pending_human review_task created")

    if not cleared:
        # Send the approval-request email here — this is the point where
        # a human needs to act, via Streamlit or by replying to this email.
        with get_session() as db:
            invoice_row = db.get(Invoice, invoice_db_id)
            vendor = db.get(Vendor, invoice_row.vendor_id)
        try:
            email_service.send_approval_request(
                to_address=settings.gmail_address,  # replace with actual approver once routed
                invoice_id=invoice_db_id,
                vendor_name=vendor.name,
                amount=f"{extracted.total} {extracted.currency}",
                plain_english_note=explanation.summary,
            )
        except Exception:
            pass  # email failure shouldn't crash the pipeline; task is still queryable in the UI
        return InvoiceStatus.PENDING_HUMAN.value

    # --- 6. Router (only runs post-approval) ---
    return _run_router_and_finish(invoice_db_id, extracted)


def resume_after_human_review(invoice_db_id: int, approved: bool) -> str:
    """Called after a ReviewTask is resolved (either Streamlit button or
    email reply — see agents/hitl_gate.resolve_review_task, which is
    called first and updates invoice.status before this runs)."""
    if not approved:
        return InvoiceStatus.REJECTED.value

    with get_session() as db:
        invoice_row = db.get(Invoice, invoice_db_id)
        from schemas.models import ExtractedInvoice, LineItem
        extracted = ExtractedInvoice(
            vendor_name=invoice_row.vendor_name_raw,
            invoice_number=invoice_row.invoice_number,
            invoice_date=invoice_row.invoice_date,
            due_date=invoice_row.due_date,
            line_items=[LineItem.model_validate(li) for li in (invoice_row.line_items_json or [])],
            subtotal=invoice_row.subtotal,
            tax=invoice_row.tax,
            total=invoice_row.total,
            currency=invoice_row.currency or settings.currency_default,
            po_number=invoice_row.po_number,
        )

    return _run_router_and_finish(invoice_db_id, extracted)


def _run_router_and_finish(invoice_db_id: int, extracted) -> str:
    with get_session() as db:
        invoice_row = db.get(Invoice, invoice_db_id)
        vendor = db.get(Vendor, invoice_row.vendor_id) if invoice_row.vendor_id else None

    routing = route_invoice(extracted, vendor.default_department if vendor else None)

    with get_session() as db:
        invoice_row = db.get(Invoice, invoice_db_id)
        invoice_row.department = routing.department
        invoice_row.approver_email = routing.approver_email
        invoice_row.status = InvoiceStatus.ROUTED.value
        db.commit()

        _log(db, invoice_db_id, "router", settings.ollama_router_model,
             f"vendor={extracted.vendor_name}", routing.model_dump_json())

    try:
        email_service.send_vendor_confirmation(
            to_address=settings.gmail_address,  # placeholder recipient for MVP/demo
            invoice_id=invoice_db_id,
            vendor_name=extracted.vendor_name,
        )
    except Exception:
        pass

    return InvoiceStatus.ROUTED.value


def _fail_to_manual_review(invoice_db_id: int, agent_name: str, detail: str) -> str:
    with get_session() as db:
        invoice_row = db.get(Invoice, invoice_db_id)
        invoice_row.status = InvoiceStatus.FAILED.value
        db.commit()
        _log(db, invoice_db_id, agent_name, None, "", f"FAILED: {detail}")
    return InvoiceStatus.FAILED.value
