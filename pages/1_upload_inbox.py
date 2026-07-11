import tempfile
import os

import streamlit as st

from db.models import Invoice
from db.session import get_session
from ingestion.dispatch import ingest_file, ingest_bytes
from ingestion.email_parser import parse_eml_file, poll_inbox_for_invoice_emails
from pipeline.orchestrator import process_invoice


def _create_invoice_row(raw_text: str, source_method: str, filename: str) -> int:
    with get_session() as db:
        invoice = Invoice(raw_text=raw_text, source_method=source_method, source_filename=filename, status="ingested")
        db.add(invoice)
        db.commit()
        db.refresh(invoice)
        return invoice.id


st.header("Upload / Inbox")

st.subheader("Upload a file")
uploaded = st.file_uploader(
    "Drop a PDF, image (.jpg/.png), or forwarded email (.eml)",
    type=["pdf", "jpg", "jpeg", "png", "eml"],
)

if uploaded is not None and st.button("Process this file"):
    with st.spinner("Ingesting and running the agent pipeline..."):
        suffix = os.path.splitext(uploaded.name)[1]
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(uploaded.getvalue())
            tmp_path = tmp.name

        try:
            if suffix.lower() == ".eml":
                attachments = parse_eml_file(tmp_path)
                if not attachments:
                    st.warning("No attachments found in this .eml file.")
                else:
                    for att in attachments:
                        result = ingest_bytes(att.content, att.filename)
                        invoice_id = _create_invoice_row(result.raw_text, result.source_method.value, att.filename)
                        status = process_invoice(invoice_id)
                        st.success(f"{att.filename} -> Invoice #{invoice_id}: {status}")
            else:
                result = ingest_file(tmp_path, original_filename=uploaded.name)
                invoice_id = _create_invoice_row(result.raw_text, result.source_method.value, uploaded.name)
                status = process_invoice(invoice_id)
                st.success(f"Invoice #{invoice_id} processed -> status: **{status}**")
                if status == "pending_human":
                    st.info("This invoice needs human review — see the Approval Queue page.")
        finally:
            os.unlink(tmp_path)


st.divider()
st.subheader("Check inbox")
st.caption("Polls the configured Gmail inbox for unread emails with invoice attachments.")

if st.button("Check inbox now"):
    with st.spinner("Polling inbox..."):
        try:
            attachments = poll_inbox_for_invoice_emails()
        except Exception as e:
            st.error(f"Could not reach inbox: {e}")
        else:
            if not attachments:
                st.info("No new invoice emails found.")
            for att in attachments:
                result = ingest_bytes(att.content, att.filename)
                invoice_id = _create_invoice_row(result.raw_text, result.source_method.value, att.filename)
                status = process_invoice(invoice_id)
                st.success(f"{att.filename} -> Invoice #{invoice_id}: {status}")