"""Integration tests for user-message routing through the agent orchestrator."""

from __future__ import annotations

from unittest.mock import Mock, patch

from app.agent.intents import Intent
from app.agent.orchestrator import handle_request


def test_user_to_roadmap_returns_structured_unconnected_response() -> None:
    response = handle_request("Build my roadmap", learner_id=21)

    assert response["intent"] is Intent.ROADMAP
    assert response["learner_id"] == 21
    assert response["result"] == {
        "status": "not_connected",
        "reason": "roadmap requires structured learner context that is not available in handle_request yet.",
    }


def test_user_to_learn_routes_to_teaching_service() -> None:
    service_result = {"message": "Here is a Spark lesson."}

    with patch("app.agent.orchestrator.handle_teaching_command", return_value=service_result) as service:
        response = handle_request("Teach me Spark", learner_id=22)

    assert response == {
        "intent": Intent.LEARN,
        "learner_id": 22,
        "result": service_result,
    }
    request = service.call_args.args[0]
    assert request.message == "Teach me Spark"
    assert request.session.session_id == "22"


def test_user_to_quiz_routes_to_quiz_service() -> None:
    service_result = (Mock(name="quiz_question"),)

    with patch("app.agent.orchestrator.list_quiz_questions", return_value=service_result) as service:
        response = handle_request("Give me a quiz", learner_id=23)

    service.assert_called_once_with()
    assert response["intent"] is Intent.QUIZ
    assert response["learner_id"] == 23
    assert response["result"] == service_result


def test_user_to_interview_routes_to_interview_service() -> None:
    service_result = (Mock(name="interview_question"),)

    with patch("app.agent.orchestrator.list_interview_questions", return_value=service_result) as service:
        response = handle_request("Start an interview", learner_id=24)

    service.assert_called_once_with()
    assert response["intent"] is Intent.INTERVIEW
    assert response["learner_id"] == 24
    assert response["result"] == service_result


def test_user_to_progress_returns_structured_unconnected_response() -> None:
    response = handle_request("Show my progress", learner_id=25)

    assert response["intent"] is Intent.PROGRESS
    assert response["learner_id"] == 25
    assert response["result"]["status"] == "not_connected"
    assert "structured learner context" in response["result"]["reason"]


def test_user_to_next_action_routes_learner_context_to_adaptive_engine() -> None:
    service_result = {
        "action": "LEARN_TOPIC",
        "topic": "SQL",
    }

    with patch("app.agent.orchestrator.get_next_best_action", return_value=service_result) as service:
        response = handle_request("What should I do next?", learner_id=26)

    service.assert_called_once_with({"learner_id": 26})
    assert response == {
        "intent": Intent.NEXT_ACTION,
        "learner_id": 26,
        "result": service_result,
    }
