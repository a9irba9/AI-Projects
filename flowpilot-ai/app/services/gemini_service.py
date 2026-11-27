from abc import ABC, abstractmethod
import logging
from flask import current_app

logger = logging.getLogger(__name__)


class MissingAPIKeyError(Exception):
    """Raised when GEMINI_API_KEY is not configured."""


class GeminiAPIError(Exception):
    """Raised when the upstream Gemini API call fails."""


class LLMTaskProvider(ABC):
    """Abstract interface for task extraction LLM providers."""

    @abstractmethod
    def generate_task_json(self, prompt: str, system_instruction: str) -> str:
        """Return a raw JSON string from the LLM."""


class GeminiProvider(LLMTaskProvider):
    """Google Gemini API provider using the official google-genai SDK."""

    def __init__(self, api_key: str, model: str = "gemini-2.5-flash"):
        if not api_key:
            raise MissingAPIKeyError("GEMINI_API_KEY is not configured.")
        from google import genai

        self._client = genai.Client(api_key=api_key)
        self._model = model

    def generate_task_json(self, prompt: str, system_instruction: str) -> str:
        from google.genai import types

        try:
            config = types.GenerateContentConfig(
                response_mime_type="application/json",
                system_instruction=system_instruction,
            )
            response = self._client.models.generate_content(
                model=self._model,
                contents=prompt,
                config=config,
            )
            return (response.text or "").strip()
        except Exception as exc:
            logger.error("Gemini API error: %s", exc)
            raise GeminiAPIError(f"Gemini API call failed: {exc}") from exc


def get_llm_provider() -> LLMTaskProvider:
    """Return the configured LLMTaskProvider."""
    api_key = (current_app.config.get("GEMINI_API_KEY") or "").strip()
    model = current_app.config.get("GEMINI_MODEL", "gemini-2.5-flash")
    return GeminiProvider(api_key=api_key, model=model)
