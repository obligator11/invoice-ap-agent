# 🧾 Invoice / AP Automation Agent

A **local-first, multi-agent invoice processing pipeline** — ingests invoices
(PDF, scanned image, or forwarded email), extracts structured data, matches
against purchase orders, flags anomalies, pauses for human review when
confidence is low or risk is high, routes for final approval, and produces a
full explainable audit trail. All AI reasoning runs on **local models only**
(Ollama + LM Studio) — no cloud API calls in the core pipeline.

Built as a demonstration of **governed AI automation**: the two decisions
that actually move money (PO matching, approval-ceiling enforcement) are
plain deterministic code, not LLM judgment. Every agent's output is
schema-validated before it touches the database. Nothing is a black box —
every step is logged and explainable.

---

## Why this exists

Most "AI does my paperwork" demos are a single prompt with no guardrails.
This project asks a different question: **what does it take to make AI
automation something a finance team could actually trust?** The answer,
worked out here, is: strict output schemas, deterministic policy
enforcement, a human-in-the-loop gate that can't be bypassed by a model's
opinion, and an audit trail detailed enough to answer "why did the system
do that?" for any invoice, at any time.

## Features

- 📄 **Multi-format ingestion** — native PDF, scanned/photographed PDF,
  standalone image, forwarded `.eml`, live inbox polling
- 🤖 **6-agent pipeline** — Extractor, Matcher, Anomaly Reasoner, Explainer,
  HITL Gate, Router — each with a single, narrow responsibility
- 🔒 **Schema-validated agent handoffs** — every LLM output is checked
  against a Pydantic schema before it's trusted; bad output degrades to
  "needs manual review," never a silent failure
- 🚦 **Deterministic guardrails** — PO matching and the auto-approve dollar
  ceiling are plain Python, not model judgment, so a human-set policy limit
  can never be argued past by an LLM
- ⏸️ **Human-in-the-loop gate** — invoices needing review pause the pipeline
  and sit in a queue, resolvable via the Streamlit UI *or* by replying
  APPROVE/REJECT to an email
- 🔍 **Full audit trail** — every agent's input, output, and raw reasoning
  is logged per invoice, browsable in the UI
- 🖥️ **Streamlit UI** — upload/inbox, live processing status, approval
  queue, ledger/dashboard, audit trail, and runtime settings
- 🏠 **100% local inference** — Ollama + LM Studio, local PostgreSQL, no
  cloud AI calls in the core pipeline

## Architecture

```
file (PDF / image / .eml)
   │
   ▼
ingestion/dispatch.py  ──►  routes to native-PDF / OCR / office-doc parser
   │
   ▼
pipeline/orchestrator.py
   │
   ├─► Extractor Agent   (Qwen2.5-Coder, LM Studio)  → structured invoice JSON
   ├─► Matcher            (plain Python, no LLM)      → PO match result
   ├─► Anomaly Reasoner   (DeepSeek R1, LM Studio)     → verdict + reasoning
   ├─► Explainer          (Llama 3.1, Ollama)          → plain-English note
   ├─► HITL Gate          (plain Python, no LLM)       → clears, or pauses
   │        └─ paused → ReviewTask queued, email sent, pipeline stops
   │           until a human resolves it (UI button or email reply)
   └─► Router             (Gemma, Ollama)              → department + approver
```

Every step writes a row to `audit_log` — timestamp, agent, model used, input,
output, and raw reasoning — regardless of whether that step used an LLM.

## Tech stack

`Python` · `Streamlit` · `PostgreSQL` · `SQLAlchemy` · `Pydantic` ·
`Ollama` · `LM Studio` · `pdfplumber` / `PyMuPDF` · `Tesseract OCR` ·
`pdf2image` · `Gmail SMTP/IMAP`

## Screenshots

*(add screenshots here — Processing view, Approval Queue, and Audit Trail
are the most illustrative)*

```
![Processing view](docs/screenshots/processing.png)
![Approval queue](docs/screenshots/approval_queue.png)
![Audit trail](docs/screenshots/audit_trail.png)
```

## Setup

```bash
# 1. System dependencies (OCR needs these installed at the OS level)
#    macOS:   brew install poppler tesseract
#    Ubuntu:  apt install poppler-utils tesseract-ocr
#    Windows (conda): conda install -c conda-forge poppler tesseract -y

# 2. Python environment
conda create -n ap_agent_env python=3.11 -y
conda activate ap_agent_env
pip install -r requirements.txt

# 3. PostgreSQL (local, free)
#    Docker:
docker run --name ap-postgres -e POSTGRES_USER=apagent -e POSTGRES_PASSWORD=apagent \
  -e POSTGRES_DB=invoice_ap -p 5432:5432 -d postgres:16
#    or a native install — then create the apagent user/db manually

# 4. Config
cp .env.example .env
# edit .env: DB creds, Gmail app password (optional), model names

# 5. Pull local models
ollama pull llama3.1
ollama pull gemma2
# In LM Studio: download a Qwen2.5-Coder and a DeepSeek-R1-Distill model,
# then start the local server (Developer tab → Start Server)

# 6. Demo data
python scripts/generate_sample_invoices.py
python scripts/seed_data.py

# 7. Run
streamlit run app.py
```

Then open the app, go to **Upload / Inbox**, and drop a file from
`sample_invoices/`. Watch it move through **Processing**, resolve anything
that lands in **Approval Queue**, and inspect the full reasoning in
**Audit Trail**.

## Known limitations (by design, for MVP scope)

- Runs synchronously — a production version would move LLM calls to a
  background worker queue instead of blocking the Streamlit UI thread
- Settings-page changes are session-only, not persisted back to `.env`
- Google Sheets read-only export is stubbed but not wired up
- Office-doc (`.docx`/`.xlsx`) ingestion works but is lightly tested

## License

MIT — do whatever you want with it.
