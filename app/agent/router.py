"""Deterministic routing for learner requests."""

from app.agent.intents import Intent


def route_request(user_message: str) -> Intent:
    """Return the intent indicated by a learner's message.

    Routing is intentionally keyword-based for now. Unsupported messages are
    rejected explicitly until a fallback intent is defined.
    """

    message = user_message.casefold()

    if "roadmap" in message:
        return Intent.ROADMAP
    if "next" in message and ("what should" in message or "do" in message):
        return Intent.NEXT_ACTION
    if "quiz" in message:
        return Intent.QUIZ
    if "interview" in message:
        return Intent.INTERVIEW
    if "progress" in message:
        return Intent.PROGRESS
    if "project" in message and ("review" in message or "feedback" in message):
        return Intent.PROJECT_REVIEW
    if "resource" in message:
        return Intent.RESOURCE
    if "practice" in message:
        return Intent.PRACTICE
    if "teach" in message or "learn" in message:
        return Intent.LEARN

    raise ValueError("Could not determine an intent for the request")
