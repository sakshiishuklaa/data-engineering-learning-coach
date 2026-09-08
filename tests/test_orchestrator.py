from unittest.mock import Mock, patch

from app.agent.intents import Intent
from app.agent.orchestrator import handle_request


def test_handle_request_routes_and_calls_teaching_service() -> None:
    service_result = {"message": "teaching response"}
    with patch("app.agent.orchestrator.handle_teaching_command", return_value=service_result) as service:
        response = handle_request("teach me spark", learner_id=7)

    assert response == {
        "intent": Intent.LEARN,
        "learner_id": 7,
        "result": service_result,
    }
    request = service.call_args.args[0]
    assert request.message == "teach me spark"
    assert request.session.session_id == "7"


def test_handle_request_calls_quiz_service() -> None:
    service_result = (Mock(name="question"),)
    with patch("app.agent.orchestrator.list_quiz_questions", return_value=service_result) as service:
        response = handle_request("quiz me", learner_id=11)

    service.assert_called_once_with()
    assert response["intent"] is Intent.QUIZ
    assert response["learner_id"] == 11
    assert response["result"] == service_result


def test_handle_request_returns_structured_response_when_context_is_missing() -> None:
    response = handle_request("build my roadmap", learner_id=3)

    assert response["intent"] is Intent.ROADMAP
    assert response["learner_id"] == 3
    assert response["result"]["status"] == "not_connected"
