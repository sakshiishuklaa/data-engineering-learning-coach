"""Focused tests for the roadmap LLM adapters."""

from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest
from pydantic import ValidationError

from app.schemas.roadmap import PersonalizedRoadmap
from app.services import llm_client


def test_gemini_uses_official_sdk_dependency_and_lazy_import() -> None:
    requirements = (Path(__file__).parents[1] / "requirements.txt").read_text()
    source = Path(llm_client.__file__).read_text()

    assert any(line.startswith("google-genai") for line in requirements.splitlines())
    assert "from google import genai" in source
    assert "google.generativeai" not in source


def _roadmap() -> PersonalizedRoadmap:
    return PersonalizedRoadmap.model_validate(
        {
            "target_role": "Data Engineer",
            "timeline_weeks": 2,
            "study_hours_per_week": 6,
            "total_estimated_weeks": 2,
            "phases": [
                {
                    "phase": 1,
                    "goal": "Learn Python foundations.",
                    "topics": ["Python"],
                    "priority": "MUST_LEARN",
                    "estimated_duration_weeks": 2,
                    "hands_on_exercises": ["Write a data transformation."],
                    "mini_project": "Build a small batch pipeline.",
                    "interview_questions": ["How do Python iterators work?"],
                    "completion_criteria": ["Can explain and test the transformation."],
                }
            ],
        }
    )


def test_openai_client_uses_settings_key_and_passes_structured_request(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: dict[str, object] = {}
    roadmap = _roadmap()

    class FakeCompletions:
        def parse(self, **kwargs: object) -> object:
            calls.update(kwargs)
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(parsed=roadmap, refusal=None))])

    class FakeOpenAI:
        def __init__(self, *, api_key: str) -> None:
            calls["api_key"] = api_key
            self.beta = SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions()))

    fake_openai = ModuleType("openai")
    fake_openai.OpenAI = FakeOpenAI
    monkeypatch.setitem(sys.modules, "openai", fake_openai)
    monkeypatch.setattr(llm_client, "get_settings", lambda: SimpleNamespace(llm_api_key="test-secret"))

    client = llm_client.OpenAIRoadmapLLMClient(model="test-model")
    result = client.generate_roadmap(prompt="roadmap prompt", response_model=PersonalizedRoadmap)

    assert result is roadmap
    assert calls["api_key"] == "test-secret"
    assert calls["model"] == "test-model"
    assert calls["messages"] == [{"role": "user", "content": "roadmap prompt"}]
    assert calls["response_format"] is PersonalizedRoadmap


def test_openai_client_requires_api_key_without_exposing_it(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(llm_client, "get_settings", lambda: SimpleNamespace(llm_api_key=None))

    with pytest.raises(ValueError, match="LLM_API_KEY is required") as error:
        llm_client.OpenAIRoadmapLLMClient()

    assert "test-secret" not in str(error.value)


def test_gemini_settings_read_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-secret")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-test-model")

    settings = llm_client.get_settings.__wrapped__()

    assert settings.gemini_api_key == "gemini-secret"
    assert settings.gemini_model == "gemini-test-model"


