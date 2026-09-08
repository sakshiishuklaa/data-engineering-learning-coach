"""Edge-case coverage for learner state, routing, and structured LLM boundaries."""

from __future__ import annotations

from unittest.mock import Mock

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.agent.router import route_request
from app.database.base import Base
from app.schemas.assessment import AssessmentResult
from app.schemas.roadmap import RoadmapGenerationInput
from app.schemas.skill_gap import (
    LearnerProfileInput,
    LearnerSkillInput,
    SkillGapAnalysisResult,
    SkillGapNode,
)
from app.schemas.teaching import TeachingRequest, TeachingSession
from app.services.learner_memory_service import create_learner
from app.services.roadmap_service import generate_personalized_roadmap
from app.services.teaching_service import handle_teaching_command


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, class_=Session)
    database_session = session_factory()
    try:
        yield database_session
    finally:
        database_session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_new_learner_uses_safe_defaults(session: Session) -> None:
    learner = create_learner(session, name="New Learner")

    assert learner.id is not None
    assert learner.experience_years == 0
    assert learner.current_role is None
    assert learner.target_role is None
    assert learner.skills == []
    assert learner.progress_records == []


def test_profile_input_allows_missing_optional_profile_fields() -> None:
    profile = LearnerProfileInput()

    assert profile.current_role is None
    assert profile.experience_years is None
    assert profile.target_company_type is None
    assert profile.preferred_cloud is None
    assert profile.learning_preference is None


def test_session_with_no_completed_topics_starts_without_mastered_topics() -> None:
    session = TeachingSession(session_id="new-session")

    assert session.completed_topics == ()
    assert session.mastered_topics == ()


def test_all_topics_completed_falls_back_to_a_safe_next_topic() -> None:
    response = handle_teaching_command(
        TeachingRequest(
            message="next topic",
            session=TeachingSession(
                session_id="complete-session",
                completed_topics=("PySpark", "Data Modeling", "Data Warehousing", "Orchestration"),
            ),
        )
    )

    assert response.topic == "PySpark"
    assert response.command == "next_topic"


@pytest.mark.parametrize("invalid_score", [-0.1, 10.1])
def test_invalid_skill_score_is_rejected(invalid_score: float) -> None:
    with pytest.raises(ValidationError):
        LearnerSkillInput(skill="SQL", current_score=invalid_score)


def test_empty_user_message_is_rejected() -> None:
    with pytest.raises(ValueError, match="Could not determine an intent"):
        route_request("")


def test_unknown_user_message_is_rejected() -> None:
    with pytest.raises(ValueError, match="Could not determine an intent"):
        route_request("Tell me something unexpected")


def _roadmap_input() -> RoadmapGenerationInput:
    node = SkillGapNode(
        skill="SQL",
        category="Databases",
        current_score=4,
        target_score=7,
        gap=3,
        priority="High",
        status="in_progress",
        prerequisites=(),
        unlocks=(),
        estimated_hours=12,
        ready_to_learn=True,
    )
    analysis = SkillGapAnalysisResult(
        target_role="Data Engineer",
        timeline_weeks=4,
        study_hours_per_week=5,
        total_capacity_hours=20,
        required_gap_hours=12,
        capacity_status="manageable",
        nodes=(node,),
        edges=(),
        critical_gaps=(),
        ready_to_learn=("SQL",),
        blocked_skills=(),
    )
    return RoadmapGenerationInput(
        learner_profile=LearnerProfileInput(),
        skill_assessment=(
            AssessmentResult(
                skill="SQL",
                current_score=4,
                target_score=7,
                gap=3,
                level="Beginner",
                priority="High",
                confidence="Medium",
                evidence_sources=("Self report",),
            ),
        ),
        skill_gap_analysis=analysis,
        target_role="Data Engineer",
        target_timeline="4 weeks",
        weekly_study_hours=5,
    )


def test_llm_failure_returns_safe_roadmap_error() -> None:
    llm_client = Mock()
    llm_client.generate_roadmap.side_effect = RuntimeError("provider unavailable")

    result = generate_personalized_roadmap(_roadmap_input(), llm_client)

    assert result.success is False
    assert result.roadmap is None
    assert result.error == "Roadmap generation failed. Please retry later."


def test_invalid_llm_response_returns_validation_failure() -> None:
    llm_client = Mock()
    llm_client.generate_roadmap.return_value = {"target_role": "Data Engineer"}

    result = generate_personalized_roadmap(_roadmap_input(), llm_client)

    assert result.success is False
    assert result.roadmap is None
    assert result.error == "Roadmap generation failed. Please retry later."
