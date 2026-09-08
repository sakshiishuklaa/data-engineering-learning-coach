"""Small progress-service adapter for adaptive next-action recommendations."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Learner, LearnerSkill, LearningProgress, QuizAttempt
from app.schemas.adaptive import NextBestAction
from app.schemas.roadmap import PersonalizedRoadmap
from app.services.adaptive_engine import get_next_best_action as decide_next_best_action
from app.services.skill_gap_service import parse_timeline_weeks


def get_next_best_action(
    session: Session,
    learner_id: int,
    roadmap: PersonalizedRoadmap | None = None,
    *,
    today: datetime | None = None,
) -> NextBestAction:
    """Retrieve the minimum persisted learner state and choose one next action."""
    learner = session.scalar(
        select(Learner)
        .where(Learner.id == learner_id)
        .options(selectinload(Learner.skills).selectinload(LearnerSkill.skill))
    )
    if learner is None:
        raise ValueError(f"Learner {learner_id} does not exist")

    progress_records = list(
        session.scalars(
            select(LearningProgress).where(LearningProgress.learner_id == learner_id)
        )
    )
    quiz_attempts = list(
        session.scalars(
            select(QuizAttempt)
            .where(QuizAttempt.learner_id == learner_id)
            .order_by(QuizAttempt.created_at, QuizAttempt.id)
        )
    )

    completed_topics = tuple(
        record.topic
        for record in progress_records
        if record.status == "completed" or record.completion_percentage >= 100
    )
    quiz_scores: dict[str, list[float]] = {}
    for attempt in quiz_attempts:
        quiz_scores.setdefault(attempt.topic, []).append(attempt.score)

    phase_priority = _phase_priority(roadmap)
    phase_prerequisites = _phase_prerequisites(roadmap)
    skill_gaps = [
        {
            "skill": learner_skill.skill.name,
            "gap": max(float(learner_skill.target_score) - float(learner_skill.proficiency_score), 0),
            "priority": phase_priority.get(learner_skill.skill.name, "GOOD_TO_LEARN"),
            "prerequisites": phase_prerequisites.get(learner_skill.skill.name, ()),
        }
        for learner_skill in learner.skills
    ]

    current_phase = _current_phase(roadmap, progress_records)
    timeline_weeks = _timeline_weeks(learner.target_timeline, roadmap)
    anchor = today or datetime.now().astimezone()
    weeks_elapsed = max((anchor.date() - learner.created_at.date()).days // 7, 0) if learner.created_at else 0

    state = {
        "skill_gaps": skill_gaps,
        "completed_topics": completed_topics,
        "quiz_scores": quiz_scores,
        "current_phase": current_phase,
        "prerequisites": phase_prerequisites,
        "timeline": {"weeks_elapsed": weeks_elapsed, "timeline_weeks": timeline_weeks},
    }
    return decide_next_best_action(state)


def _phase_priority(roadmap: PersonalizedRoadmap | None) -> dict[str, str]:
    if roadmap is None:
        return {}
    return {topic: phase.priority for phase in roadmap.phases for topic in phase.topics}


def _phase_prerequisites(roadmap: PersonalizedRoadmap | None) -> dict[str, tuple[str, ...]]:
    if roadmap is None:
        return {}
    return {topic: phase.prerequisites for phase in roadmap.phases for topic in phase.topics}


def _current_phase(roadmap: PersonalizedRoadmap | None, progress_records: list[LearningProgress]) -> int:
    if roadmap is None:
        return 1
    completion = {record.topic: record.completion_percentage for record in progress_records}
    for phase in roadmap.phases:
        if not all(completion.get(topic, 0) >= 100 for topic in phase.topics):
            return phase.phase
    return roadmap.phases[-1].phase


def _timeline_weeks(target_timeline: str | None, roadmap: PersonalizedRoadmap | None) -> int:
    if target_timeline:
        return parse_timeline_weeks(target_timeline)
    if roadmap is not None:
        return roadmap.timeline_weeks
    return 1
