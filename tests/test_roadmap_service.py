"""Tests for Module 5 personalized roadmap generation."""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.database.base import Base
from app.services.onboarding_service import save_onboarding_profile
import app.services.roadmap_service as roadmap_service
from app.schemas.assessment import AssessmentResult
from app.schemas.roadmap import PersonalizedRoadmap, RoadmapGenerationInput
from app.schemas.skill_gap import LearnerProfileInput, SkillGapAnalysisResult, SkillGapNode
from app.services.roadmap_service import generate_personalized_roadmap, validate_roadmap


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    database_session = sessionmaker(bind=engine, class_=Session)()
    Base.metadata.create_all(engine)
    try:
        yield database_session
    finally:
        database_session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def _onboarding_profile() -> dict[str, object]:
    return {
        "current_role": "Data Analyst",
        "experience_years": 2,
        "education": "Bachelor's degree",
        "python_level": "Intermediate",
        "sql_level": "Intermediate",
        "database_experience": "Beginner",
        "cloud_experience": "No experience",
        "git_github_level": "Beginner",
        "linux_level": "Beginner",
        "etl_elt_level": "No experience",
        "data_warehousing_level": "No experience",
        "spark_pyspark_level": "No experience",
        "airflow_orchestration_level": "No experience",
        "docker_level": "No experience",
        "existing_projects": None,
        "target_role": "Data Engineer",
        "target_company_type": "Product company",
        "preferred_cloud": "AWS",
        "study_hours_per_week": 8,
        "target_timeline": "6 months",
        "learning_preference": "Hands-on projects",
    }


class MockRoadmapLLMClient:
    """Simple structured-output fake for roadmap generation tests."""

    def __init__(self, response: Any = None, error: Exception | None = None) -> None:
        self.response = response
        self.error = error
        self.prompt = ""
        self.response_model: type[PersonalizedRoadmap] | None = None

    def generate_roadmap(self, *, prompt: str, response_model: type[PersonalizedRoadmap]) -> Any:
        self.prompt = prompt
        self.response_model = response_model
        if self.error is not None:
            raise self.error
        return self.response


def _node(
    skill: str,
    current_score: float,
    target_score: float,
    priority: str,
    prerequisites: tuple[str, ...] = (),
) -> SkillGapNode:
    return SkillGapNode(
        skill=skill,
        category="Data engineering",
        current_score=current_score,
        target_score=target_score,
        gap=round(max(target_score - current_score, 0), 1),
        priority=priority,
        status="met" if current_score >= target_score else "in_progress",
        prerequisites=prerequisites,
        unlocks=(),
        estimated_hours=24,
        ready_to_learn=True,
    )


def _generation_input() -> RoadmapGenerationInput:
    gap_analysis = SkillGapAnalysisResult(
        target_role="Data Engineer",
        timeline_weeks=8,
        study_hours_per_week=6,
        total_capacity_hours=48,
        required_gap_hours=72,
        capacity_status="tight",
        nodes=(
            _node("Python", 7, 7, "Low"),
            _node("SQL", 8, 7.5, "Low"),
            _node("PySpark", 1, 7, "Critical", ("Python",)),
            _node("Data Modeling", 1, 6.5, "High", ("SQL",)),
            _node("Data Warehousing", 1, 6.5, "High", ("Data Modeling",)),
            _node("Git", 5, 6, "Low"),
        ),
        edges=(),
        critical_gaps=("PySpark",),
        ready_to_learn=("PySpark", "Data Modeling", "Git"),
        blocked_skills=("Data Warehousing",),
    )
    return RoadmapGenerationInput(
        learner_profile=LearnerProfileInput(current_role="Data Analyst", experience_years=2),
        skill_assessment=(
            AssessmentResult(
                skill="PySpark",
                current_score=1,
                target_score=7,
                gap=6,
                level="Beginner",
                priority="Critical",
                confidence="High",
                evidence_sources=("Quiz",),
            ),
        ),
        skill_gap_analysis=gap_analysis,
        target_role="Data Engineer",
        target_timeline="8 weeks",
        weekly_study_hours=6,
    )


