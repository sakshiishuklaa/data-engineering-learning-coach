"""LLM adapters for structured roadmap generation."""

from __future__ import annotations

import time
from typing import Any

from app.config import get_settings
from app.schemas.roadmap import PersonalizedRoadmap
from app.services.roadmap_service import RoadmapLLMClient

DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"
_UNSUPPORTED_GEMINI_SCHEMA_KEYWORDS = frozenset({"exclusiveMinimum", "exclusiveMaximum"})
_GEMINI_MAX_RETRIES = 2
_GEMINI_RETRY_DELAY_SECONDS = 0.1


def _gemini_compatible_schema(schema: Any) -> Any:
    """Copy a JSON schema while removing keywords unsupported by Gemini schemas."""
    if isinstance(schema, dict):
        return {
            key: _gemini_compatible_schema(value)
            for key, value in schema.items()
            if key not in _UNSUPPORTED_GEMINI_SCHEMA_KEYWORDS
        }
    if isinstance(schema, list):
        return [_gemini_compatible_schema(value) for value in schema]
    return schema


def _gemini_error_status_code(error: Exception) -> int | None:
    """Read a provider status code without depending on a specific SDK error class."""
    for source in (error, getattr(error, "response", None)):
        for attribute in ("status_code", "code"):
            value = getattr(source, attribute, None)
            try:
                if value is not None:
                    return int(value)
            except (TypeError, ValueError):
                continue
    return None


def _is_retryable_gemini_error(error: Exception) -> bool:
    """Retry only transient provider failures, never client or validation errors."""
    status_code = _gemini_error_status_code(error)
    if status_code in {429, 500, 502, 503, 504}:
        return True
    if status_code is not None:
        return False

    message = str(error).lower()
    if any(marker in message for marker in ("invalid api key", "unauthorized", "invalid argument", "bad request", "schema", "validation")):
        return False
    return "503" in message or "unavailable" in message or "temporarily unavailable" in message


class OpenAIRoadmapLLMClient(RoadmapLLMClient):
    """Generate validated roadmap data through OpenAI structured outputs."""

    def __init__(self, model: str = DEFAULT_OPENAI_MODEL, client: Any | None = None) -> None:
        api_key = get_settings().llm_api_key
        if not api_key:
            raise ValueError("LLM_API_KEY is required to use the OpenAI roadmap client.")

        if client is None:
            from openai import OpenAI

            client = OpenAI(api_key=api_key)
        self._client = client
        self._model = model

    def generate_roadmap(self, *, prompt: str, response_model: type[PersonalizedRoadmap]) -> Any:
        """Return the provider-parsed structured roadmap response."""
        response = self._client.beta.chat.completions.parse(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
            response_format=response_model,
        )
        message = response.choices[0].message
        if getattr(message, "refusal", None):
            raise ValueError("OpenAI refused to generate the roadmap.")
        parsed = getattr(message, "parsed", None)
        if parsed is None:
            raise ValueError("OpenAI returned no structured roadmap.")
        return parsed


class GeminiRoadmapLLMClient(RoadmapLLMClient):
    """Generate validated roadmap data through Gemini structured outputs."""

    def __init__(self, model: str | None = None, client: Any | None = None) -> None:
        settings = get_settings()
        api_key = settings.gemini_api_key
        if not api_key:
            raise ValueError("GEMINI_API_KEY is required to use the Gemini roadmap client.")

        if client is None:
            from google import genai

            client = genai.Client(api_key=api_key)
        self._client = client
        self._model = model or settings.gemini_model or DEFAULT_GEMINI_MODEL

    def generate_roadmap(self, *, prompt: str, response_model: type[PersonalizedRoadmap]) -> Any:
        """Return a Pydantic-validated structured roadmap response."""
        from google.genai import types

        response_schema = _gemini_compatible_schema(response_model.model_json_schema())
        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=response_schema,
        )
        for attempt in range(_GEMINI_MAX_RETRIES + 1):
            try:
                response = self._client.models.generate_content(
                    model=self._model,
                    contents=prompt,
                    config=config,
                )
                break
            except Exception as error:
                if attempt >= _GEMINI_MAX_RETRIES or not _is_retryable_gemini_error(error):
                    raise
                time.sleep(_GEMINI_RETRY_DELAY_SECONDS * (2**attempt))
        parsed = getattr(response, "parsed", None)
        if parsed is None:
            raise ValueError("Gemini returned no structured roadmap.")
        return response_model.model_validate(parsed)
