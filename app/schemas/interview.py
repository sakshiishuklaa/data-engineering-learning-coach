"""Schemas for Module 11 data engineering interview practice."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

InterviewMode = Literal[
    "SQL",
    "Python",
    "Spark",
    "AWS",
    "Azure",
    "ETL",
    "Data Warehousing",
    "System Design",
    "Scenario-based",
]
InterviewDifficulty = Literal["Junior", "Mid-level", "Senior"]


class InterviewQuestionRequest(BaseModel):
    """Request for a targeted interview question."""

    mode: InterviewMode
    difficulty: InterviewDifficulty
    previous_answer: str | None = None
    previous_missing_concepts: tuple[str, ...] = ()


class InterviewQuestion(BaseModel):
    """One interview question with its rubric."""

    question_id: str = Field(min_length=1)
    mode: InterviewMode
    difficulty: InterviewDifficulty
    question: str = Field(min_length=1)
    expected_concepts: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def expected_concepts_must_be_clean(self) -> "InterviewQuestion":
        normalized = [" ".join(concept.strip().split()) for concept in self.expected_concepts]
        if any(not concept for concept in normalized):
            raise ValueError("Expected concepts must not be blank.")
        if len({concept.lower() for concept in normalized}) != len(normalized):
            raise ValueError("Expected concepts must be unique.")
        self.expected_concepts = tuple(normalized)
        return self


class InterviewAnswerSubmission(BaseModel):
    """Learner answer submitted for evaluation and persistence."""

    learner_id: int = Field(gt=0)
    question_id: str = Field(min_length=1)
    learner_answer: str = Field(min_length=1)


class InterviewEvaluation(BaseModel):
    """Structured interview feedback following the required flow."""

    score: float = Field(ge=0, le=10)
    evaluation: str = Field(min_length=1)
    missing_concepts: tuple[str, ...] = ()
    improved_interview_answer: str = Field(min_length=1)
    follow_up_question: str = Field(min_length=1)


class InterviewAnswerResult(BaseModel):
    """Persisted interview attempt result."""

    attempt_id: int
    learner_id: int
    question: InterviewQuestion
    learner_answer: str
    evaluation: InterviewEvaluation
    created_at: datetime


class InterviewAttemptSummary(BaseModel):
    """Compact historical interview performance item."""

    attempt_id: int
    mode: InterviewMode
    difficulty: InterviewDifficulty
    question: str
    score: float = Field(ge=0, le=10)
    missing_concepts: tuple[str, ...]
    created_at: datetime


class InterviewReport(BaseModel):
    """Aggregated interview performance report for one learner."""

    learner_id: int
    strengths: tuple[str, ...]
    weaknesses: tuple[str, ...]
    topics_to_revise: tuple[str, ...]
    average_score: float = Field(ge=0, le=10)
    recommended_next_topics: tuple[str, ...]
    attempts: tuple[InterviewAttemptSummary, ...]