def _valid_roadmap_dict() -> dict[str, Any]:
    return {
        "target_role": "Data Engineer",
        "timeline_weeks": 8,
        "study_hours_per_week": 6,
        "total_estimated_weeks": 8,
        "phases": [
            {
                "phase": 1,
                "goal": "Build Spark foundations without repeating known Python.",
                "topics": ["PySpark"],
                "prerequisites": ["Python"],
                "priority": "MUST_LEARN",
                "estimated_duration_weeks": 3,
                "hands_on_exercises": ["Read partitioned files and run DataFrame transformations."],
                "mini_project": "Create a local PySpark batch job for CSV to parquet conversion.",
                "interview_questions": ["How does Spark distribute DataFrame work?"],
                "completion_criteria": ["Can write and explain a tested PySpark transformation."],
            },
            {
                "phase": 2,
                "goal": "Model analytics-ready data.",
                "topics": ["Data Modeling"],
                "prerequisites": ["SQL"],
                "priority": "MUST_LEARN",
                "estimated_duration_weeks": 2,
                "hands_on_exercises": ["Design facts and dimensions from event data."],
                "mini_project": "Build a star schema for product usage analytics.",
                "interview_questions": ["When would you denormalize analytics data?"],
                "completion_criteria": ["Can justify grain, keys, and table relationships."],
            },
            {
                "phase": 3,
                "goal": "Load modeled data into warehouse-style layers.",
                "topics": ["Data Warehousing"],
                "prerequisites": ["Data Modeling"],
                "priority": "MUST_LEARN",
                "estimated_duration_weeks": 2,
                "hands_on_exercises": ["Create staging, intermediate, and mart tables."],
                "mini_project": "Extend the model into a warehouse-style reporting layer.",
                "interview_questions": ["How do staging and mart layers differ?"],
                "completion_criteria": ["Can explain warehouse layers and load order."],
            },
            {
                "phase": 4,
                "goal": "Round out workflow basics.",
                "topics": ["Git"],
                "prerequisites": [],
                "priority": "OPTIONAL",
                "estimated_duration_weeks": 1,
                "hands_on_exercises": ["Use branches and pull-request style reviews."],
                "mini_project": "Version the previous projects with clean commits.",
                "interview_questions": ["How would you resolve a merge conflict?"],
                "completion_criteria": ["Can branch, commit, and review changes confidently."],
            },
        ],
    }


def test_generates_structured_roadmap_through_mock_llm_client() -> None:
    generation_input = _generation_input()
    client = MockRoadmapLLMClient(response=_valid_roadmap_dict())

    result = generate_personalized_roadmap(generation_input, client)

    assert result.success is True
    assert result.roadmap is not None
    assert client.response_model is PersonalizedRoadmap
    assert "structured JSON only" in client.prompt
    assert "Known skills to skip as topics" in client.prompt
    assert "Canonical allowed topic names: ['PySpark', 'Data Modeling', 'Data Warehousing', 'Git']" in client.prompt
    assert "MUST_LEARN skills that must all be covered: ['PySpark', 'Data Modeling', 'Data Warehousing']" in client.prompt
    assert "Preserve each learner-specific skill priority exactly as supplied in the skill gaps." in client.prompt
    assert "GOOD_TO_LEARN skills are useful but are not required MUST_LEARN skills" in client.prompt
    assert "never promote them to MUST_LEARN merely because they are generally important for a Data Engineer." in client.prompt
    assert "respect prerequisites" in client.prompt
    assert "Include every listed MUST_LEARN skill somewhere in the roadmap." in client.prompt
    assert "Advanced SQL, PySpark DataFrames, or Data Transformations" in client.prompt
    assert all("SQL" not in phase.topics for phase in result.roadmap.phases)


