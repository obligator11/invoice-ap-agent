-- Reference SQL — equivalent to db/models.py, kept here so you have a
-- versioned starting point for Alembic (`alembic revision --autogenerate`
-- will produce something close to this once models.py is the source of
-- truth). Run manually only if you're not using init_db()/Alembic.

CREATE TABLE IF NOT EXISTS vendors (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    default_department VARCHAR(100),
    bank_account_last4 VARCHAR(8),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS purchase_orders (
    id SERIAL PRIMARY KEY,
    po_number VARCHAR(100) NOT NULL UNIQUE,
    vendor_id INTEGER NOT NULL REFERENCES vendors(id),
    line_items_json JSONB NOT NULL,
    total_amount NUMERIC(12,2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'USD',
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_po_number ON purchase_orders(po_number);

CREATE TABLE IF NOT EXISTS invoices (
    id SERIAL PRIMARY KEY,
    source_method VARCHAR(50) NOT NULL,
    source_filename VARCHAR(500),
    raw_text TEXT,

    vendor_id INTEGER REFERENCES vendors(id),
    vendor_name_raw VARCHAR(255),
    invoice_number VARCHAR(100),
    invoice_date DATE,
    due_date DATE,
    line_items_json JSONB,
    subtotal NUMERIC(12,2),
    tax NUMERIC(12,2),
    total NUMERIC(12,2),
    currency VARCHAR(3),
    po_number VARCHAR(100),

    status VARCHAR(50) NOT NULL DEFAULT 'ingested',
    match_status VARCHAR(50),
    verdict VARCHAR(50),
    department VARCHAR(100),
    approver_email VARCHAR(255),

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_invoice_number ON invoices(invoice_number);

CREATE TABLE IF NOT EXISTS review_tasks (
    id SERIAL PRIMARY KEY,
    invoice_id INTEGER NOT NULL REFERENCES invoices(id),
    reason VARCHAR(50) NOT NULL,
    explanation_summary TEXT NOT NULL,
    reasoning_chain TEXT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending_human',
    resolution VARCHAR(50),
    resolved_by VARCHAR(255),
    resolved_at TIMESTAMP,
    resolution_channel VARCHAR(20),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS audit_log (
    id SERIAL PRIMARY KEY,
    invoice_id INTEGER NOT NULL REFERENCES invoices(id),
    agent_name VARCHAR(50) NOT NULL,
    model_used VARCHAR(100),
    input_summary TEXT NOT NULL,
    output_summary TEXT NOT NULL,
    raw_output TEXT,
    timestamp TIMESTAMP DEFAULT NOW()
);
