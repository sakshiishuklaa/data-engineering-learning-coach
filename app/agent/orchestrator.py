"""Thin orchestration layer for agent requests."""

from __future__ import annotations

from typing import Any

from app.agent.intents import Intent
from app.agent.router import route_request
from app.schemas.teaching import TeachingRequest, TeachingSession
from app.services.adaptive_engine import get_next_best_action
from app.services.interview_service import list_interview_questions
from app.services.quiz_service import list_quiz_questions
from app.services.resource_recommendation import recommend_resources
from app.services.teaching_service import handle_teaching_command


def handle_request(user_message: str, learner_id: int) -> dict[str, Any]:
    """Route a request, invoke its available service, and wrap the result."""
    intent = route_request(user_message)
    result = _dispatch(intent, user_message, learner_id)
    return {
        "intent": intent,
        "learner_id": learner_id,
        "result": result,
    }


def _dispatch(intent: Intent, user_message: str, learner_id: int) -> Any:
    if intent in {Intent.LEARN, Intent.PRACTICE}:
        request = TeachingRequest(
            message=user_message,
            session=TeachingSession(session_id=str(learner_id)),
        )
        return handle_teaching_command(request)

    if intent is Intent.QUIZ:
        return list_quiz_questions()

    if intent is Intent.INTERVIEW:
        return list_interview_questions()

    if intent is Intent.RESOURCE:
        return recommend_resources(_topic_from_message(user_message), "beginner")

    if intent is Intent.NEXT_ACTION:
        return get_next_best_action({"learner_id": learner_id})

    return {
        "status": "not_connected",
        "reason": (
            f"{intent.value} requires structured learner context that is not "
            "available in handle_request yet."
        ),
    }


def _topic_from_message(message: str) -> str:
    normalized = message.casefold()
    for keyword, topic in (
        ("spark", "Spark"),
        ("python", "Python"),
        ("sql", "SQL"),
        ("etl", "ETL"),
        ("cloud", "Cloud"),
        ("warehouse", "Data Warehousing"),
        ("orchestration", "Orchestration"),
    ):
        if keyword in normalized:
            return topic
    return "Python"
