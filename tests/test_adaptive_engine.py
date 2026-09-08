"""Scenario tests for the Module 13.3 adaptive decision engine."""

from __future__ import annotations

from dataclasses import dataclass

from app.services.adaptive_engine import get_next_best_action


def _state(**overrides: object) -> dict[str, object]:
    state: dict[str, object] = {
        "skill_gaps": [
            {"skill": "SQL", "gap": 8, "priority": "MUST_LEARN", "prerequisites": []},
            {"skill": "Python", "gap": 4, "priority": "GOOD_TO_LEARN", "prerequisites": []},
        ],
        "completed_topics": [],
        "quiz_scores": {},
        "current_phase": 1,
        "timeline": {"weeks_elapsed": 1, "timeline_weeks": 8},
    }
    state.update(overrides)
    return state


def test_prefers_must_learn_skill() -> None:
    action = get_next_best_action(_state())
    assert action.topic == "SQL"
    assert action.action == "LEARN_TOPIC"


def test_respects_incomplete_prerequisite() -> None:
    action = get_next_best_action(
        _state(
            skill_gaps=[{"skill": "PySpark", "gap": 9, "priority": "MUST_LEARN", "prerequisites": ["Python"]}],
            prerequisites={"PySpark": ["Python"]},
        )
    )
    assert action.topic == "Python"
    assert action.action == "LEARN_TOPIC"


def test_recommends_practice_after_repeated_failures() -> None:
    action = get_next_best_action(_state(quiz_scores={"SQL": [4, 5]}))
    assert action.topic == "SQL"
    assert action.action == "PRACTICE"


def test_completed_topic_is_skipped_without_revision_evidence() -> None:
    action = get_next_best_action(_state(completed_topics=["SQL"], quiz_scores={"SQL": [8]}))
    assert action.topic == "Python"


def test_completed_topic_can_be_revised_after_repeated_failures() -> None:
    action = get_next_best_action(_state(completed_topics=["SQL"], quiz_scores={"SQL": [4, 5]}))
    assert action.topic == "SQL"
    assert action.action == "REVISE"


def test_behind_schedule_prioritizes_high_impact_skill() -> None:
    action = get_next_best_action(
        _state(
            skill_gaps=[
                {"skill": "Optional Tool", "gap": 10, "priority": "OPTIONAL"},
                {"skill": "Core SQL", "gap": 7, "priority": "MUST_LEARN"},
            ],
            timeline={"weeks_elapsed": 9, "timeline_weeks": 8},
        )
    )
    assert action.topic == "Core SQL"


def test_returns_phase_action_when_no_skill_gaps_remain() -> None:
    action = get_next_best_action(_state(skill_gaps=[], current_phase=3))

    assert action.action == "MOVE_TO_NEXT_PHASE"
    assert action.topic == "Phase 3"
    assert action.estimated_minutes == 15


def test_accepts_mapping_skill_gaps_and_scalar_quiz_scores() -> None:
    action = get_next_best_action(
        {
            "skill_gaps": {"Python": {"gap": 10, "priority": "MUST_LEARN"}},
            "quiz_scores": {"Python": 5},
            "completed_topics": (),
            "current_phase": 2,
        }
    )

    assert action.topic == "Python"
    assert action.priority == "High"


@dataclass
class LearnerState:
    skill_gaps: list[object]
    completed_topics: tuple[str, ...] = ()
    quiz_scores: dict[str, object] | None = None
    current_phase: int = 1
    behind_schedule: bool | None = None
    timeline: dict[str, object] | None = None


@dataclass
class SkillGap:
    skill: str
    gap: float
    priority: str
    prerequisites: tuple[str, ...] = ()


def test_accepts_object_state_and_skill_gap_records() -> None:
    action = get_next_best_action(
        LearnerState(
            skill_gaps=[SkillGap("Airflow", 10, "MUST_LEARN")],
            quiz_scores={},
        )
    )

    assert action.topic == "Airflow"
    assert action.priority == "High"


def test_completed_prerequisite_unblocks_dependent_skill() -> None:
    action = get_next_best_action(
        _state(
            skill_gaps=[
                {"skill": "Spark", "gap": 9, "priority": "MUST_LEARN"},
            ],
            completed_topics=["Python"],
            prerequisites={"Spark": ["Python"]},
        )
    )

    assert action.topic == "Spark"
    assert action.action == "LEARN_TOPIC"


def test_explicit_schedule_flag_overrides_timeline_and_total_weeks_is_supported() -> None:
    not_behind = get_next_best_action(
        _state(
            behind_schedule=False,
            timeline={"weeks_elapsed": 10, "total_weeks": 8},
            skill_gaps=[{"skill": "SQL", "gap": 5, "priority": "OPTIONAL"}],
        )
    )
    behind = get_next_best_action(
        _state(
            timeline={"weeks_elapsed": 10, "total_weeks": 8},
            skill_gaps=[{"skill": "SQL", "gap": 5, "priority": "OPTIONAL"}],
        )
    )

    assert not_behind.priority == "Low"
    assert behind.priority == "Medium"
