from __future__ import annotations

import email as email_lib
import imaplib
from dataclasses import dataclass

from config.settings import settings


@dataclass
class EmailAttachment:
    filename: str
    content: bytes


def parse_eml_file(filepath: str) -> list[EmailAttachment]:
    with open(filepath, "rb") as f:
        msg = email_lib.message_from_binary_file(f)
    return _extract_attachments(msg)


def poll_inbox_for_invoice_emails(label_or_folder: str = "INBOX") -> list[EmailAttachment]:
    """Pulls attachments from unread emails in the given folder. Intended
    to be called on a schedule (cron / background thread) or via the
    Streamlit 'Check inbox' button."""
    attachments: list[EmailAttachment] = []
    with imaplib.IMAP4_SSL(settings.gmail_imap_host) as imap:
        imap.login(settings.gmail_address, settings.gmail_app_password)
        imap.select(label_or_folder)
        status, data = imap.search(None, "UNSEEN")
        if status != "OK":
            return attachments

        for num in data[0].split():
            status, msg_data = imap.fetch(num, "(RFC822)")
            if status != "OK":
                continue
            msg = email_lib.message_from_bytes(msg_data[0][1])
            attachments.extend(_extract_attachments(msg))

    return attachments


def _extract_attachments(msg: email_lib.message.Message) -> list[EmailAttachment]:
    results: list[EmailAttachment] = []
    for part in msg.walk():
        content_disposition = part.get_content_disposition()
        if content_disposition != "attachment":
            continue
        filename = part.get_filename()
        if not filename:
            continue
        payload = part.get_payload(decode=True)
        if payload:
            results.append(EmailAttachment(filename=filename, content=payload))
    return results
