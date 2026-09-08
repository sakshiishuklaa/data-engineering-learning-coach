"""Streamlit rendering for Module 12 learning resources."""

from __future__ import annotations

import streamlit as st

from app.services.resource_recommendation import recommend_resources


def render_resources(topic: str, learner_level: str) -> None:
    """Display recommendations for the learner's current topic."""
    st.subheader(f"Recommended resources for {topic}")
    resources = recommend_resources(topic, learner_level)

    if not resources:
        st.info("No resources are available for this topic yet.")
        return

    for resource in resources:
        st.markdown(f"### {resource.title}")
        st.markdown(f"**Type:** {resource.resource_type}")
        st.markdown(f"**Difficulty:** {resource.difficulty}")
        st.markdown(f"**Description:** {resource.description}")
        st.markdown(f"**Link:** [{resource.title}]({resource.url})")