def test_gemini_client_uses_structured_pydantic_request(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: dict[str, object] = {}
    roadmap = _roadmap()
    parsed_response: object = roadmap

    class FakeGenerateContentConfig:
        def __init__(self, **kwargs: object) -> None:
            self.__dict__.update(kwargs)

    class FakeModels:
        def generate_content(self, **kwargs: object) -> object:
            calls.update(kwargs)
            return SimpleNamespace(parsed=parsed_response)

    class FakeClient:
        def __init__(self, *, api_key: str) -> None:
            calls["api_key"] = api_key
            self.models = FakeModels()

    fake_google = ModuleType("google")
    fake_genai = ModuleType("google.genai")
    fake_genai.Client = FakeClient
    fake_types = ModuleType("google.genai.types")
    fake_types.GenerateContentConfig = FakeGenerateContentConfig
    fake_genai.types = fake_types
    fake_google.genai = fake_genai
    monkeypatch.setitem(sys.modules, "google", fake_google)
    monkeypatch.setitem(sys.modules, "google.genai", fake_genai)
    monkeypatch.setitem(sys.modules, "google.genai.types", fake_types)
    monkeypatch.setattr(
        llm_client,
        "get_settings",
        lambda: SimpleNamespace(gemini_api_key="gemini-secret", gemini_model="configured-model"),
    )

    client = llm_client.GeminiRoadmapLLMClient()
    result = client.generate_roadmap(prompt="roadmap prompt", response_model=PersonalizedRoadmap)

    assert result is roadmap
    assert calls["api_key"] == "gemini-secret"
    assert calls["model"] == "configured-model"
    assert calls["contents"] == "roadmap prompt"
    config = calls["config"]
    assert config.response_mime_type == "application/json"
    response_schema = config.response_schema
    assert response_schema["properties"]["study_hours_per_week"]["type"] == "number"
    assert "exclusiveMinimum" not in response_schema["properties"]["study_hours_per_week"]
    phase_schema = response_schema["$defs"]["RoadmapPhase"]
    assert response_schema["properties"]["phases"]["items"]["$ref"] == "#/$defs/RoadmapPhase"
    assert phase_schema["properties"]["priority"]["enum"] == [
        "MUST_LEARN",
        "GOOD_TO_LEARN",
        "OPTIONAL",
    ]
    assert phase_schema["properties"]["topics"]["type"] == "array"

    original_schema = PersonalizedRoadmap.model_json_schema()
    assert original_schema["properties"]["study_hours_per_week"]["exclusiveMinimum"] == 0

    parsed_response = _roadmap().model_dump() | {"study_hours_per_week": 0}
    with pytest.raises(ValidationError):
        client.generate_roadmap(prompt="roadmap prompt", response_model=PersonalizedRoadmap)


def test_gemini_client_requires_api_key_without_exposing_it(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        llm_client,
        "get_settings",
        lambda: SimpleNamespace(gemini_api_key=None, gemini_model="configured-model"),
    )

    with pytest.raises(ValueError, match="GEMINI_API_KEY is required") as error:
        llm_client.GeminiRoadmapLLMClient()

    assert "gemini-secret" not in str(error.value)


def _retry_test_client(monkeypatch: pytest.MonkeyPatch, responses: list[object]) -> tuple[object, dict[str, int]]:
    calls = {"count": 0}

    class FakeGenerateContentConfig:
        def __init__(self, **kwargs: object) -> None:
            self.__dict__.update(kwargs)

    class FakeModels:
        def generate_content(self, **kwargs: object) -> object:
            calls["count"] += 1
            response = responses.pop(0)
            if isinstance(response, Exception):
                raise response
            return response

    fake_google = ModuleType("google")
    fake_genai = ModuleType("google.genai")
    fake_types = ModuleType("google.genai.types")
    fake_types.GenerateContentConfig = FakeGenerateContentConfig
    fake_genai.types = fake_types
    fake_google.genai = fake_genai
    monkeypatch.setitem(sys.modules, "google", fake_google)
    monkeypatch.setitem(sys.modules, "google.genai", fake_genai)
    monkeypatch.setitem(sys.modules, "google.genai.types", fake_types)
    monkeypatch.setattr(
        llm_client,
        "get_settings",
        lambda: SimpleNamespace(gemini_api_key="gemini-secret", gemini_model="configured-model"),
    )
    return (
        llm_client.GeminiRoadmapLLMClient(client=SimpleNamespace(models=FakeModels())),
        calls,
    )


def test_gemini_retries_503_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    roadmap = _roadmap()
    transient_error = RuntimeError("503 UNAVAILABLE")
    client, calls = _retry_test_client(monkeypatch, [transient_error, SimpleNamespace(parsed=roadmap)])
    sleeps: list[float] = []
    monkeypatch.setattr(llm_client.time, "sleep", sleeps.append)

    result = client.generate_roadmap(prompt="roadmap prompt", response_model=PersonalizedRoadmap)

    assert result is roadmap
    assert calls["count"] == 2
    assert sleeps == [0.1]


def test_gemini_retries_503_only_with_bounded_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    client, calls = _retry_test_client(
        monkeypatch,
        [RuntimeError("503 UNAVAILABLE"), RuntimeError("503 UNAVAILABLE"), RuntimeError("503 UNAVAILABLE")],
    )
    sleeps: list[float] = []
    monkeypatch.setattr(llm_client.time, "sleep", sleeps.append)

    with pytest.raises(RuntimeError, match="503 UNAVAILABLE"):
        client.generate_roadmap(prompt="roadmap prompt", response_model=PersonalizedRoadmap)

    assert calls["count"] == 3
    assert sleeps == [0.1, 0.2]


def test_gemini_does_not_retry_non_retryable_error(monkeypatch: pytest.MonkeyPatch) -> None:
    client, calls = _retry_test_client(monkeypatch, [RuntimeError("invalid API key")])
    sleeps: list[float] = []
    monkeypatch.setattr(llm_client.time, "sleep", sleeps.append)

    with pytest.raises(RuntimeError, match="invalid API key"):
        client.generate_roadmap(prompt="roadmap prompt", response_model=PersonalizedRoadmap)

    assert calls["count"] == 1
    assert sleeps == []
