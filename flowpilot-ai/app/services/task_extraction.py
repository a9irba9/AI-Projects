from datetime import date, datetime, timedelta
import json
from typing import Any, Optional
from app.services.gemini_service import (
    GeminiAPIError,
    LLMTaskProvider,
    MissingAPIKeyError,
    get_llm_provider,
)
from app.services.task_service import VALID_CATEGORIES, VALID_PRIORITIES

EXTRACTION_SYSTEM_PROMPT = (
    "You are FlowPilot AI, a business workflow extraction assistant. "
    "Convert the user's natural-language request into strictly valid JSON matching the schema. "
    "Rules:\n"
    "1. Never invent a person, company, date, or commitment.\n"
    "2. Interpret relative dates (e.g. 'tomorrow', 'next Friday') using the provided Current Date.\n"
    "3. If a date is ambiguous or unclear, set due_date to null, requires_clarification to true, "
    "and provide a concise clarification_question.\n"
    "4. Use null for any missing information.\n"
    "5. Allowed categories: Operations, Finance, Sales, Customer Support, HR, IT, General.\n"
    "6. Allowed priorities: Low, Medium, High, Critical."
)


class ExtractionError(Exception):
    """Raised when AI task extraction or JSON validation fails."""


def _validate_date_str(raw_val: Any) -> Optional[str]:
    if raw_val is None or str(raw_val).strip().lower() in ("", "null", "none"):
        return None
    try:
        parsed = datetime.strptime(str(raw_val).strip(), "%Y-%m-%d").date()
        return parsed.isoformat()
    except ValueError:
        return None


def validate_and_normalize_extraction(raw_output: str | dict[str, Any]) -> dict[str, Any]:
    """Validate and normalize raw JSON output from the LLM."""
    if isinstance(raw_output, str):
        try:
            data = json.loads(raw_output)
        except json.JSONDecodeError as exc:
            raise ExtractionError(f"Malformed JSON from AI: {exc}") from exc
    elif isinstance(raw_output, dict):
        data = raw_output
    else:
        raise ExtractionError("Unexpected AI output format.")

    if not isinstance(data, dict):
        raise ExtractionError("AI output must be a JSON object.")

    title = (data.get("title") or "").strip()
    if not title:
        raise ExtractionError("AI output is missing a required 'title'.")

    description = (data.get("description") or "").strip()

    category = (data.get("category") or "General").strip()
    if category not in VALID_CATEGORIES:
        category = "General"

    priority = (data.get("priority") or "Medium").strip()
    if priority not in VALID_PRIORITIES:
        priority = "Medium"

    raw_due = data.get("due_date")
    due_date = _validate_date_str(raw_due)
    date_was_invalid = raw_due is not None and str(raw_due).strip() != "" and due_date is None

    assigned_to = data.get("assigned_to")
    assigned_to = str(assigned_to).strip() if assigned_to is not None else None
    if assigned_to == "":
        assigned_to = None

    raw_items = data.get("action_items")
    if isinstance(raw_items, list):
        action_items = [str(x).strip() for x in raw_items if str(x).strip()]
    else:
        action_items = []

    try:
        confidence = float(data.get("confidence", 0.0) or 0.0)
        confidence = max(0.0, min(1.0, confidence))
    except (TypeError, ValueError):
        confidence = 0.0

    requires_clarification = bool(data.get("requires_clarification", False))
    clarification_question = data.get("clarification_question")
    if clarification_question is not None:
        clarification_question = str(clarification_question).strip() or None

    if date_was_invalid:
        requires_clarification = True
        clarification_question = (
            clarification_question or "The due date could not be parsed. Please specify YYYY-MM-DD."
        )

    return {
        "title": title[:200],
        "description": description,
        "category": category,
        "priority": priority,
        "due_date": due_date,
        "assigned_to": assigned_to,
        "action_items": action_items,
        "confidence": confidence,
        "requires_clarification": requires_clarification,
        "clarification_question": clarification_question,
    }


