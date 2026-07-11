import streamlit as st

from config.settings import settings
from services.llm_clients import list_ollama_models, list_lmstudio_models, LLMUnavailableError

st.header("Settings")

st.subheader("Detected local models")
col1, col2 = st.columns(2)

with col1:
    st.markdown("**Ollama**")
    try:
        ollama_models = list_ollama_models()
        st.success(f"Reachable — {len(ollama_models)} model(s) found")
        st.session_state["ollama_explainer_model"] = st.selectbox(
            "Explainer model", options=ollama_models,
            index=ollama_models.index(settings.ollama_explainer_model) if settings.ollama_explainer_model in ollama_models else 0,
        )
        st.session_state["ollama_router_model"] = st.selectbox(
            "Router model", options=ollama_models,
            index=ollama_models.index(settings.ollama_router_model) if settings.ollama_router_model in ollama_models else 0,
        )
    except LLMUnavailableError as e:
        st.error(f"Ollama unreachable: {e.detail}")

with col2:
    st.markdown("**LM Studio**")
    try:
        lmstudio_models = list_lmstudio_models()
        st.success(f"Reachable — {len(lmstudio_models)} model(s) found")
        st.session_state["lmstudio_extractor_model"] = st.selectbox(
            "Extractor model", options=lmstudio_models,
            index=lmstudio_models.index(settings.lmstudio_extractor_model) if settings.lmstudio_extractor_model in lmstudio_models else 0,
        )
        st.session_state["lmstudio_reasoner_model"] = st.selectbox(
            "Reasoner model", options=lmstudio_models,
            index=lmstudio_models.index(settings.lmstudio_reasoner_model) if settings.lmstudio_reasoner_model in lmstudio_models else 0,
        )
    except LLMUnavailableError as e:
        st.error(f"LM Studio unreachable: {e.detail}")

st.divider()
st.subheader("Business rules")

new_ceiling = st.number_input(
    "Auto-approve ceiling ($) — anything above this ALWAYS requires human review",
    value=settings.auto_approve_max_amount, min_value=0.0, step=50.0,
)
new_sla = st.number_input(
    "Review SLA (hours) before an escalation email is sent",
    value=float(settings.review_sla_hours), min_value=1.0, step=1.0,
)

if st.button("Apply for this session"):
    settings.auto_approve_max_amount = new_ceiling
    settings.review_sla_hours = int(new_sla)
    st.success("Applied. (Restart the app and update .env to persist these across restarts.)")

st.caption(
    "TODO for production use: write these values back to .env or a DB-backed "
    "settings table so they survive a restart, instead of living only in "
    "the in-memory settings singleton for this session."
)
