"""Streamlit renderer for the Module 15.1 learner dashboard page."""

from __future__ import annotations

import streamlit as st
from sqlalchemy.orm import Session

from app.schemas.roadmap import PersonalizedRoadmap
from app.services.progress_service import get_progress_dashboard


def render_dashboard(
    session: Session,
    learner_id: int,
    roadmap: PersonalizedRoadmap | None = None,
) -> None:
    """Render only the five learner-facing dashboard sections for one learner."""
    dashboard = get_progress_dashboard(session, learner_id, roadmap=roadmap)

    st.subheader("Overall progress")
    st.metric("Overall progress", f"{dashboard.overall_progress_percentage}%")

    st.subheader("Current phase")
    if dashboard.current_phase is None:
        st.info("No current phase is available yet.")
    else:
        phase = dashboard.current_phase
        st.write(f"Phase {phase.phase}: {phase.goal}")
        st.progress(phase.completion_percentage / 100)
        st.caption(
            f"{phase.completion_percentage}% complete "
            f"({phase.completed_topics}/{phase.total_topics} topics)"
        )

    st.subheader("Today's task")
    if dashboard.upcoming_tasks:
        task = dashboard.upcoming_tasks[0]
        st.write(task.topic)
        st.caption(f"{task.status} · {task.completion_percentage}% complete")
    else:
        st.info("No task is currently available.")

    st.subheader("Next Best Action")
    st.write(dashboard.next_recommendation.title)
    st.caption(dashboard.next_recommendation.rationale)

    st.subheader("Current skill gaps")
    if dashboard.weak_areas:
        st.table(
            [
                {
                    "Skill": skill.skill,
                    "Current": skill.current_score,
                    "Target": skill.target_score,
                    "Gap": skill.improvement_needed,
                }
                for skill in dashboard.weak_areas
            ]
        )
    else:
        st.info("No current skill gaps are tracked.")
