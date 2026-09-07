"""Tests for Module 11 data engineering interview agent."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import Session, sessionmaker

from app.database.base import Base
from app.database.session import get_db
from app.main import app
from app.models import InterviewAttempt
from app.schemas.interview import InterviewDifficulty, InterviewMode, InterviewQuestionRequest
from app.services.interview_service import (
    QUESTION_BANK,
    evaluate_interview_answer,
    get_interview_question,
    get_interview_report,
    submit_interview_answer,
)
from app.services.learner_memory_service import create_learner


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


def test_question_bank_covers_all_interview_modes_and_difficulties() -> None:
    expected_modes: set[InterviewMode] = {
        "SQL",
        "Python",
        "Spark",
        "AWS",
        "Azure",
        "ETL",
        "Data Warehousing",
        "System Design",
        "Scenario-based",
    }
    expected_difficulties: set[InterviewDifficulty] = {"Junior", "Mid-level", "Senior"}

    assert len(QUESTION_BANK) == len(expected_modes) * len(expected_difficulties)
    assert {(question.mode, question.difficulty) for question in QUESTION_BANK} == {
        (mode, difficulty) for mode in expected_modes for difficulty in expected_difficulties
    }
    assert all(question.question and question.expected_concepts for question in QUESTION_BANK)


def test_get_interview_question_can_target_previous_missing_concept() -> None:
    question = get_interview_question(
        InterviewQuestionRequest(
            mode="Spark",
            difficulty="Mid-level",
            previous_answer="I would repartition the data.",
            previous_missing_concepts=("data movement across executors",),
        )
    )

    assert question.question_id.startswith("followup-spark-mid-level-data-movement")
    assert "data movement across executors" in question.question
    assert question.expected_concepts[0] == "data movement across executors"
    assert question.mode == "Spark"


def test_evaluate_interview_answer_scores_missing_concepts_and_dependent_follow_up() -> None:
    question = get_interview_question(InterviewQuestionRequest(mode="SQL", difficulty="Mid-level"))

    result = evaluate_interview_answer(
        question,
        "I would use row_number over a partition by event_id and order by timestamp descending.",
    )

    assert result.score < 10
    assert "filter rank to one" in result.missing_concepts
    assert "filter rank to one" in result.follow_up_question
    assert "ROW_NUMBER window function" in result.improved_interview_answer


def test_submit_interview_answer_persists_attempt_and_report(session: Session) -> None:
    learner = create_learner(session, name="Asha Patel")
    sql_question = get_interview_question(InterviewQuestionRequest(mode="SQL", difficulty="Junior"))
    spark_question = get_interview_question(InterviewQuestionRequest(mode="Spark", difficulty="Senior"))

    first = submit_interview_answer(
        session,
        learner_id=learner.id,
        question_id=sql_question.question_id,
        learner_answer=(
            "I would join customers to orders, group by customer, calculate sum(order_value), "
            "and use having to filter totals over 1000."
        ),
    )
    second = submit_interview_answer(
        session,
        learner_id=learner.id,
        question_id=spark_question.question_id,
        learner_answer="I would check Spark UI for long tasks and use broadcast join if one side is small.",
    )

    attempts = list(session.scalars(select(InterviewAttempt).order_by(InterviewAttempt.id)))
    report = get_interview_report(session, learner.id)

    assert first.attempt_id == attempts[0].id
    assert second.evaluation.follow_up_question
    assert len(attempts) == 2
    assert attempts[0].mode == "SQL"
    assert report.average_score == round((first.evaluation.score + second.evaluation.score) / 2, 1)
    assert "Spark Senior interview practice" in report.recommended_next_topics
    assert report.attempts[0].attempt_id == second.attempt_id


def test_interview_endpoints_return_structured_results() -> None:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, class_=Session)
    api_session = session_factory()
    learner = create_learner(api_session, name="Asha Patel")

    def override_get_db():
        yield api_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            question_response = client.post(
                "/interviews/questions",
                json={"mode": "ETL", "difficulty": "Mid-level"},
            )
            answer_response = client.post(
                "/interviews/answers",
                json={
                    "learner_id": learner.id,
                    "question_id": question_response.json()["question_id"],
                    "learner_answer": (
                        "I would make the load idempotent with checkpoints, deduplication keys, "
                        "transactional upserts, and retries for transient failures."
                    ),
                },
            )
            report_response = client.get(f"/interviews/report/{learner.id}")
    finally:
        app.dependency_overrides.clear()
        api_session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()

    assert question_response.status_code == 200
    assert question_response.json()["mode"] == "ETL"
    assert answer_response.status_code == 200
    assert answer_response.json()["evaluation"]["score"] > 7
    assert answer_response.json()["evaluation"]["follow_up_question"]
    assert report_response.status_code == 200
    assert report_response.json()["average_score"] == answer_response.json()["evaluation"]["score"]
