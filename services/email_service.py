from __future__ import annotations

import imaplib
import email as email_lib
import re
import smtplib
from email.message import EmailMessage

from config.settings import settings


def _send(to_address: str, subject: str, body: str) -> None:
    msg = EmailMessage()
    msg["From"] = settings.gmail_address
    msg["To"] = to_address
    msg["Subject"] = subject
    msg.set_content(body)

    with smtplib.SMTP(settings.gmail_smtp_host, settings.gmail_smtp_port) as smtp:
        smtp.starttls()
        smtp.login(settings.gmail_address, settings.gmail_app_password)
        smtp.send_message(msg)


def send_approval_request(
    to_address: str,
    invoice_id: int,
    vendor_name: str,
    amount: str,
    plain_english_note: str,
) -> None:
    subject = f"[Action needed] Invoice #{invoice_id} from {vendor_name} — {amount}"
    body = (
        f"An invoice needs your review:\n\n"
        f"Vendor: {vendor_name}\n"
        f"Amount: {amount}\n"
        f"Invoice ID: {invoice_id}\n\n"
        f"Why it was flagged:\n{plain_english_note}\n\n"
        f"Reply to this email with APPROVE or REJECT to resolve it, "
        f"or use the Approval Queue page in the app for more detail."
    )
    _send(to_address, subject, body)


def send_vendor_confirmation(to_address: str, invoice_id: int, vendor_name: str) -> None:
    subject = f"Invoice #{invoice_id} approved"
    body = f"Hi {vendor_name},\n\nYour invoice #{invoice_id} has been approved for payment."
    _send(to_address, subject, body)


def send_escalation(to_address: str, invoice_id: int, hours_pending: float) -> None:
    subject = f"[SLA breach] Invoice #{invoice_id} unresolved for {hours_pending:.0f}h"
    body = (
        f"Invoice #{invoice_id} has been sitting in the review queue for "
        f"{hours_pending:.0f} hours, past the {settings.review_sla_hours}h SLA. "
        f"Please resolve it in the Approval Queue."
    )
    _send(to_address, subject, body)


_APPROVE_RE = re.compile(r"\bAPPROVE\b", re.IGNORECASE)
_REJECT_RE = re.compile(r"\bREJECT\b", re.IGNORECASE)


def poll_for_approval_replies() -> list[dict]:
    """Checks the inbox for unread replies containing APPROVE/REJECT.

    Returns a list of dicts: {"from": ..., "invoice_id": ..., "decision": "approved"|"rejected"}
    Matching an invoice_id back from a reply is done via the subject line
    convention `Invoice #<id>` that send_approval_request uses — keep that
    convention if you change the subject format.
    """
    results: list[dict] = []
    with imaplib.IMAP4_SSL(settings.gmail_imap_host) as imap:
        imap.login(settings.gmail_address, settings.gmail_app_password)
        imap.select("INBOX")
        status, data = imap.search(None, "UNSEEN")
        if status != "OK":
            return results

        for num in data[0].split():
            status, msg_data = imap.fetch(num, "(RFC822)")
            if status != "OK":
                continue
            msg = email_lib.message_from_bytes(msg_data[0][1])
            subject = msg.get("Subject", "")
            from_addr = email_lib.utils.parseaddr(msg.get("From", ""))[1]

            body_text = _extract_plain_body(msg)
            invoice_match = re.search(r"Invoice #(\d+)", subject)
            if not invoice_match:
                continue
            invoice_id = int(invoice_match.group(1))

            if _APPROVE_RE.search(body_text):
                results.append({"from": from_addr, "invoice_id": invoice_id, "decision": "approved"})
            elif _REJECT_RE.search(body_text):
                results.append({"from": from_addr, "invoice_id": invoice_id, "decision": "rejected"})

    return results


def _extract_plain_body(msg: email_lib.message.Message) -> str:
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                return part.get_payload(decode=True).decode(errors="ignore")
        return ""
    return msg.get_payload(decode=True).decode(errors="ignore")
