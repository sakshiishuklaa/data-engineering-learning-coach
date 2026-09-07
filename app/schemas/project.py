"""Schemas for project recommendation and review workflows."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

ProjectLevel = Literal[1, 2, 3, 4]
ProjectLevelName = Literal["Beginner", "Intermediate", "Advanced", "Production-style"]
ReviewCriterion = Literal[
    "Architecture",
    "Scalability",
    "Performance",
    "Data Quality",
    "Security",
    "Cost",
    "Monitoring",
    "Error handling",
    "Maintainability",
]


class ProjectRecommendationInput(BaseModel):
    """Learner context used to generate portfolio project recommendations."""

    learner_skill_level: ProjectLevelName
    current_roadmap_phase: int = Field(ge=1)
    target_role: str = Field(min_length=1)
    technologies_learned: tuple[str, ...] = ()
    missing_skills: tuple[str, ...] = ()
    preferred_cloud: str | None = None

    @model_validator(mode="after")
    def normalize_skills(self) -> "ProjectRecommendationInput":
        self.technologies_learned = _normalized_unique(self.technologies_learned)
        self.missing_skills = _normalized_unique(self.missing_skills)
        return self


class SchemaColumn(BaseModel):
    """A column in a recommended project table."""

    name: str
    data_type: str
    description: str


class ProjectTableSchema(BaseModel):
    """A table or file schema for the recommended project."""

    table_name: str
    grain: str
    columns: tuple[SchemaColumn, ...] = Field(min_length=1)


class ProjectRecommendation(BaseModel):
    """A complete, resume-ready data engineering project blueprint."""

    project_name: str
    level: ProjectLevel
    level_name: ProjectLevelName
    fit_reason: str
    business_problem: str
    data_source: str
    architecture: tuple[str, ...] = Field(min_length=1)
    technologies: tuple[str, ...] = Field(min_length=1)
    schema: tuple[ProjectTableSchema, ...] = Field(min_length=1)
    data_flow: tuple[str, ...] = Field(min_length=1)
    etl_steps: tuple[str, ...] = Field(min_length=1)
    data_quality_checks: tuple[str, ...] = Field(min_length=1)
    error_handling: tuple[str, ...] = Field(min_length=1)
    orchestration: str
    monitoring: tuple[str, ...] = Field(min_length=1)
    deployment: tuple[str, ...] = Field(min_length=1)
    github_structure: tuple[str, ...] = Field(min_length=1)
    resume_bullets: tuple[str, ...] = Field(min_length=1)
    interview_explanation: str


class ProjectRecommendationResult(BaseModel):
    """Project recommendation output grouped with the learner context."""

    target_role: str
    recommended_start_level: ProjectLevel
    missing_skills_to_practice: tuple[str, ...]
    recommendations: tuple[ProjectRecommendation, ...] = Field(min_length=1)


class ProjectReviewInput(BaseModel):
    """Submitted project details for review mode."""

    project_name: str = Field(min_length=1)
    target_role: str = Field(min_length=1)
    level: ProjectLevel
    architecture: str = ""
    technologies: tuple[str, ...] = ()
    schema: str = ""
    data_flow: str = ""
    etl_steps: tuple[str, ...] = ()
    data_quality_checks: tuple[str, ...] = ()
    error_handling: str = ""
    orchestration: str = ""
    monitoring: str = ""
    deployment: str = ""
    security_controls: tuple[str, ...] = ()
    cost_controls: tuple[str, ...] = ()
    performance_controls: tuple[str, ...] = ()
    repository_structure: tuple[str, ...] = ()

    @model_validator(mode="after")
    def normalize_tuple_fields(self) -> "ProjectReviewInput":
        self.technologies = _normalized_unique(self.technologies)
        self.etl_steps = _normalized_unique(self.etl_steps)
        self.data_quality_checks = _normalized_unique(self.data_quality_checks)
        self.security_controls = _normalized_unique(self.security_controls)
        self.cost_controls = _normalized_unique(self.cost_controls)
        self.performance_controls = _normalized_unique(self.performance_controls)
        self.repository_structure = _normalized_unique(self.repository_structure)
        return self


class ProjectReviewScore(BaseModel):
    """Score and feedback for one review criterion."""

    criterion: ReviewCriterion
    score: float = Field(ge=0, le=10)
    strengths: tuple[str, ...]
    improvements: tuple[str, ...]


class ProjectReviewResult(BaseModel):
    """Rubric-based review result for a learner project."""

    project_name: str
    target_role: str
    overall_score: float = Field(ge=0, le=10)
    readiness: str
    scores: tuple[ProjectReviewScore, ...]
    priority_improvements: tuple[str, ...]
    resume_readiness: str
    interview_guidance: str


def _normalized_unique(values: tuple[str, ...]) -> tuple[str, ...]:
    seen: set[str] = set()
    normalized: list[str] = []
    for value in values:
        cleaned = " ".join(value.strip().split())
        key = cleaned.lower()
        if cleaned and key not in seen:
            normalized.append(cleaned)
            seen.add(key)
    return tuple(normalized)
