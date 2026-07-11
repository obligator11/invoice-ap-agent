"""
Seeds vendors + purchase_orders so the sample invoices in
sample_invoices/ have something real to match against.

Run: python scripts/seed_data.py   (after `streamlit run app.py` has
created the tables at least once, or call init_db() yourself first)
"""
from db.models import PurchaseOrder, Vendor
from db.session import get_session, init_db


def main():
    init_db()
    with get_session() as db:
        acme = db.query(Vendor).filter_by(name="Acme Supplies").one_or_none()
        if not acme:
            acme = Vendor(name="Acme Supplies", default_department="Office Ops")
            db.add(acme)
            db.flush()

        initech = db.query(Vendor).filter_by(name="Initech Hardware").one_or_none()
        if not initech:
            initech = Vendor(name="Initech Hardware", default_department="IT")
            db.add(initech)
            db.flush()

        if not db.query(PurchaseOrder).filter_by(po_number="PO-1001").one_or_none():
            db.add(PurchaseOrder(
                po_number="PO-1001",
                vendor_id=acme.id,
                line_items_json=[
                    {"description": "Widgets", "quantity": 100, "unit_price": 2.50},
                    {"description": "Shipping", "quantity": 1, "unit_price": 15.00},
                ],
                total_amount=265.00,
                currency="USD",
            ))

        if not db.query(PurchaseOrder).filter_by(po_number="PO-3001").one_or_none():
            db.add(PurchaseOrder(
                po_number="PO-3001",
                vendor_id=initech.id,
                line_items_json=[
                    {"description": "Server rack", "quantity": 2, "unit_price": 800.00},
                ],
                total_amount=1600.00,
                currency="USD",
            ))

        db.commit()
    print("Seed data inserted.")


if __name__ == "__main__":
    main()
