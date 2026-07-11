import streamlit as st

from db.models import Invoice, ReviewTask
from db.session import get_session
from agents.hitl_gate import resolve_review_task
from pipeline.orchestrator import resume_after_human_review
from services.email_service import poll_for_approval_replies

st.header("Approval Queue")

if st.button("📥 Check email replies"):
    try:
        replies = poll_for_approval_replies()
    except Exception as e:
        st.error(f"Could not check email: {e}")
    else:
        with get_session() as db:
            for reply in replies:
                task = (
                    db.query(ReviewTask)
                    .filter_by(invoice_id=reply["invoice_id"], status="pending_human")
                    .one_or_none()
                )
                if task:
                    resolve_review_task(
                        task.id, reply["decision"], resolved_by=f"email:{reply['from']}", channel="email_reply"
                    )
                    resume_after_human_review(reply["invoice_id"], approved=(reply["decision"] == "approved"))
        st.success(f"Resolved {len(replies)} task(s) from email replies.")
        st.rerun()

st.divider()

with get_session() as db:
    pending = (
        db.query(ReviewTask)
        .filter_by(status="pending_human")
        .order_by(ReviewTask.created_at.asc())
        .all()
    )

    if not pending:
        st.info("Nothing waiting for review right now. 🎉")

    for task in pending:
        invoice = db.get(Invoice, task.invoice_id)

        with st.container(border=True):
            st.markdown(f"### Invoice #{invoice.id} — {invoice.vendor_name_raw or 'Unknown vendor'}")
            st.markdown(f"**Amount:** {invoice.total} {invoice.currency}  |  **Reason:** `{task.reason}`")

            st.info(f"**Why it was flagged:** {task.explanation_summary}")

            with st.expander("Show full reasoning chain (raw)"):
                st.text(task.reasoning_chain)

            approver_name = st.text_input(
                "Your name (for the audit log)", key=f"name_{task.id}", value="reviewer"
            )

            c1, c2, c3 = st.columns(3)
            if c1.button("✅ Approve", key=f"approve_{task.id}"):
                resolve_review_task(task.id, "approved", approver_name, "streamlit")
                resume_after_human_review(invoice.id, approved=True)
                st.rerun()
            if c2.button("❌ Reject", key=f"reject_{task.id}"):
                resolve_review_task(task.id, "rejected", approver_name, "streamlit")
                resume_after_human_review(invoice.id, approved=False)
                st.rerun()
            if c3.button("✏️ Edit & Approve", key=f"edit_{task.id}"):
                st.session_state[f"editing_{task.id}"] = True

            if st.session_state.get(f"editing_{task.id}"):
                new_total = st.number_input(
                    "Corrected total", value=float(invoice.total), key=f"newtotal_{task.id}"
                )
                if st.button("Confirm corrected approval", key=f"confirmedit_{task.id}"):
                    invoice.total = new_total
                    db.commit()
                    resolve_review_task(task.id, "edited_and_approved", approver_name, "streamlit")
                    resume_after_human_review(invoice.id, approved=True)
                    st.rerun()
