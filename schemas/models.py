
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator



class SourceMethod(str, Enum):
    NATIVE_PDF = "native_pdf"
    OCR_SCAN = "ocr_scan"
    OCR_PHOTO = "ocr_photo"
    EMAIL_ATTACHMENT = "email_attachment"
    OFFICE_DOC = "office_doc"


class MatchStatus(str, Enum):
    MATCHED = "matched"
    PARTIAL_MATCH = "partial_match"
    NO_PO_FOUND = "no_po_found"
    MISMATCH = "mismatch"


class Verdict(str, Enum):
    AUTO_APPROVE = "auto_approve"
    NEEDS_REVIEW = "needs_review"
    REJECT = "reject"


class InvoiceStatus(str, Enum):
    INGESTED = "ingested"
    EXTRACTED = "extracted"
    MATCHED = "matched"
    REASONED = "reasoned"
    PENDING_HUMAN = "pending_human"
    APPROVED = "approved"
    REJECTED = "rejected"
    ROUTED = "routed"
    PAID = "paid"
    FAILED = "failed"


class ReviewResolution(str, Enum):
    APPROVED = "approved"
    REJECTED = "rejected"
    EDITED_AND_APPROVED = "edited_and_approved"



class LineItem(BaseModel):
    description: str
    quantity: Decimal = Field(gt=0)
    unit_price: Decimal = Field(ge=0)
    line_total: Decimal = Field(ge=0)

    @field_validator("line_total")
    @classmethod
    def check_line_math(cls, v: Decimal, info) -> Decimal:
        # Loose tolerance for rounding, not exact equality
        qty = info.data.get("quantity")
        price = info.data.get("unit_price")
        if qty is not None and price is not None:
            expected = qty * price
            if abs(expected - v) > Decimal("0.05"):
                raise ValueError(
                    f"line_total {v} doesn't match quantity*unit_price {expected}"
                )
        return v


class ExtractedInvoice(BaseModel):
    """Strict schema the Extractor Agent's JSON output must satisfy."""

    vendor_name: str
    invoice_number: str
    invoice_date: date
    due_date: Optional[date] = None
    line_items: list[LineItem] = Field(default_factory=list)
    subtotal: Decimal
    tax: Decimal = Decimal("0")
    total: Decimal
    currency: str = "USD"
    po_number: Optional[str] = None

    @field_validator("total")
    @classmethod
    def check_total_math(cls, v: Decimal, info) -> Decimal:
        subtotal = info.data.get("subtotal")
        tax = info.data.get("tax", Decimal("0"))
        if subtotal is not None:
            expected = subtotal + tax
            if abs(expected - v) > Decimal("0.05"):
                raise ValueError(f"total {v} != subtotal+tax {expected}")
        return v



class LineDiff(BaseModel):
    field: str                 
    line_description: str
    po_value: Optional[str] = None
    invoice_value: Optional[str] = None


class MatchResult(BaseModel):
    status: MatchStatus
    po_number: Optional[str] = None
    diffs: list[LineDiff] = Field(default_factory=list)
    notes: Optional[str] = None



class AgentVerdict(BaseModel):
    verdict: Verdict
    reasoning_chain: str        
    risk_flags: list[str] = Field(default_factory=list)  
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)



class PlainExplanation(BaseModel):
    summary: str                 
    based_on_verdict: Verdict



class ReviewTask(BaseModel):
    invoice_id: int
    reason: Verdict
    explanation_summary: str
    reasoning_chain: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    resolved: bool = False
    resolution: Optional[ReviewResolution] = None
    resolved_by: Optional[str] = None
    resolved_at: Optional[datetime] = None
    resolution_channel: Optional[str] = None  # "streamlit" | "email_reply"


class RoutingDecision(BaseModel):
    department: str
    approver_email: str
    rationale: str



class AuditLogEntry(BaseModel):
    model_config = {"protected_namespaces": ()}

    invoice_id: int
    agent_name: str             # "extractor" | "matcher" | "reasoner" | "explainer" | "hitl_gate" | "router"
    model_used: Optional[str] = None   # None for deterministic agents
    input_summary: str
    output_summary: str
    raw_output: Optional[str] = None   # full reasoning / JSON, unabridged
    timestamp: datetime = Field(default_factory=datetime.utcnow)
