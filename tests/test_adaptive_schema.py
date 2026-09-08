"""Validation tests for the Module 13.1 adaptive schema."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.adaptive import NextBestAction


def _action(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "action": "PRACTICE",
        "topic": "SQL joins",
        "reason": "Reinforce a weak prerequisite.",
        "priority": "High",
        "estimated_minutes": 30,
        "expected_outcome": "Explain and apply inner and outer joins.",
    }
    values.update(overrides)
    return values


def test_accepts_each_allowed_action() -> None:
    allowed_actions = (
        "LEARN_TOPIC",
        "PRACTICE",
        "REVISE",
        "TAKE_QUIZ",
        "BUILD_PROJECT",
        "REVIEW_PROJECT",
        "INTERVIEW_PRACTICE",
        "MOVE_TO_NEXT_PHASE",
    )

    for action in allowed_actions:
        result = NextBestAction.model_validate(_action(action=action))
        assert result.action == action


def test_rejects_unknown_action() -> None:
    with pytest.raises(ValidationError):
        NextBestAction.model_validate(_action(action="WATCH_VIDEO"))


@pytest.mark.parametrize("field", ["topic", "reason", "priority", "expected_outcome"])
def test_rejects_blank_text_fields(field: str) -> None:
    with pytest.raises(ValidationError):
        NextBestAction.model_validate(_action(**{field: ""}))


@pytest.mark.parametrize("estimated_minutes", [0, -5])
def test_rejects_non_positive_estimated_minutes(estimated_minutes: int) -> None:
    with pytest.raises(ValidationError):
        NextBestAction.model_validate(_action(estimated_minutes=estimated_minutes))
