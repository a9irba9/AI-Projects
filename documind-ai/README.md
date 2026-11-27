# DocuMind AI — Intelligent Document Processing & Retrieval System

An enterprise-style document intelligence web application built with **Python 3.12**, **Flask**, **SQLAlchemy (SQLite)**, **PyMuPDF**, **Google Gemini API**, and **FAISS** for Retrieval-Augmented Generation (RAG).

---

## Purpose & Business Value

**Core Purpose:** Turn static, unstructured business PDFs into searchable, structured, and verifiable company knowledge.

- **Problem Solved:** Staff waste hours manually opening PDFs (invoices, purchase orders, quotations, contracts), copying numbers into spreadsheets, and searching folders for specific terms.
- **How It Fulfils This Purpose:**
  1. **Ingests & Validates PDFs** (batch upload, `%PDF-` header check, SHA-256 duplicate detection, page-by-page extraction).
  2. **Extracts Structured Data** (supplier, invoice number, dates, currency, totals, terms) into SQLite with manual correction and CSV export.
  3. **Answers Questions with Citations (RAG):** Indexes document chunks in FAISS so users can ask questions in any language and receive grounded answers with exact **document name + page number** references.

---

## Architecture Overview

- **Backend (`app/`)**:
  - `app/__init__.py`: Flask application factory, directory initialization, SQLAlchemy setup, and blueprint registration.
  - `app/models/`: SQLAlchemy models (`Document`, `DocumentPage`, `DocumentChunk`, `ExtractedInformation`, `Conversation`, `Message`).
  - `app/services/`:
    - `pdf_extractor.py`: Page-by-page text extraction using PyMuPDF (`fitz`) with optional `pytesseract` OCR fallback.
    - `llm_provider.py`: Abstract `LLMProvider` interface with `GeminiProvider` (`google-genai`).
    - `information_extractor.py`: Structured JSON business field extraction, numeric normalization, and manual edit support.
    - `embedding_service.py` & `vector_store.py`: Configurable text chunking and FAISS (`IndexFlatIP`) vector storage persisted to `storage/vector_index/`.
    - `rag_service.py`: Context-grounded Q&A with document name and page-number source attribution.
  - `app/routes/`: `dashboard`, `documents`, `assistant`, and `exports` blueprints.
- **Frontend (`app/templates/`, `app/static/`)**: Responsive Bootstrap 5 enterprise dashboard.

---

## Installation & Startup

1. **Create and activate the Python 3.12 virtual environment:**
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

2. **Install dependencies:**
   ```powershell
   pip install -r requirements.txt
   ```

3. **Configure environment variables:**
   Copy `.env.example` to `.env` and set `GEMINI_API_KEY` and `SECRET_KEY`.

4. **Generate synthetic sample PDFs (optional):**
   ```powershell
   python scripts/generate_samples.py
   ```

5. **Run the application (SQLite database is initialized automatically on startup):**
   ```powershell
   python run.py
   ```
   Open `http://127.0.0.1:5000` in your browser.

6. **Run automated tests:**
   ```powershell
   python -m pytest -v
   ```

---

## API & Route Reference

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/` | Business dashboard with metrics & recent uploads |
| `GET` | `/health` | JSON health check |
| `GET` | `/documents/` | List & search uploaded documents (`?q=`) |
| `POST` | `/documents/upload` | Upload PDF, validate, deduplicate, extract, and index |
| `GET` | `/documents/<id>` | View document metadata, extracted fields, and page text |
| `POST` | `/documents/<id>/extract` | Re-run AI structured extraction |
| `POST` | `/documents/<id>/fields/update` | Save manual corrections to extracted fields |
| `POST` | `/documents/<id>/delete` | Delete document, stored PDF, and vector index entries |
| `GET` | `/assistant/` | Interactive AI Assistant chat UI |
| `POST` | `/assistant/ask` | Ask a question via RAG (returns JSON answer + sources) |
| `POST` | `/assistant/clear` | Clear current session conversation |
| `GET` | `/exports/extracted` | View extracted data table |
| `GET` | `/exports/csv` | Download extracted data as escaped CSV |
| `GET` | `/exports/settings` | View runtime configuration & OCR/API status |

---

## Demonstration Walkthrough

1. Start the app (`python run.py`) and open `http://127.0.0.1:5000`.
2. Go to **Documents** and upload `storage/samples/sample_invoice_1.pdf`.
3. Inspect the extracted page text and structured invoice fields on the **Document Detail** page.
4. Go to **AI Assistant** and ask: `"What is the total invoice amount?"` and `"When is payment due?"` — verify answers and source citations.
5. Upload `storage/samples/sample_invoice_2.pdf` and ask the assistant to compare the two invoices.
6. Go to **Extracted Data** and click **Export CSV** to download `documind_extracted_data.csv`.

---

## Known Limitations
- **OCR:** Requires Tesseract OCR to be installed on the system `PATH`; otherwise scanned PDFs report `insufficient_text` honestly.
- **OpenAI Provider:** `LLMProvider` is abstracted for multi-provider support, but only `GeminiProvider` is implemented in this version.
