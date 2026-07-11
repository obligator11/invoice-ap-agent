
import streamlit as st

from db.session import init_db

st.set_page_config(page_title="Invoice / AP Automation", page_icon="🧾", layout="wide")

if "db_initialized" not in st.session_state:
    init_db()
    st.session_state["db_initialized"] = True

st.title("🧾 Invoice / AP Automation Agent")
st.markdown(
    """
Welcome. Use the sidebar to navigate:

- **Upload / Inbox** — submit invoices for processing
- **Processing** — watch an invoice move through the agent pipeline live
- **Approval Queue** — resolve anything paused for human review
- **Ledger** — every invoice, its status, and its numbers
- **Audit Trail** — full reasoning chain for any invoice, from every agent
- **Settings** — models in use, auto-approve threshold, SLA hours

Everything here runs against **local models only** (Ollama + LM Studio) and a
**local PostgreSQL** database — no cloud AI calls in the core pipeline.
"""
)