def _build_demo_response(user_request: str, current_date: date) -> dict[str, Any]:
    """Return a deterministic, explicitly labelled Demo Mode response."""
    req_lower = user_request.lower()
    due = (current_date + timedelta(days=1)).isoformat() if "tomorrow" in req_lower else None

    if "abc manufacturing" in req_lower or "supplier" in req_lower or "delayed" in req_lower:
        payload = {
            "title": "Follow up with ABC Manufacturing supplier",
            "description": f"Demo Mode extraction for: {user_request}",
            "category": "Operations",
            "priority": "High" if "high" in req_lower else "Medium",
            "due_date": due,
            "assigned_to": "Operations Team",
            "action_items": [
                "Contact ABC Manufacturing supplier regarding the delayed delivery",
                "Confirm revised shipment ETA and update stakeholders",
            ],
            "confidence": 0.92,
            "requires_clarification": False,
            "clarification_question": None,
        }
    else:
        payload = {
            "title": user_request[:80].strip() or "Business workflow task",
            "description": f"Demo Mode extraction for: {user_request}",
            "category": "General",
            "priority": "High" if "high" in req_lower else "Medium",
            "due_date": due,
            "assigned_to": None,
            "action_items": ["Review request details", "Assign owner and confirm timeline"],
            "confidence": 0.75,
            "requires_clarification": due is None,
            "clarification_question": "Please confirm the target due date." if due is None else None,
        }

    normalized = validate_and_normalize_extraction(payload)
    normalized["is_demo"] = True
    normalized["demo_notice"] = (
        "Simulated Demo Mode response (GEMINI_API_KEY is not configured)."
    )
    return normalized


def extract_task_from_request(
    user_request: str,
    current_date: Optional[date] = None,
    provider: Optional[LLMTaskProvider] = None,
) -> dict[str, Any]:
    """
    Extract structured task fields from a natural-language request.
    Falls back to an explicitly labelled Demo Mode when GEMINI_API_KEY is absent.
    """
    text = (user_request or "").strip()
    if not text:
        raise ExtractionError("Please enter a business request.")

    ref_date = current_date or date.today()

    if provider is None:
        try:
            provider = get_llm_provider()
        except MissingAPIKeyError:
            return _build_demo_response(text, ref_date)

    prompt = (
        f"Current Date: {ref_date.isoformat()}\n"
        f"User Request: {text}\n\n"
        "Return a single JSON object with keys: title, description, category, priority, "
        "due_date, assigned_to, action_items, confidence, requires_clarification, clarification_question."
    )

    try:
        raw_json = provider.generate_task_json(prompt, EXTRACTION_SYSTEM_PROMPT)
    except GeminiAPIError as exc:
        raise ExtractionError(str(exc)) from exc

    normalized = validate_and_normalize_extraction(raw_json)
    normalized["is_demo"] = False
    normalized["demo_notice"] = None
    return normalized


def extract_multiple_tasks_from_request(
    user_request: str,
    current_date: Optional[date] = None,
    provider: Optional[LLMTaskProvider] = None,
) -> list[dict[str, Any]]:
    """Extract multiple structured tasks from meeting notes or a multi-item email."""
    text = (user_request or "").strip()
    if not text:
        raise ExtractionError("Please enter meeting notes or a business request.")

    ref_date = current_date or date.today()

    if provider is None:
        try:
            provider = get_llm_provider()
        except MissingAPIKeyError:
            # Deterministic Demo Mode for multi-task extraction
            lines = [ln.strip("-* \t") for ln in text.splitlines() if ln.strip()]
            if len(lines) <= 1:
                return [_build_demo_response(text, ref_date)]
            return [_build_demo_response(ln, ref_date) for ln in lines[:5]]

    prompt = (
        f"Current Date: {ref_date.isoformat()}\n"
        f"Meeting Notes / Email:\n{text}\n\n"
        "Extract ALL distinct actionable tasks as a JSON object with a single key 'tasks' "
        "containing a list of task objects (each with: title, description, category, priority, "
        "due_date, assigned_to, action_items, confidence, requires_clarification, clarification_question)."
    )
    try:
        raw_json = provider.generate_task_json(prompt, EXTRACTION_SYSTEM_PROMPT)
        parsed = json.loads(raw_json)
    except (GeminiAPIError, json.JSONDecodeError) as exc:
        raise ExtractionError(f"Batch extraction failed: {exc}") from exc

    raw_tasks = parsed.get("tasks") if isinstance(parsed, dict) else parsed
    if not isinstance(raw_tasks, list) or not raw_tasks:
        raise ExtractionError("AI did not return a valid list of tasks.")

    results = []
    for item in raw_tasks[:10]:
        norm = validate_and_normalize_extraction(item)
        norm["is_demo"] = False
        norm["demo_notice"] = None
        results.append(norm)
    return results
