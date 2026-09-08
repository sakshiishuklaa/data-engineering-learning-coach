"""Intent definitions for the learning-coach agent."""

from enum import Enum


class Intent(str, Enum):
    """Supported high-level learner intents."""

    ROADMAP = "roadmap"
    LEARN = "learn"
    PRACTICE = "practice"
    QUIZ = "quiz"
    PROGRESS = "progress"
    PROJECT_REVIEW = "project_review"
    INTERVIEW = "interview"
    RESOURCE = "resource"
    NEXT_ACTION = "next_action"
