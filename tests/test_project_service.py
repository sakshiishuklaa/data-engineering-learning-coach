"""Tests for Module 10 project recommendation and review engine."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.schemas.project import ProjectRecommendationInput, ProjectReviewInput
from app.services.project_service import recommend_projects, review_project


def _recommendation_input() -> ProjectRecommendationInput:
    return ProjectRecommendationInput(
        learner_skill_level="Intermediate",
        current_roadmap_phase=3,
        target_role="Data Engineer",
        technologies_learned=("Python", "SQL", "Docker"),
        missing_skills=("PySpark", "Data Quality", "Orchestration"),
        preferred_cloud="AWS",
    )


def test_recommend_projects_returns_all_levels_with_required_sections() -> None:
    result = recommend_projects(_recommendation_input())

    assert result.recommended_start_level == 2
    assert result.missing_skills_to_practice == ("PySpark", "Data Quality", "Orchestration")
    assert tuple(project.level for project in result.recommendations) == (1, 2, 3, 4)
    for project in result.recommendations:
        assert project.business_problem
        assert project.data_source
        assert project.architecture
        assert project.technologies
        assert project.schema
        assert project.data_flow
        assert project.etl_steps
        assert project.data_quality_checks
        assert project.error_handling
        assert project.orchestration
        assert project.monitoring
        assert project.deployment
        assert project.github_structure
        assert project.resume_bullets
        assert project.interview_explanation


def test_recommend_projects_personalizes_by_role_level_and_missing_skills() -> None:
    result = recommend_projects(
        ProjectRecommendationInput(
            learner_skill_level="Advanced",
            current_roadmap_phase=4,
            target_role="Analytics Engineer",
            technologies_learned=("dbt", "SQL"),
            missing_skills=("Data Warehousing",),
        )
    )

    assert result.recommended_start_level == 3
    assert result.recommendations[0].project_name == "Beginner Sales Analytics Warehouse"
    assert "dbt" in result.recommendations[1].technologies
    assert "Data Warehousing" in result.recommendations[2].interview_explanation


def test_review_project_scores_each_required_dimension_and_prioritizes_weaknesses() -> None:
    result = review_project(
        ProjectReviewInput(
            project_name="Orders Pipeline",
            target_role="Data Engineer",
            level=4,
            architecture="Raw files land in storage, Spark writes lake tables, and Airflow handles orchestration.",
            technologies=("Python", "PySpark", "Airflow"),
            schema="raw_orders and clean_orders tables",
            data_flow="incremental loads use partition dates and support backfill",
            etl_steps=("extract", "validate", "load"),
            data_quality_checks=("not null order_id", "unique order_id", "freshness check", "volume anomaly check"),
            error_handling="Retries failed tasks and quarantines invalid records with idempotent reloads.",
            orchestration="Airflow DAG",
            monitoring="Alerts track row count, duration, freshness, and failure metrics.",
            deployment="Docker and CI/CD",
            performance_controls=("partition pruning", "right-sized Spark cluster"),
            repository_structure=("README.md", "src/", "tests/", "configs/", "dags/"),
        )
    )

    assert len(result.scores) == 9
    assert {score.criterion for score in result.scores} == {
        "Architecture",
        "Scalability",
        "Performance",
        "Data Quality",
        "Security",
        "Cost",
        "Monitoring",
        "Error handling",
        "Maintainability",
    }
    assert result.overall_score < 8
    assert result.readiness == "needs_targeted_improvements"
    assert any("secret management" in improvement for improvement in result.priority_improvements)
    assert "security" in result.interview_guidance.lower() or "cost" in result.interview_guidance.lower()


def test_review_project_can_mark_strong_project_as_portfolio_ready() -> None:
    result = review_project(
        ProjectReviewInput(
            project_name="Production Data Platform",
            target_role="Data Engineer",
            level=2,
            architecture="Raw API data lands in a warehouse stage, quality checks run before marts publish.",
            technologies=("Python", "SQL", "Airflow", "Docker"),
            schema="raw_events, stg_events, mart_events_daily",
            data_flow="incremental partitioned loads run in parallel and support backfill",
            etl_steps=("extract", "stage", "transform", "test", "publish"),
            data_quality_checks=("not null", "unique", "freshness", "range", "relationship", "volume"),
            error_handling="Retry transient failures, quarantine bad records, and rerun idempotent tasks.",
            orchestration="Airflow DAG",
            monitoring="Alert on failure, row count changes, freshness misses, duration spikes, and metrics.",
            deployment="Docker Compose",
            security_controls=("secrets in environment", "least privilege IAM", "encrypt storage"),
            cost_controls=("budget alert", "right-size compute", "storage lifecycle rules"),
            performance_controls=("partition tables", "index keys", "cache small dimensions"),
            repository_structure=("README.md", "src/", "tests/", "config/", "docs/", "dags/"),
        )
    )

    assert result.overall_score >= 8
    assert result.readiness == "portfolio_ready"
    assert result.priority_improvements == ()


def test_project_endpoints_return_structured_results() -> None:
    with TestClient(app) as client:
        recommendation_response = client.post(
            "/projects/recommendations",
            json={
                "learner_skill_level": "Beginner",
                "current_roadmap_phase": 1,
                "target_role": "Data Engineer",
                "technologies_learned": ["Python"],
                "missing_skills": ["SQL"],
            },
        )
        review_response = client.post(
            "/projects/review",
            json={
                "project_name": "Local Pipeline",
                "target_role": "Data Engineer",
                "level": 1,
                "architecture": "Raw CSV to SQLite warehouse",
                "data_quality_checks": ["not null id"],
                "repository_structure": ["README.md", "src/", "tests/"],
            },
        )

    assert recommendation_response.status_code == 200
    assert recommendation_response.json()["recommended_start_level"] == 1
    assert len(recommendation_response.json()["recommendations"]) == 4
    assert review_response.status_code == 200
    assert review_response.json()["project_name"] == "Local Pipeline"
