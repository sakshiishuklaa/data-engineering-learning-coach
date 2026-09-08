"""Priority scoring helpers for adaptive learning recommendations."""

from __future__ import annotations

from numbers import Real


PRIORITY_WEIGHTS: dict[str, float] = {
    "skill_gap": 0.25,
    "role_relevance": 0.35,
    "prerequisite_importance": 0.25,
    "timeline_risk": 0.15,
}


def calculate_priority(
    skill_gap: float,
    role_relevance: float,
    prerequisite_importance: float,
    timeline_risk: float,
) -> float:
    """Return a weighted priority score from 0 to 100.

    Each input is a component score on the same 0-to-100 scale. The weights
    are kept at module level so the scoring policy can be configured without
    adding decision logic to this helper.
    """
    scores = {
        "skill_gap": skill_gap,
        "role_relevance": role_relevance,
        "prerequisite_importance": prerequisite_importance,
        "timeline_risk": timeline_risk,
    }
    for name, score in scores.items():
        if not isinstance(score, Real) or isinstance(score, bool) or not 0 <= score <= 100:
            raise ValueError(f"{name} must be between 0 and 100.")

    return sum(scores[name] * PRIORITY_WEIGHTS[name] for name in scores)
