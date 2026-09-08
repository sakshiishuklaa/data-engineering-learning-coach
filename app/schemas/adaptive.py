"""Schemas for adaptive learning recommendations."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


NextBestActionType = Literal[
    "LEARN_TOPIC",
    "PRACTICE",
    "REVISE",
    "TAKE_QUIZ",
    "BUILD_PROJECT",
    "REVIEW_PROJECT",
    "INTERVIEW_PRACTICE",
    "MOVE_TO_NEXT_PHASE",
]


class NextBestAction(BaseModel):
    """One recommended learning action for the learner."""

    action: NextBestActionType
    topic: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    priority: str = Field(min_length=1)
    estimated_minutes: int = Field(gt=0)
    expected_outcome: str = Field(min_length=1)
