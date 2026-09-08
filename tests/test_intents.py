from enum import Enum

from app.agent.intents import Intent


def test_intent_defines_supported_intents() -> None:
    assert list(Intent) == [
        Intent.ROADMAP,
        Intent.LEARN,
        Intent.PRACTICE,
        Intent.QUIZ,
        Intent.PROGRESS,
        Intent.PROJECT_REVIEW,
        Intent.INTERVIEW,
        Intent.RESOURCE,
        Intent.NEXT_ACTION,
    ]


def test_intent_is_a_string_enum_with_stable_values() -> None:
    assert issubclass(Intent, Enum)
    assert {intent.name: intent.value for intent in Intent} == {
        "ROADMAP": "roadmap",
        "LEARN": "learn",
        "PRACTICE": "practice",
        "QUIZ": "quiz",
        "PROGRESS": "progress",
        "PROJECT_REVIEW": "project_review",
        "INTERVIEW": "interview",
        "RESOURCE": "resource",
        "NEXT_ACTION": "next_action",
    }
