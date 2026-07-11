from __future__ import annotations

from db.models import Invoice, ReviewTask as ReviewTaskRow
from db.session import get_session
from config.settings import settings
from schemas.models import AgentVerdict, InvoiceStatus, PlainExplanation, Verdict


def apply_policy_ceiling(invoice_total: float, verdict: AgentVerdict) -> AgentVerdict:
    """Deterministic override — runs before the gate decision below."""
    if invoice_total > settings.auto_approve_max_amount and verdict.verdict == Verdict.AUTO_APPROVE:
        verdict.verdict = Verdict.NEEDS_REVIEW
        if "above_auto_approve_ceiling" not in verdict.risk_flags:
            verdict.risk_flags.append("above_auto_approve_ceiling")
    return verdict


def run_hitl_gate(
    invoice_db_id: int,
    invoice_total: float,
    verdict: AgentVerdict,
    explanation: PlainExplanation,
) -> bool:
    """Returns True if the invoice cleared the gate and can proceed to
    the Router immediately (auto_approve). Returns False if it now sits
    in review_tasks awaiting a human — the caller (pipeline) must stop
    processing this invoice for now."""
    final_verdict = apply_policy_ceiling(invoice_total, verdict)

    with get_session() as db:
        invoice = db.get(Invoice, invoice_db_id)
        invoice.verdict = final_verdict.verdict.value

        if final_verdict.verdict == Verdict.AUTO_APPROVE:
            invoice.status = InvoiceStatus.APPROVED.value
            db.commit()
            return True

        invoice.status = InvoiceStatus.PENDING_HUMAN.value
        review_task = ReviewTaskRow(
            invoice_id=invoice_db_id,
            reason=final_verdict.verdict.value,
            explanation_summary=explanation.summary,
            reasoning_chain=final_verdict.reasoning_chain,
            status="pending_human",
        )
        db.add(review_task)
        db.commit()
        return False


def resolve_review_task(
    review_task_id: int,
    resolution: str,           # "approved" | "rejected" | "edited_and_approved"
    resolved_by: str,
    channel: str,              # "streamlit" | "email_reply"
) -> None:
    """Called by either the Streamlit Approval Queue page or the email
    reply poller. Whichever path resolves it, the same audit fields get
    filled in — that symmetry is what the spec means by 'log who
    approved it and when, no matter which path was used.'"""
    from datetime import datetime

    with get_session() as db:
        task = db.get(ReviewTaskRow, review_task_id)
        task.status = "resolved"
        task.resolution = resolution
        task.resolved_by = resolved_by
        task.resolved_at = datetime.utcnow()
        task.resolution_channel = channel

        invoice = db.get(Invoice, task.invoice_id)
        invoice.status = (
            InvoiceStatus.APPROVED.value if resolution in ("approved", "edited_and_approved")
            else InvoiceStatus.REJECTED.value
        )
        db.commit()