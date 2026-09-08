"""Deterministic next-best-action selection for adaptive learning."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from app.schemas.adaptive import NextBestAction
from app.services.adaptive_priority import calculate_priority


def get_next_best_action(learner_state: Any) -> NextBestAction:
    """Select exactly one next action from a learner-state snapshot.

    ``learner_state`` may be a mapping or an object with matching attributes.
    Skill gaps may be supplied as a mapping of topic to gap score or as a
    sequence of records containing at least ``skill`` and ``gap``.
    """
    completed = {_normalize(topic) for topic in _value(learner_state, "completed_topics", ())}
    quiz_scores = _quiz_scores(_value(learner_state, "quiz_scores", {}))
    current_phase = _value(learner_state, "current_phase", 1)
    skills = _skill_records(learner_state)

    if not skills:
        return _phase_action(current_phase)

    behind_schedule = _is_behind_schedule(learner_state)
    prerequisites = _value(learner_state, "prerequisites", {})
    candidates: list[dict[str, Any]] = []

    for record in skills:
        topic = str(record.get("skill", record.get("topic", ""))).strip()
        if not topic:
            continue
        topic_key = _normalize(topic)
        scores = quiz_scores.get(topic_key, ())
        repeated_failure = len(scores) >= 2 and all(score < 6 for score in scores[-2:])
        topic_prerequisites = tuple(record.get("prerequisites", ())) or tuple(
            _mapping_value(prerequisites, topic, ())
        )
        missing_prerequisites = tuple(
            prerequisite for prerequisite in topic_prerequisites if _normalize(prerequisite) not in completed
        )

        # Completed topics are eligible only when quiz evidence justifies revision.
        if topic_key in completed and not repeated_failure:
            continue

        # A missing prerequisite must be selected before its dependent skill.
        if missing_prerequisites:
            prerequisite = missing_prerequisites[0]
            candidates.append(
                {
                    "topic": prerequisite,
                    "action": "LEARN_TOPIC",
                    "reason": f"Learn prerequisite {prerequisite} before progressing to {topic}.",
                    "score": 100.0 if record.get("priority") == "MUST_LEARN" else 80.0,
                    "estimated_minutes": 45,
                    "outcome": f"Complete {prerequisite} so {topic} is unblocked.",
                }
            )
            continue

        gap = _as_percentage(record.get("gap", record.get("skill_gap", 0)))
        role_relevance = float(record.get("role_relevance", _role_relevance(record)))
        prerequisite_importance = float(
            record.get("prerequisite_importance", 100 if record.get("prerequisites") else 0)
        )
        timeline_risk = 100.0 if behind_schedule else float(record.get("timeline_risk", 0))
        priority_score = calculate_priority(gap, role_relevance, prerequisite_importance, timeline_risk)
        if record.get("priority") == "MUST_LEARN":
            priority_score += 10
        if behind_schedule:
            priority_score += 5
        if repeated_failure:
            priority_score += 100

        if repeated_failure:
            action = "REVISE" if topic_key in completed else "PRACTICE"
            reason = f"Recent quiz attempts show repeated difficulty with {topic}."
            outcome = f"Strengthen {topic} before attempting the next assessment."
        else:
            action = "LEARN_TOPIC"
            reason = f"{topic} is a high-priority skill gap for the current learning path."
            outcome = f"Build foundational understanding of {topic}."

        candidates.append(
            {
                "topic": topic,
                "action": action,
                "reason": reason,
                "score": priority_score,
                "estimated_minutes": 30 if action != "REVISE" else 25,
                "outcome": outcome,
            }
        )

    if not candidates:
        return _phase_action(current_phase)

    selected = max(candidates, key=lambda candidate: (candidate["score"], _normalize(candidate["topic"])))
    return NextBestAction(
        action=selected["action"],
        topic=selected["topic"],
        reason=selected["reason"],
        priority=_priority_label(selected["score"]),
        estimated_minutes=selected["estimated_minutes"],
        expected_outcome=selected["outcome"],
    )


def _skill_records(learner_state: Any) -> list[dict[str, Any]]:
    raw = _value(learner_state, "skill_gaps", ())
    if isinstance(raw, Mapping):
        records = []
        for skill, value in raw.items():
            records.append({"skill": skill, "gap": value} if not isinstance(value, Mapping) else {"skill": skill, **value})
        return records
    return [_record(item) for item in raw]


def _record(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if hasattr(value, "model_dump"):
        return value.model_dump()
    return {name: getattr(value, name) for name in ("skill", "gap", "priority", "prerequisites") if hasattr(value, name)}


def _quiz_scores(value: Any) -> dict[str, tuple[float, ...]]:
    if isinstance(value, Mapping):
        result: dict[str, tuple[float, ...]] = {}
        for topic, scores in value.items():
            if isinstance(scores, Sequence) and not isinstance(scores, (str, bytes)):
                result[_normalize(topic)] = tuple(float(score) for score in scores)
            else:
                result[_normalize(topic)] = (float(scores),)
        return result
    return {}


def _is_behind_schedule(state: Any) -> bool:
    explicit = _value(state, "behind_schedule", None)
    if explicit is not None:
        return bool(explicit)
    timeline = _value(state, "timeline", None)
    if isinstance(timeline, Mapping):
        if "behind_schedule" in timeline:
            return bool(timeline["behind_schedule"])
        elapsed = timeline.get("weeks_elapsed")
        total = timeline.get("timeline_weeks", timeline.get("total_weeks"))
        if elapsed is not None and total is not None:
            return float(elapsed) > float(total)
    return False


def _phase_action(current_phase: Any) -> NextBestAction:
    return NextBestAction(
        action="MOVE_TO_NEXT_PHASE",
        topic=f"Phase {current_phase}",
        reason="Current tracked topics do not have an eligible remaining action.",
        priority="Medium",
        estimated_minutes=15,
        expected_outcome=f"Progress to the next learning phase after phase {current_phase}.",
    )


def _value(source: Any, name: str, default: Any) -> Any:
    if isinstance(source, Mapping):
        return source.get(name, default)
    return getattr(source, name, default)


def _mapping_value(source: Any, key: str, default: Any) -> Any:
    if isinstance(source, Mapping):
        return source.get(key, default)
    return default


def _as_percentage(value: Any) -> float:
    number = float(value)
    return number * 10 if 0 <= number <= 10 else number


def _role_relevance(record: Mapping[str, Any]) -> float:
    return {"MUST_LEARN": 100.0, "GOOD_TO_LEARN": 70.0, "OPTIONAL": 40.0}.get(record.get("priority"), 50.0)


def _priority_label(score: float) -> str:
    if score >= 80:
        return "Critical"
    if score >= 60:
        return "High"
    if score >= 35:
        return "Medium"
    return "Low"


def _normalize(value: Any) -> str:
    return str(value).strip().lower()
