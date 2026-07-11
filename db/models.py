from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Column, Integer, String, Numeric, Date, DateTime, Text, Boolean,
    ForeignKey, JSON,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Vendor(Base):
    __tablename__ = "vendors"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False, unique=True)
    default_department = Column(String(100), nullable=True)
    bank_account_last4 = Column(String(8), nullable=True)   # for "changed bank details" anomaly check
    created_at = Column(DateTime, default=datetime.utcnow)

    invoices = relationship("Invoice", back_populates="vendor")
    purchase_orders = relationship("PurchaseOrder", back_populates="vendor")


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"

    id = Column(Integer, primary_key=True)
    po_number = Column(String(100), nullable=False, unique=True, index=True)
    vendor_id = Column(Integer, ForeignKey("vendors.id"), nullable=False)
    line_items_json = Column(JSON, nullable=False)   # [{description, quantity, unit_price}, ...]
    total_amount = Column(Numeric(12, 2), nullable=False)
    currency = Column(String(3), default="USD")
    created_at = Column(DateTime, default=datetime.utcnow)

    vendor = relationship("Vendor", back_populates="purchase_orders")


class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True)

    # --- ingestion metadata ---
    source_method = Column(String(50), nullable=False)   # SourceMethod enum value
    source_filename = Column(String(500), nullable=True)
    raw_text = Column(Text, nullable=True)                # what OCR/pdfplumber produced

    # --- extracted fields (nullable until Extractor Agent runs) ---
    vendor_id = Column(Integer, ForeignKey("vendors.id"), nullable=True)
    vendor_name_raw = Column(String(255), nullable=True)   # as-extracted, pre-vendor-match
    invoice_number = Column(String(100), nullable=True, index=True)
    invoice_date = Column(Date, nullable=True)
    due_date = Column(Date, nullable=True)
    line_items_json = Column(JSON, nullable=True)
    subtotal = Column(Numeric(12, 2), nullable=True)
    tax = Column(Numeric(12, 2), nullable=True)
    total = Column(Numeric(12, 2), nullable=True)
    currency = Column(String(3), nullable=True)
    po_number = Column(String(100), nullable=True)

    # --- pipeline state ---
    status = Column(String(50), nullable=False, default="ingested")   # InvoiceStatus enum value
    match_status = Column(String(50), nullable=True)                   # MatchStatus enum value
    verdict = Column(String(50), nullable=True)                        # Verdict enum value
    department = Column(String(100), nullable=True)
    approver_email = Column(String(255), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    vendor = relationship("Vendor", back_populates="invoices")
    review_tasks = relationship("ReviewTask", back_populates="invoice")
    audit_entries = relationship("AuditLogEntry", back_populates="invoice")


class ReviewTask(Base):
    __tablename__ = "review_tasks"

    id = Column(Integer, primary_key=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=False)

    reason = Column(String(50), nullable=False)              # Verdict enum value that triggered it
    explanation_summary = Column(Text, nullable=False)       # Explainer Agent's plain-English note
    reasoning_chain = Column(Text, nullable=False)            # Reasoner Agent's raw chain

    status = Column(String(20), nullable=False, default="pending_human")  # pending_human | resolved
    resolution = Column(String(50), nullable=True)             # ReviewResolution enum value
    resolved_by = Column(String(255), nullable=True)           # human identity or "email:<address>"
    resolved_at = Column(DateTime, nullable=True)
    resolution_channel = Column(String(20), nullable=True)     # "streamlit" | "email_reply"

    created_at = Column(DateTime, default=datetime.utcnow)

    invoice = relationship("Invoice", back_populates="review_tasks")


class AuditLogEntry(Base):
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=False)

    agent_name = Column(String(50), nullable=False)
    model_used = Column(String(100), nullable=True)   # null for deterministic agents (Matcher, HITL Gate)
    input_summary = Column(Text, nullable=False)
    output_summary = Column(Text, nullable=False)
    raw_output = Column(Text, nullable=True)           # unabridged reasoning/JSON for the audit panel

    timestamp = Column(DateTime, default=datetime.utcnow)

    invoice = relationship("Invoice", back_populates="audit_entries")
