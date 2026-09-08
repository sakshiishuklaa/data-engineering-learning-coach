import pytest

from app.agent.intents import Intent
from app.agent.router import route_request


@pytest.mark.parametrize(
    ("message", "expected_intent"),
    [
        ("build my roadmap", Intent.ROADMAP),
        ("teach me spark", Intent.LEARN),
        ("quiz me", Intent.QUIZ),
        ("interview me", Intent.INTERVIEW),
        ("show my progress", Intent.PROGRESS),
        ("what should I do next", Intent.NEXT_ACTION),
    ],
)
def test_route_request_matches_example_messages(
    message: str, expected_intent: Intent
) -> None:
    assert route_request(message) is expected_intent


@pytest.mark.parametrize(
    ("message", "expected_intent"),
    [
        ("Help me practice SQL", Intent.PRACTICE),
        ("Review my project", Intent.PROJECT_REVIEW),
        ("Recommend a resource", Intent.RESOURCE),
    ],
)
def test_route_request_handles_remaining_intents(
    message: str, expected_intent: Intent
) -> None:
    assert route_request(message) is expected_intent


def test_route_request_rejects_unrecognized_messages() -> None:
    with pytest.raises(ValueError, match="Could not determine an intent"):
        route_request("hello there")
