"""Tests for the Module 12.2 resource recommendation service."""

import pytest

from app.services.resource_recommendation import recommend_resources


def test_recommendations_are_topic_specific_and_capped_at_three() -> None:
    resources = recommend_resources("sql", "beginner")

    assert len(resources) <= 3
    assert resources
    assert all(resource.topic == "SQL" for resource in resources)


def test_recommendations_prioritize_official_then_learning_then_practice() -> None:
    resources = recommend_resources("SQL", "Intermediate")

    assert [resource.resource_type for resource in resources] == [
        "Official documentation",
        "Learning resource",
        "Practice",
    ]


def test_recommendations_match_learner_level_within_priority_group() -> None:
    beginner_resources = recommend_resources("Spark", "beginner")
    advanced_resources = recommend_resources("Spark", "advanced")

    assert beginner_resources[0].difficulty == "Beginner" or beginner_resources[0].difficulty == "Intermediate"
    assert advanced_resources[0].difficulty == "Intermediate"
    assert [resource.id for resource in beginner_resources] == [resource.id for resource in advanced_resources]


def test_unknown_topic_returns_no_resources() -> None:
    assert recommend_resources("Kubernetes", "Beginner") == []


def test_unsupported_learner_level_is_rejected() -> None:
    with pytest.raises(ValueError, match="Unsupported learner level"):
        recommend_resources("SQL", "Expert")
