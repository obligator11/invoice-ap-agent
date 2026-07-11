from __future__ import annotations

from decimal import Decimal

from db.models import PurchaseOrder
from schemas.models import ExtractedInvoice, LineDiff, MatchResult, MatchStatus

_AMOUNT_TOLERANCE = Decimal("0.02")


def match_invoice_to_po(invoice: ExtractedInvoice, po: PurchaseOrder | None) -> MatchResult:
    if po is None:
        return MatchResult(
            status=MatchStatus.NO_PO_FOUND,
            po_number=invoice.po_number,
            notes="No purchase order found with this number." if invoice.po_number
                  else "Invoice has no PO number at all.",
        )

    diffs: list[LineDiff] = []

    # --- total amount check ---
    po_total = Decimal(str(po.total_amount))
    if abs(po_total - invoice.total) > _AMOUNT_TOLERANCE:
        diffs.append(
            LineDiff(
                field="total_amount",
                line_description="(invoice total)",
                po_value=str(po_total),
                invoice_value=str(invoice.total),
            )
        )

    # --- line item checks ---
    po_items = {item["description"].strip().lower(): item for item in po.line_items_json}
    for inv_item in invoice.line_items:
        key = inv_item.description.strip().lower()
        po_item = po_items.get(key)
        if po_item is None:
            diffs.append(
                LineDiff(
                    field="line_item",
                    line_description=inv_item.description,
                    po_value=None,
                    invoice_value=f"qty={inv_item.quantity}, price={inv_item.unit_price}",
                )
            )
            continue

        if Decimal(str(po_item["quantity"])) != inv_item.quantity:
            diffs.append(
                LineDiff(
                    field="quantity",
                    line_description=inv_item.description,
                    po_value=str(po_item["quantity"]),
                    invoice_value=str(inv_item.quantity),
                )
            )
        if abs(Decimal(str(po_item["unit_price"])) - inv_item.unit_price) > _AMOUNT_TOLERANCE:
            diffs.append(
                LineDiff(
                    field="unit_price",
                    line_description=inv_item.description,
                    po_value=str(po_item["unit_price"]),
                    invoice_value=str(inv_item.unit_price),
                )
            )

    if not diffs:
        return MatchResult(status=MatchStatus.MATCHED, po_number=po.po_number)

    # Some line items matched fine, some didn't -> partial. If every
    # comparable field is off, call it a full mismatch instead.
    total_comparable_fields = len(invoice.line_items) + 1  # +1 for total_amount
    status = MatchStatus.MISMATCH if len(diffs) >= total_comparable_fields else MatchStatus.PARTIAL_MATCH

    return MatchResult(status=status, po_number=po.po_number, diffs=diffs)
