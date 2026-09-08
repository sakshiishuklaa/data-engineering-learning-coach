"""Integration tests for persisted progress and adaptive recommendations."""

from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.database.base import Base
from app.models import QuizAttempt
from app.schemas.roadmap import PersonalizedRoadmap, RoadmapPhase
from app.services.learner_memory_service import (
    add_skill_to_learner,
    create_learner,
    create_learning_progress,
    create_skill,
)
from app.services.progress import get_next_best_action


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    database_session = sessionmaker(bind=engine, class_=Session)()
    try:
        yield database_session
    finally:
        database_session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def _roadmap() -> PersonalizedRoadmap:
    return PersonalizedRoadmap(
        target_role="Data Engineer",
        timeline_weeks=6,
        study_hours_per_week=8,
        total_estimated_weeks=6,
        phases=(
            RoadmapPhase(
                phase=1,
                goal="Build SQL foundations",
                topics=("SQL",),
                prerequisites=(),
                priority="MUST_LEARN",
                estimated_duration_weeks=3,
                hands_on_exercises=("Write joins.",),
                mini_project="Build a reporting query.",
                interview_questions=("Explain joins.",),
                completion_criteria=("Complete the SQL task.",),
            ),
            RoadmapPhase(
                phase=2,
                goal="Build modeling foundations",
                topics=("Data Modeling",),
                prerequisites=("SQL",),
                priority="GOOD_TO_LEARN",
                estimated_duration_weeks=3,
                hands_on_exercises=("Design a star schema.",),
                mini_project="Model orders.",
                interview_questions=("What is grain?",),
                completion_criteria=("Explain the model.",),
            ),
        ),
    )


def test_integration_returns_next_best_action_from_persisted_skill_state(session: Session) -> None:
    learner = create_learner(session, name="Asha", target_timeline="6 weeks")
    sql = create_skill(session, name="SQL", category="Databases")
    add_skill_to_learner(session, learner.id, sql.id, proficiency_score=2, target_score=10)

    action = get_next_best_action(session, learner.id, _roadmap())

    assert action.action == "LEARN_TOPIC"
    assert action.topic == "SQL"
    assert action.expected_outcome


def test_integration_uses_completed_topics_and_quiz_history(session: Session) -> None:
    learner = create_learner(session, name="Asha", target_timeline="6 weeks")
    sql = create_skill(session, name="SQL", category="Databases")
    modeling = create_skill(session, name="Data Modeling", category="Analytics engineering")
    add_skill_to_learner(session, learner.id, sql.id, proficiency_score=6, target_score=10)
    add_skill_to_learner(session, learner.id, modeling.id, proficiency_score=2, target_score=10)
    create_learning_progress(session, learner.id, "SQL", status="completed", completion_percentage=100)
    for score in (4, 5):
        session.add(
            QuizAttempt(
                learner_id=learner.id,
                skill_id=sql.id,
                topic="SQL",
                difficulty="Beginner",
                question="Question",
                learner_answer="Answer",
                score=score,
                correct_points=[],
                missing_points=[],
                mistakes=[],
                improved_answer="Improved",
                recommended_action="Review.",
                created_at=datetime(2026, 9, 7, 9, 0),
            )
        )
    session.commit()

    action = get_next_best_action(session, learner.id, _roadmap())

    assert action.topic == "SQL"
    assert action.action == "REVISE"


def test_integration_respects_roadmap_prerequisites(session: Session) -> None:
    learner = create_learner(session, name="Asha", target_timeline="6 weeks")
    modeling = create_skill(session, name="Data Modeling", category="Analytics engineering")
    add_skill_to_learner(session, learner.id, modeling.id, proficiency_score=1, target_score=10)

    action = get_next_best_action(session, learner.id, _roadmap())

    assert action.topic == "SQL"
    assert action.action == "LEARN_TOPIC"
