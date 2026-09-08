"""Validation and persistence for the learner onboarding flow."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Learner, OnboardingProfile, Skill
from app.services.learner_memory_service import (
    add_skill_to_learner,
    create_learner,
    create_skill,
    get_learner_skill,
    update_learner_skill_score,
)

SKILL_LEVELS = ("No experience", "Beginner", "Intermediate", "Advanced")
SKILL_LEVEL_SCORES = {
    "No experience": 0.0,
    "Beginner": 3.0,
    "Intermediate": 6.0,
    "Advanced": 8.0,
}
ONBOARDING_SKILL_DEFINITIONS = (
    ("python_level", "Python", "Programming"),
    ("sql_level", "SQL", "Databases"),
    ("database_experience", "Databases", "Databases"),
    ("cloud_experience", "Cloud", "Cloud"),
    ("git_github_level", "Git", "Developer workflow"),
    ("linux_level", "Linux", "Developer workflow"),
    ("etl_elt_level", "ETL/ELT", "Data pipelines"),
    ("data_warehousing_level", "Data Warehousing", "Analytics engineering"),
    ("spark_pyspark_level", "Spark/PySpark", "Distributed processing"),
    ("airflow_orchestration_level", "Orchestration", "Data pipelines"),
    ("docker_level", "Docker", "DevOps"),
)
REQUIRED_TEXT_FIELDS = (
    "current_role",
    "education",
    "target_role",
    "target_company_type",
    "preferred_cloud",
    "target_timeline",
    "learning_preference",
)
SKILL_FIELDS = (
    "python_level",
    "sql_level",
    "database_experience",
    "cloud_experience",
    "git_github_level",
    "linux_level",
    "etl_elt_level",
    "data_warehousing_level",
    "spark_pyspark_level",
    "airflow_orchestration_level",
    "docker_level",
)
ONBOARDING_FIELDS = set(REQUIRED_TEXT_FIELDS) | set(SKILL_FIELDS) | {
    "experience_years",
    "existing_projects",
    "study_hours_per_week",
}


def validate_onboarding_profile(profile: dict[str, Any]) -> dict[str, Any]:
    """Return cleaned onboarding input or raise ``ValueError`` with all validation errors."""
    unknown_fields = set(profile) - ONBOARDING_FIELDS
    missing_fields = ONBOARDING_FIELDS - set(profile)
    errors: list[str] = []
    if unknown_fields:
        errors.append(f"Unsupported fields: {', '.join(sorted(unknown_fields))}")
    if missing_fields:
        errors.append(f"Missing fields: {', '.join(sorted(missing_fields))}")

    cleaned = dict(profile)
    for field in REQUIRED_TEXT_FIELDS:
        value = str(cleaned.get(field, "")).strip()
        if not value:
            errors.append(f"{field.replace('_', ' ').capitalize()} is required.")
        cleaned[field] = value
    for field in SKILL_FIELDS:
        if cleaned.get(field) not in SKILL_LEVELS:
            errors.append(f"{field.replace('_', ' ').capitalize()} must be a valid skill level.")
    cleaned["existing_projects"] = str(cleaned.get("existing_projects") or "").strip() or None

    for field, maximum in (("experience_years", 80), ("study_hours_per_week", 168)):
        try:
            value = float(cleaned.get(field))
        except (TypeError, ValueError):
            errors.append(f"{field.replace('_', ' ').capitalize()} must be a number.")
            continue
        if not 0 <= value <= maximum or (field == "study_hours_per_week" and value == 0):
            lower_bound = "more than 0" if field == "study_hours_per_week" else "at least 0"
            errors.append(f"{field.replace('_', ' ').capitalize()} must be {lower_bound} and no more than {maximum}.")
        cleaned[field] = value

    if errors:
        raise ValueError(" ".join(errors))
    return cleaned


def get_onboarding_profile(session: Session, learner_id: int) -> OnboardingProfile | None:
    return session.get(OnboardingProfile, learner_id)


def get_existing_onboarding_profile(session: Session) -> OnboardingProfile | None:
    """Find the existing local profile so returning users are not onboarded again."""
    return session.scalar(select(OnboardingProfile).order_by(OnboardingProfile.learner_id))


def _persist_onboarding_skills(session: Session, learner_id: int, profile: dict[str, Any]) -> None:
    for field, skill_name, category in ONBOARDING_SKILL_DEFINITIONS:
        skill = get_skill_by_name(session, skill_name)
        if skill is None:
            skill = create_skill(session, name=skill_name, category=category)

        score = SKILL_LEVEL_SCORES[profile[field]]
        learner_skill = get_learner_skill(session, learner_id, skill.id)
        if learner_skill is None:
            add_skill_to_learner(session, learner_id, skill.id, proficiency_score=score, target_score=10)
        else:
            update_learner_skill_score(session, learner_id, skill.id, proficiency_score=score, target_score=10)


def get_skill_by_name(session: Session, name: str) -> Skill | None:
    return session.scalar(select(Skill).where(Skill.name == name))


def save_onboarding_profile(session: Session, profile: dict[str, Any]) -> OnboardingProfile:
    """Create the local learner/profile pair or update the existing onboarding profile."""
    cleaned = validate_onboarding_profile(profile)
    onboarding_profile = get_existing_onboarding_profile(session)
    if onboarding_profile is None:
        learner = create_learner(
            session,
            name="Learner",
            experience_years=cleaned["experience_years"],
            current_role=cleaned["current_role"],
            target_role=cleaned["target_role"],
            target_company_type=cleaned["target_company_type"],
            target_timeline=cleaned["target_timeline"],
            study_hours_per_week=cleaned["study_hours_per_week"],
            preferred_cloud=cleaned["preferred_cloud"],
        )
        onboarding_profile = OnboardingProfile(learner_id=learner.id, **cleaned)
        session.add(onboarding_profile)
    else:
        for field, value in cleaned.items():
            setattr(onboarding_profile, field, value)
        learner = onboarding_profile.learner
        learner.experience_years = cleaned["experience_years"]
        learner.current_role = cleaned["current_role"]
        learner.target_role = cleaned["target_role"]
        learner.target_company_type = cleaned["target_company_type"]
        learner.target_timeline = cleaned["target_timeline"]
        learner.study_hours_per_week = cleaned["study_hours_per_week"]
        learner.preferred_cloud = cleaned["preferred_cloud"]
    _persist_onboarding_skills(session, learner.id, cleaned)
    session.commit()
    session.refresh(onboarding_profile)
    return onboarding_profile
