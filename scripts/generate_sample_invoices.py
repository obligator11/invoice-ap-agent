"""
Generates 9 synthetic files into sample_invoices/, covering every
ingestion path the spec calls for:

  1. clean_native_pdf_acme.pdf        — clean native-text PDF, matches its PO exactly
  2. native_pdf_price_mismatch.pdf    — native PDF, unit price differs from PO
  3. native_pdf_no_po.pdf             — native PDF, no PO number at all
  4. native_pdf_duplicate_invoice.pdf — same invoice_number as file #1 (dup check)
  5. scanned_blurry_rotated.pdf       — image-based PDF (deliberately low quality, rotated)
  6. photo_receipt.jpg                — standalone photo, same content as a normal invoice
  7. round_number_invoice.pdf         — suspicious exact round-number total
  8. forwarded_email.eml              — .eml with a PDF attachment
  9. just_under_threshold.pdf         — total priced just under the auto-approve ceiling

Run: python scripts/generate_sample_invoices.py
"""
import os
import random
from email.message import EmailMessage

from fpdf import FPDF
from PIL import Image, ImageDraw, ImageFont

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "sample_invoices")
os.makedirs(OUT_DIR, exist_ok=True)


def _invoice_text(vendor, invoice_number, date, due_date, items, subtotal, tax, total, po_number=None):
    lines = [
        f"INVOICE",
        f"Vendor: {vendor}",
        f"Invoice #: {invoice_number}",
        f"Date: {date}    Due: {due_date}",
    ]
    if po_number:
        lines.append(f"PO Number: {po_number}")
    lines.append("")
    lines.append("Description         Qty   Unit Price   Line Total")
    for desc, qty, price, line_total in items:
        lines.append(f"{desc:<20}{qty:<6}{price:<13}{line_total}")
    lines.append("")
    lines.append(f"Subtotal: {subtotal}")
    lines.append(f"Tax: {tax}")
    lines.append(f"Total: {total}")
    return "\n".join(lines)


def _write_pdf(filename: str, text: str, rotate: bool = False, blurry: bool = False):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    for line in text.split("\n"):
        pdf.cell(0, 8, line, ln=True)
    path = os.path.join(OUT_DIR, filename)
    pdf.output(path)
    return path


def _write_scanned_style_pdf(filename: str, text: str):
    """Renders text onto an image (simulating a photographed page), then
    wraps that image in a PDF with no embedded text layer — so
    pdfplumber/PyMuPDF find near-zero real text and the ingestion
    dispatcher correctly routes it to OCR."""
    img = Image.new("RGB", (1000, 1400), color=(235, 235, 230))  # slightly off-white, like a scan
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 22)
    except Exception:
        font = ImageFont.load_default()

    y = 60
    for line in text.split("\n"):
        draw.text((60, y), line, fill=(30, 30, 30), font=font)
        y += 34

    img = img.rotate(random.uniform(-3, 3), expand=True, fillcolor=(235, 235, 230))
    img = img.filter(__import__("PIL.ImageFilter", fromlist=["GaussianBlur"]).GaussianBlur(1.2))

    path = os.path.join(OUT_DIR, filename)
    img.convert("RGB").save(path, "PDF")
    return path


def _write_photo(filename: str, text: str):
    img = Image.new("RGB", (900, 1100), color=(240, 240, 235))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 24)
    except Exception:
        font = ImageFont.load_default()
    y = 50
    for line in text.split("\n"):
        draw.text((50, y), line, fill=(20, 20, 20), font=font)
        y += 36
    path = os.path.join(OUT_DIR, filename)
    img.save(path)
    return path


def main():
    # 1. Clean native PDF — matches PO-1001 exactly (create this PO in seed data too)
    text1 = _invoice_text(
        "Acme Supplies", "INV-1001", "2026-06-01", "2026-06-15",
        [("Widgets", 100, "2.50", "250.00"), ("Shipping", 1, "15.00", "15.00")],
        "265.00", "0.00", "265.00", po_number="PO-1001",
    )
    _write_pdf("clean_native_pdf_acme.pdf", text1)

    # 2. Native PDF with a price mismatch vs the same PO
    text2 = _invoice_text(
        "Acme Supplies", "INV-1002", "2026-06-02", "2026-06-16",
        [("Widgets", 100, "3.00", "300.00"), ("Shipping", 1, "15.00", "15.00")],
        "315.00", "0.00", "315.00", po_number="PO-1001",
    )
    _write_pdf("native_pdf_price_mismatch.pdf", text2)

    # 3. Native PDF, no PO at all
    text3 = _invoice_text(
        "Globex Consulting", "INV-2001", "2026-06-03", "2026-06-17",
        [("Strategy consulting", 10, "150.00", "1500.00")],
        "1500.00", "0.00", "1500.00",
    )
    _write_pdf("native_pdf_no_po.pdf", text3)

    # 4. Duplicate invoice number of #1 (same vendor, same invoice_number)
    _write_pdf("native_pdf_duplicate_invoice.pdf", text1.replace("INV-1001", "INV-1001"))

    # 5. Scanned/blurry/rotated version of a normal invoice (needs OCR)
    text5 = _invoice_text(
        "Initech Hardware", "INV-3001", "2026-06-04", "2026-06-18",
        [("Server rack", 2, "800.00", "1600.00")],
        "1600.00", "0.00", "1600.00", po_number="PO-3001",
    )
    _write_scanned_style_pdf("scanned_blurry_rotated.pdf", text5)

    # 6. Standalone photo of a receipt
    text6 = _invoice_text(
        "Corner Cafe Catering", "INV-4001", "2026-06-05", "2026-06-05",
        [("Lunch catering", 1, "180.00", "180.00")],
        "180.00", "0.00", "180.00",
    )
    _write_photo("photo_receipt.jpg", text6)

    # 7. Suspicious round-number invoice
    text7 = _invoice_text(
        "Umbrella Logistics", "INV-5001", "2026-06-06", "2026-06-20",
        [("Freight services", 1, "5000.00", "5000.00")],
        "5000.00", "0.00", "5000.00",
    )
    _write_pdf("round_number_invoice.pdf", text7)

    # 8. Forwarded email with a PDF attachment
    pdf_path = _write_pdf("email_attachment_source.pdf", text3)
    msg = EmailMessage()
    msg["From"] = "vendor@globex.example.com"
    msg["To"] = "ap-inbox@company.example.com"
    msg["Subject"] = "Fwd: Invoice INV-2001 from Globex Consulting"
    msg.set_content("Please see attached invoice.")
    with open(pdf_path, "rb") as f:
        msg.add_attachment(f.read(), maintype="application", subtype="pdf", filename="invoice_2001.pdf")
    with open(os.path.join(OUT_DIR, "forwarded_email.eml"), "wb") as f:
        f.write(bytes(msg))

    # 9. Just under the default $500 auto-approve ceiling
    text9 = _invoice_text(
        "Acme Supplies", "INV-1003", "2026-06-07", "2026-06-21",
        [("Widgets", 199, "2.50", "497.50")],
        "497.50", "0.00", "497.50", po_number="PO-1001",
    )
    _write_pdf("just_under_threshold.pdf", text9)

    print(f"Generated 9 sample files in {os.path.abspath(OUT_DIR)}")


if __name__ == "__main__":
    main()
