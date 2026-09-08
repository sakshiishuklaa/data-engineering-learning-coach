"""Tests for the Module 15.1 dashboard page renderer."""

from dataclasses import dataclass, field

from app.schemas.progress import (
    NextRecommendation,
    PhaseProgressSummary,
    ProgressDashboard,
    SkillProgressSummary,
    TopicProgressSummary,
)
from app.ui import dashboard as dashboard_ui


@dataclass
class _FakeStreamlit:
    calls: list[tuple[str, object]] = field(default_factory=list)

    def subheader(self, value: str) -> None:
        self.calls.append(("subheader", value))

    def metric(self, label: str, value: str) -> None:
        self.calls.append(("metric", (label, value)))

    def write(self, value: str) -> None:
        self.calls.append(("write", value))

    def caption(self, value: str) -> None:
        self.calls.append(("caption", value))

    def progress(self, value: float) -> None:
        self.calls.append(("progress", value))

    def table(self, value: object) -> None:
        self.calls.append(("table", value))

    def info(self, value: str) -> None:
        self.calls.append(("info", value))


def _dashboard() -> ProgressDashboard:
    return ProgressDashboard(
        learner_id=1,
        learner_name="Asha Patel",
        overall_progress_percentage=42.5,
        roadmap_completion_percentage=40,
        topic_completion_percentage=40,
        skill_improvement_percentage=45,
        project_progress_percentage=50,
        quiz_average_score=None,
        study_streak_days=0,
        current_phase=PhaseProgressSummary(
            phase=2,
            goal="Build reliable pipelines",
            completion_percentage=25,
            completed_topics=1,
            total_topics=4,
            status="in_progress",
            topics=("Airflow",),
        ),
        phases=(),
        skills=(),
        completed_topics=(),
        upcoming_tasks=(
            TopicProgressSummary(
                topic="Airflow",
                status="in_progress",
                completion_percentage=25,
                last_activity_at="2026-09-08T00:00:00Z",
            ),
        ),
        weak_areas=(
            SkillProgressSummary(
                skill="Airflow",
                category="Orchestration",
                current_score=3,
                target_score=8,
                improvement_needed=5,
                progress_to_target_percentage=37.5,
            ),
        ),
        projects=(),
        recent_quiz_performance=(),
        next_recommendation=NextRecommendation(
            title="Continue Airflow",
            rationale="This topic is already 25% complete.",
            action_type="topic",
            topic="Airflow",
        ),
    )


def test_render_dashboard_uses_progress_service_and_displays_only_required_sections(monkeypatch) -> None:
    fake_streamlit = _FakeStreamlit()
    captured: dict[str, object] = {}

    def fake_get_progress_dashboard(session, learner_id, roadmap=None):
        captured.update(session=session, learner_id=learner_id, roadmap=roadmap)
        return _dashboard()

    monkeypatch.setattr(dashboard_ui, "st", fake_streamlit)
    monkeypatch.setattr(dashboard_ui, "get_progress_dashboard", fake_get_progress_dashboard)

    roadmap = object()
    dashboard_ui.render_dashboard("session", 7, roadmap=roadmap)

    assert captured == {"session": "session", "learner_id": 7, "roadmap": roadmap}
    assert [value for kind, value in fake_streamlit.calls if kind == "subheader"] == [
        "Overall progress",
        "Current phase",
        "Today's task",
        "Next Best Action",
        "Current skill gaps",
    ]
    rendered = "\n".join(str(value) for _, value in fake_streamlit.calls)
    assert "42.5%" in rendered
    assert "Phase 2: Build reliable pipelines" in rendered
    assert "Airflow" in rendered
    assert "Continue Airflow" in rendered
    assert "5" in rendered
    assert "Roadmap Completion" not in rendered
    assert "Study Streak" not in rendered
    assert "Recent Quiz Performance" not in rendered


def test_render_dashboard_shows_empty_states_for_missing_phase_task_and_gaps(monkeypatch) -> None:
    fake_streamlit = _FakeStreamlit()
    snapshot = _dashboard().model_copy(
        update={"current_phase": None, "upcoming_tasks": (), "weak_areas": ()}
    )
    monkeypatch.setattr(dashboard_ui, "st", fake_streamlit)
    monkeypatch.setattr(dashboard_ui, "get_progress_dashboard", lambda *args, **kwargs: snapshot)

    dashboard_ui.render_dashboard("session", 1)

    assert ("info", "No current phase is available yet.") in fake_streamlit.calls
    assert ("info", "No task is currently available.") in fake_streamlit.calls
    assert ("info", "No current skill gaps are tracked.") in fake_streamlit.calls
