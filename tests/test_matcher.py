from decimal import Decimal
from datetime import date

from agents.matcher import match_invoice_to_po
from schemas.models import ExtractedInvoice, LineItem, MatchStatus


class FakePO:
    def __init__(self, po_number, line_items_json, total_amount):
        self.po_number = po_number
        self.line_items_json = line_items_json
        self.total_amount = total_amount


def _sample_invoice(total: str, unit_price: str) -> ExtractedInvoice:
    return ExtractedInvoice(
        vendor_name="Acme Supplies",
        invoice_number="INV-1001",
        invoice_date=date(2026, 6, 1),
        line_items=[
            LineItem(description="Widgets", quantity=Decimal(100), unit_price=Decimal(unit_price),
                     line_total=Decimal(unit_price) * 100)
        ],
        subtotal=Decimal(total),
        tax=Decimal("0"),
        total=Decimal(total),
        po_number="PO-1001",
    )


def test_exact_match():
    po = FakePO("PO-1001", [{"description": "Widgets", "quantity": 100, "unit_price": 2.50}], 250.00)
    invoice = _sample_invoice(total="250.00", unit_price="2.50")
    result = match_invoice_to_po(invoice, po)
    assert result.status == MatchStatus.MATCHED
    assert result.diffs == []


def test_price_mismatch():
    po = FakePO("PO-1001", [{"description": "Widgets", "quantity": 100, "unit_price": 2.50}], 250.00)
    invoice = _sample_invoice(total="300.00", unit_price="3.00")
    result = match_invoice_to_po(invoice, po)
    assert result.status in (MatchStatus.PARTIAL_MATCH, MatchStatus.MISMATCH)
    assert any(d.field == "unit_price" for d in result.diffs)


def test_no_po_found():
    invoice = _sample_invoice(total="250.00", unit_price="2.50")
    result = match_invoice_to_po(invoice, None)
    assert result.status == MatchStatus.NO_PO_FOUND
