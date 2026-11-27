# AI Business Assistants Portfolio

Two production-minded, human-in-the-loop Python/Flask AI web applications built for enterprise document intelligence and workflow automation.

---

## Projects

### 1. [DocuMind AI](./documind-ai/README.md) — Intelligent Document Processing & Retrieval System
- **Purpose:** Turn unstructured business PDFs (invoices, purchase orders, quotations, contracts) into searchable, structured, and verifiable company knowledge.
- **Key Features:** Batch PDF upload, SHA-256 duplicate detection, PyMuPDF + optional OCR extraction, Google Gemini structured JSON extraction, FAISS vector search, any-language-to-any-language RAG with exact page citations, Chart.js analytics, side-by-side document comparison, and CSV export.
- **Stack:** Python 3.12, Flask, SQLAlchemy (SQLite), PyMuPDF, Google Gemini (`gemini-2.5-flash` & `gemini-embedding-001`), FAISS, Bootstrap 5, Chart.js, `pytest` (16 tests).

### 2. [FlowPilot AI](./flowpilot-ai/README.md) — Smart Business Workflow Assistant
- **Purpose:** Turn unstructured natural-language business requests into structured, trackable, human-approved tasks.
- **Key Features:** Single & multi-task extraction from natural language or meeting notes, strict JSON validation, explicit Demo Mode, human-in-the-loop review & approval, Kanban Board & Table views, full Activity History audit log, and formula-injection-safe CSV export.
- **Stack:** Python 3.12, Flask, SQLAlchemy (SQLite), Google Gemini (`gemini-2.5-flash`), Bootstrap 5, `pytest` (28 tests).

---

## Deployment
Both projects include `gunicorn` in `requirements.txt` and a `Procfile` (`web: gunicorn run:app`) for deployment on platforms like **Render** (set **Root Directory** to `documind-ai` or `flowpilot-ai`).