def test_rejects_roadmap_that_violates_known_topic_or_prerequisite_rules() -> None:
    generation_input = _generation_input()
    invalid_roadmap = _valid_roadmap_dict()
    invalid_roadmap["phases"][0]["topics"] = ["Data Warehousing", "SQL"]
    invalid_roadmap["phases"][0]["prerequisites"] = ["Data Modeling"]

    result = generate_personalized_roadmap(generation_input, MockRoadmapLLMClient(response=invalid_roadmap))

    assert result.success is False
    assert result.roadmap is None
    assert result.error == "Generated roadmap failed validation."
    assert any("already-known topic: SQL" in error for error in result.validation_errors)
    assert any("before prerequisites: Data Modeling" in error for error in result.validation_errors)


def test_validation_rejects_timeline_overrun_and_missing_must_learn_skills() -> None:
    generation_input = _generation_input()
    invalid_roadmap = PersonalizedRoadmap.model_validate(_valid_roadmap_dict() | {"timeline_weeks": 8})
    longer_roadmap = invalid_roadmap.model_copy(update={"total_estimated_weeks": 9})
    missing_required_roadmap = invalid_roadmap.model_copy(
        update={"phases": tuple(phase for phase in invalid_roadmap.phases if "PySpark" not in phase.topics)}
    )

    errors = validate_roadmap(longer_roadmap, generation_input)
    missing_errors = validate_roadmap(missing_required_roadmap, generation_input)

    assert "Roadmap exceeds the requested target timeline." in errors
    assert any("Roadmap omits MUST_LEARN skills" in error and "PySpark" in error for error in missing_errors)


def test_llm_failure_returns_graceful_error_without_raw_output() -> None:
    result = generate_personalized_roadmap(
        _generation_input(),
        MockRoadmapLLMClient(error=RuntimeError("API key missing")),
    )

    assert result.success is False
    assert result.roadmap is None
    assert result.error == "RuntimeError: API key missing"
    assert result.validation_errors == ()


def test_llm_failure_error_redacts_credentials() -> None:
    result = generate_personalized_roadmap(
        _generation_input(),
        MockRoadmapLLMClient(
            error=RuntimeError("Gemini request failed: GEMINI_API_KEY=gemini-secret")
        ),
    )

    assert result.success is False
    assert result.error is not None
    assert result.error.startswith("RuntimeError: ")
    assert "gemini-secret" not in result.error
    assert "[REDACTED" in result.error


def test_unparseable_llm_response_returns_graceful_error() -> None:
    result = generate_personalized_roadmap(
        _generation_input(),
        MockRoadmapLLMClient(response={"freeform": "learn spark then stuff"}),
    )

    assert result.success is False
    assert result.roadmap is None
    assert result.error is not None
    assert result.error.startswith("ValidationError:")


def test_generate_personalized_roadmap_for_learner_builds_persisted_context(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    saved_profile = save_onboarding_profile(session, _onboarding_profile())
    captured: dict[str, Any] = {}

    def fake_generate(generation_input: RoadmapGenerationInput, llm_client: Any) -> Any:
        captured["input"] = generation_input
        captured["client"] = llm_client
        return roadmap_service.RoadmapGenerationResult(success=True)

    monkeypatch.setattr(roadmap_service, "generate_personalized_roadmap", fake_generate)
    llm_client = object()

    result = roadmap_service.generate_personalized_roadmap_for_learner(
        session, saved_profile.learner_id, llm_client
    )

    generation_input = captured["input"]
    assert result.success is True
    assert captured["client"] is llm_client
    assert generation_input.target_role == "Data Engineer"
    assert generation_input.target_timeline == "6 months"
    assert generation_input.weekly_study_hours == 8
    assert generation_input.learner_profile.current_role == "Data Analyst"
    assert {skill.skill for skill in generation_input.skill_gap_analysis.nodes} >= {"Python", "PySpark"}
    assert "Cloud" not in {skill.skill for skill in generation_input.skill_gap_analysis.nodes}
    assert "Databases" not in {skill.skill for skill in generation_input.skill_gap_analysis.nodes}
    assert next(node for node in generation_input.skill_gap_analysis.nodes if node.skill == "PySpark").current_score == 0
    assert all(assessment.current_score >= 1 for assessment in generation_input.skill_assessment)
