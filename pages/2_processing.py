import streamlit as st

from db.models import AuditLogEntry, Invoice
from db.session import get_session

st.header("Processing")
st.caption("Each invoice's current pipeline stage. Refresh to update.")

STAGE_ORDER = ["extractor", "matcher", "reasoner", "explainer", "hitl_gate", "router"]

with get_session() as db:
    invoices = db.query(Invoice).order_by(Invoice.created_at.desc()).limit(25).all()

    for inv in invoices:
        completed_stages = {
            e.agent_name for e in
            db.query(AuditLogEntry).filter_by(invoice_id=inv.id).all()
        }

        with st.container(border=True):
            cols = st.columns([1, 2, 3, 2])
            cols[0].markdown(f"**#{inv.id}**")
            cols[1].markdown(inv.vendor_name_raw or "*(not yet extracted)*")
            status_emoji = {
                "pending_human": "⏸️",
                "failed": "❌",
                "routed": "✅",
                "approved": "✅",
                "rejected": "🚫",
            }.get(inv.status, "🔄")
            cols[2].markdown(f"{status_emoji} `{inv.status}`")
            cols[3].markdown(f"source: `{inv.source_method}`")

            stage_line = "  →  ".join(
                f"✅{s}" if s in completed_stages else f"⬜{s}" for s in STAGE_ORDER
            )
            st.caption(stage_line)

            if inv.status == "pending_human":
                st.warning("Paused — awaiting human review. See Approval Queue.")

if not invoices:
    st.info("No invoices yet — go to Upload / Inbox to submit one.")
