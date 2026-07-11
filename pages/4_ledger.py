import pandas as pd
import streamlit as st

from db.models import Invoice
from db.session import get_session

st.header("Ledger")

with get_session() as db:
    rows = db.query(Invoice).order_by(Invoice.created_at.desc()).all()

    data = [
        {
            "ID": r.id,
            "Vendor": r.vendor_name_raw,
            "Invoice #": r.invoice_number,
            "Total": float(r.total) if r.total is not None else None,
            "Currency": r.currency,
            "Status": r.status,
            "Match": r.match_status,
            "Verdict": r.verdict,
            "Department": r.department,
            "Source": r.source_method,
            "Created": r.created_at,
        }
        for r in rows
    ]

df = pd.DataFrame(data)

col1, col2, col3 = st.columns(3)
status_filter = col1.multiselect("Status", options=sorted(df["Status"].dropna().unique()) if not df.empty else [])
vendor_filter = col2.multiselect("Vendor", options=sorted(df["Vendor"].dropna().unique()) if not df.empty else [])
verdict_filter = col3.multiselect("Verdict", options=sorted(df["Verdict"].dropna().unique()) if not df.empty else [])

filtered = df
if status_filter:
    filtered = filtered[filtered["Status"].isin(status_filter)]
if vendor_filter:
    filtered = filtered[filtered["Vendor"].isin(vendor_filter)]
if verdict_filter:
    filtered = filtered[filtered["Verdict"].isin(verdict_filter)]

st.dataframe(filtered, use_container_width=True, hide_index=True)
st.caption(f"{len(filtered)} of {len(df)} invoices shown.")
