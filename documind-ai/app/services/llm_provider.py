from abc import ABC, abstractmethod
import json
import logging
from typing import Any, List
from flask import current_app

logger = logging.getLogger(__name__)


class LLMConfigurationError(Exception):
    """Raised when required LLM API credentials are missing or invalid."""


class LLMProviderError(Exception):
    """Raised when an upstream LLM API call fails."""


class LLMProvider(ABC):
    """Abstract base class for LLM and embedding providers."""

    @abstractmethod
    def generate_text(self, prompt: str, system_instruction: str | None = None) -> str:
        """Generate a plain text response."""

    @abstractmethod
    def generate_json(self, prompt: str, system_instruction: str | None = None) -> dict[str, Any]:
        """Generate and parse a structured JSON response."""

    @abstractmethod
    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Generate embedding vectors for a list of texts."""


class GeminiProvider(LLMProvider):
    """Google Gemini API provider using the google-genai SDK."""

    def __init__(self, api_key: str, model: str, embedding_model: str):
        if not api_key or api_key == "your-gemini-api-key-here":
            raise LLMConfigurationError("GEMINI_API_KEY is not configured.")
        from google import genai

        self._client = genai.Client(api_key=api_key)
        self._model = model
        self._embedding_model = embedding_model

    def generate_text(self, prompt: str, system_instruction: str | None = None) -> str:
        from google.genai import types

        try:
            config = (
                types.GenerateContentConfig(system_instruction=system_instruction)
                if system_instruction
                else None
            )
            response = self._client.models.generate_content(
                model=self._model,
                contents=prompt,
                config=config,
            )
            return (response.text or "").strip()
        except Exception as exc:
            logger.error("Gemini generate_text error: %s", exc)
            raise LLMProviderError(f"Gemini API error: {exc}") from exc

    def generate_json(self, prompt: str, system_instruction: str | None = None) -> dict[str, Any]:
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
            raw = (response.text or "").strip()
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            logger.error("Gemini returned invalid JSON: %s", exc)
            raise LLMProviderError(f"Invalid JSON from Gemini: {exc}") from exc
        except Exception as exc:
            logger.error("Gemini generate_json error: %s", exc)
            raise LLMProviderError(f"Gemini API error: {exc}") from exc

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        try:
            embeddings: List[List[float]] = []
            for text in texts:
                res = self._client.models.embed_content(
                    model=self._embedding_model,
                    contents=text,
                )
                embeddings.append(list(res.embeddings[0].values))
            return embeddings
        except Exception as exc:
            logger.error("Gemini embed_texts error: %s", exc)
            raise LLMProviderError(f"Gemini embedding error: {exc}") from exc


def get_llm_provider() -> LLMProvider:
    """Factory returning the configured LLMProvider instance."""
    provider_name = current_app.config.get("LLM_PROVIDER", "gemini").lower()
    if provider_name == "gemini":
        return GeminiProvider(
            api_key=current_app.config.get("GEMINI_API_KEY", ""),
            model=current_app.config.get("GEMINI_MODEL", "gemini-2.5-flash"),
            embedding_model=current_app.config.get(
                "GEMINI_EMBEDDING_MODEL", "gemini-embedding-001"
            ),
        )
    raise LLMConfigurationError(f"Unsupported LLM_PROVIDER: {provider_name}")
