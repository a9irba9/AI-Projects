# FlowPilot AI — Smart Business Workflow Assistant

**FlowPilot AI** is an enterprise-style, human-in-the-loop business workflow automation web application. It accepts natural-language business requests, uses Google Gemini (`gemini-2.5-flash`) to extract structured task data, presents an editable review screen for human approval, persists approved tasks in SQLite, tracks an audit log of all actions, and exports tasks to CSV.

---

## Purpose & Business Value

**Core Purpose:** Turn unstructured natural-language requests into structured, trackable, human-approved business tasks.

- **Problem Solved:** Work requests arrive as messy sentences in emails, chat messages, or meeting notes. Converting them manually is slow, while letting AI create tasks blindly is risky.
- **How It Fulfils This Purpose:**
  1. **Understands Natural Language:** Extracts `title`, `category`, `priority`, `due_date` (relative to backend date), `assigned_to`, and `action_items`.
  2. **Enforces Human-in-the-Loop Approval:** Stages AI proposals in an editable review screen; nothing is saved until a human clicks **Approve** (or **Reject**).
  3. **Manages Lifecycle & Audit Trail:** Tracks statuses (`Pending` → `In Progress` → `Completed`), logs every action in **Activity History**, and exports filtered tasks to CSV.

---

## Key Features
- **Natural-Language Task Extraction:** Converts plain-English business requests into structured JSON (`title`, `description`, `category`, `priority`, `due_date`, `assigned_to`, `action_items`, `confidence`, `requires_clarification`).
- **Human-in-the-Loop Review:** AI never creates tasks automatically. Users inspect, edit, and explicitly **Approve** or **Reject** every proposed task.
- **Explicit Demo Mode:** Works out-of-the-box without a `GEMINI_API_KEY` using clearly labelled deterministic sample responses.
- **Task Management:** Full CRUD, status transitions (`Pending`, `In Progress`, `Completed`, `Cancelled`), search, multi-filter (`status`, `priority`, `category`), and sorting (`created_at`, `due_date`).
- **Activity History Audit Log:** Records `AI request processed`, `Task approved`, `Task rejected`, `Task created`, `Task edited`, `Status changed`, and `Task deleted` (preserving history even after task deletion).
- **Safe CSV Export:** UTF-8 (with BOM) export supporting active filters and spreadsheet formula-injection protection (`=`, `+`, `-`, `@`).

---

## Technology Stack
- **Backend:** Python 3.12, Flask 3.1, Flask Blueprints, SQLAlchemy 2.0, SQLite
- **AI:** Google Gemini API (`google-genai` SDK, `gemini-2.5-flash`)
- **Frontend:** HTML5, CSS3, Bootstrap 5, JavaScript
- **Testing:** `pytest` (28 automated tests using mocked AI responses)

---

## Project Structure
```text
flowpilot-ai/
├── app/
│   ├── __init__.py              # App factory, CSRF protection, blueprint registration
│   ├── extensions.py            # SQLAlchemy instance
│   ├── models/
│   │   ├── task.py              # Task model
│   │   └── activity.py          # ActivityLog model (ondelete="SET NULL" FK)
│   ├── routes/
│   │   ├── dashboard.py         # KPI dashboard & /health
│   │   ├── tasks.py             # Task CRUD, search, filter, sort, status
│   │   ├── ai_processing.py     # Natural-language input, review, approve/reject
│   │   └── exports.py           # Activity History & CSV export
│   ├── services/
│   │   ├── gemini_service.py    # Modular LLMTaskProvider & GeminiProvider
│   │   ├── task_extraction.py   # Prompting, JSON validation, Demo Mode
│   │   ├── task_service.py      # Task validation & DB operations
│   │   └── activity_service.py  # Audit logging
│   ├── templates/               # Bootstrap 5 Jinja2 templates
│   └── static/css/style.css
├── tests/                       # 28 pytest tests (m1..m5)
├── config.py
├── run.py
├── requirements.txt
├── .env.example
└── .gitignore
```

---

## Database Schema
- **`tasks`**: `id` (PK), `title`, `description`, `category`, `priority`, `due_date`, `assigned_to`, `action_items_json`, `status`, `original_request`, `confidence`, `created_at` (UTC), `updated_at` (UTC).
- **`activity_logs`**: `id` (PK), `event_type`, `task_id` (FK -> `tasks.id`, `ON DELETE SET NULL`), `details`, `created_at` (UTC).

---

## Installation & Startup (Windows, Python 3.12)

1. **Create and activate virtual environment:**
   ```powershell
   cd flowpilot-ai
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```
2. **Install dependencies:**
   ```powershell
   pip install -r requirements.txt
   ```
3. **Configure environment variables:**
   Copy `.env.example` to `.env`.
   - For **Demo Mode**, leave `GEMINI_API_KEY=` blank.
   - For **Live Gemini**, set `GEMINI_API_KEY=your_ai_studio_key`.
4. **Run the application:**
   ```powershell
   python run.py
   ```
   Open `http://127.0.0.1:5001`.
5. **Run tests:**
   ```powershell
   python -m pytest -v
   ```

---

## Example Business Requests
- *"The delivery to ABC Manufacturing is delayed. Follow up with the supplier tomorrow and mark it as high priority."*
- *"Schedule a meeting with the finance team next Friday to discuss the quarterly budget."*
- *"The customer reported a damaged product. Assign an investigation task to the support team."*

---

## Recruitment Demo Script (2–3 Minutes)
1. Open the **Dashboard** (`/`) to show KPI cards and recent tasks/activity.
2. Go to **Create Task** (`/ai/create`), click **Fill Example Request**, and submit.
3. On **Review Proposed Task** (`/ai/review`), point out the Demo Mode / Gemini badge, edit the title or priority, and click **Approve Task**.
4. Show the saved task on **All Tasks** (`/tasks/`) and change its status to **In Progress**.
5. Open **Activity History** (`/exports/activity`) to show the full audit trail.
6. Click **Export CSV** on **All Tasks** to download `flowpilot_tasks_YYYY-MM-DD.csv`.

---

## Known Limitations
- **No user authentication:** Designed as a single-workspace internal tool MVP.
- **No external integrations:** Email, Slack, or calendar sync are intentionally out of scope.
- **Demo Mode:** Uses deterministic keyword-based sample responses when `GEMINI_API_KEY` is not set.
