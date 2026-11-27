from datetime import date
import json
import pytest
from app.services.gemini_service import GeminiAPIError, LLMTaskProvider
from app.services.task_extraction import (
    ExtractionError,
    extract_task_from_request,
    validate_and_normalize_extraction,
)


class MockProvider(LLMTaskProvider):
    def __init__(self, response_text: str):
        self.response_text = response_text
        self.last_prompt = ""

    def generate_task_json(self, prompt: str, system_instruction: str) -> str:
        self.last_prompt = prompt
        return self.response_text


class ErrorProvider(LLMTaskProvider):
    def generate_task_json(self, prompt: str, system_instruction: str) -> str:
        raise GeminiAPIError("Upstream 503 Service Unavailable")


def test_valid_structured_response_and_backend_date_injection():
    payload = {
        "title": "Follow up with ABC Manufacturing",
        "description": "Check delayed delivery",
        "category": "Operations",
        "priority": "High",
        "due_date": "2026-11-27",
        "assigned_to": "Operations Team",
        "action_items": ["Call supplier", "Log ETA"],
        "confidence": 0.95,
        "requires_clarification": False,
        "clarification_question": None,
    }
    provider = MockProvider(json.dumps(payload))
    res = extract_task_from_request(
        "Follow up tomorrow", current_date=date(2026, 11, 26), provider=provider
    )
    assert "Current Date: 2026-11-26" in provider.last_prompt
    assert res["title"] == "Follow up with ABC Manufacturing"
    assert res["category"] == "Operations"
    assert res["priority"] == "High"
    assert res["due_date"] == "2026-11-27"
    assert res["is_demo"] is False


def test_missing_title_raises_extraction_error():
    with pytest.raises(ExtractionError, match="title"):
        validate_and_normalize_extraction({"description": "No title"})


def test_invalid_category_and_priority_mapped_safely():
    res = validate_and_normalize_extraction(
        {
            "title": "Test task",
            "category": "NonExistent",
            "priority": "SuperUrgent",
        }
    )
    assert res["category"] == "General"
    assert res["priority"] == "Medium"


def test_invalid_date_triggers_clarification():
    res = validate_and_normalize_extraction(
        {"title": "Test task", "due_date": "next-ish"}
    )
    assert res["due_date"] is None
    assert res["requires_clarification"] is True
    assert res["clarification_question"] is not None


def test_malformed_json_raises_extraction_error():
    with pytest.raises(ExtractionError, match="Malformed JSON"):
        validate_and_normalize_extraction("{not valid json")


def test_null_values_handled_safely():
    res = validate_and_normalize_extraction(
        {
            "title": "Null fields task",
            "description": None,
            "due_date": None,
            "assigned_to": None,
            "action_items": None,
            "confidence": None,
        }
    )
    assert res["due_date"] is None
    assert res["assigned_to"] is None
    assert res["action_items"] == []
    assert res["confidence"] == 0.0


def test_ambiguous_date_clarification_preserved():
    res = validate_and_normalize_extraction(
        {
            "title": "Quarterly review",
            "due_date": None,
            "requires_clarification": True,
            "clarification_question": "Which Friday do you mean?",
        }
    )
    assert res["requires_clarification"] is True
    assert "Friday" in res["clarification_question"]


def test_gemini_api_error_handled():
    with pytest.raises(ExtractionError, match="503"):
        extract_task_from_request("Do something", provider=ErrorProvider())


def test_missing_api_key_triggers_demo_mode(app):
    with app.app_context():
        app.config["GEMINI_API_KEY"] = ""
        res = extract_task_from_request(
            "The delivery to ABC Manufacturing is delayed. Follow up with the supplier tomorrow and mark it as high priority.",
            current_date=date(2026, 11, 26),
        )
        assert res["is_demo"] is True
        assert "Demo Mode" in res["demo_notice"]
        assert res["category"] == "Operations"
        assert res["priority"] == "High"
        assert res["due_date"] == "2026-11-27"
