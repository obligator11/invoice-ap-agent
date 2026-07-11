import streamlit as st

from db.models import AuditLogEntry, Invoice, ReviewTask
from db.session import get_session

st.header("Audit Trail")

with get_session() as db:
    invoices = db.query(Invoice).order_by(Invoice.created_at.desc()).all()
    options = {f"#{i.id} — {i.vendor_name_raw or 'unknown'} ({i.status})": i.id for i in invoices}

if not options:
    st.info("No invoices yet.")
else:
    choice = st.selectbox("Select an invoice", options=list(options.keys()))
    invoice_id = options[choice]

    with get_session() as db:
        invoice = db.get(Invoice, invoice_id)
        entries = (
            db.query(AuditLogEntry)
            .filter_by(invoice_id=invoice_id)
            .order_by(AuditLogEntry.timestamp.asc())
            .all()
        )
        review_tasks = db.query(ReviewTask).filter_by(invoice_id=invoice_id).all()

        st.subheader(f"Invoice #{invoice.id} — {invoice.vendor_name_raw}")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total", f"{invoice.total} {invoice.currency}" if invoice.total else "—")
        c2.metric("Status", invoice.status)
        c3.metric("Match", invoice.match_status or "—")
        c4.metric("Verdict", invoice.verdict or "—")

        st.divider()
        st.markdown("### Timeline")
        for entry in entries:
            with st.expander(
                f"🕒 {entry.timestamp.strftime('%Y-%m-%d %H:%M:%S')} — **{entry.agent_name}**"
                + (f" (`{entry.model_used}`)" if entry.model_used else " (deterministic)")
            ):
                st.markdown(f"**Input:** {entry.input_summary}")
                st.markdown(f"**Output:** {entry.output_summary}")
                if entry.raw_output:
                    st.text_area("Raw model output", entry.raw_output, height=150, key=f"raw_{entry.id}")

        if review_tasks:
            st.divider()
            st.markdown("### Human review")
            for task in review_tasks:
                st.markdown(
                    f"- **{task.status}** — reason: `{task.reason}` — "
                    + (
                        f"resolved by **{task.resolved_by}** via `{task.resolution_channel}` "
                        f"at {task.resolved_at} → **{task.resolution}**"
                        if task.status == "resolved" else "still pending"
                    )
                )
