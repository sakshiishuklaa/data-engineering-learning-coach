"""Module 10 project recommendation and review engine."""

from __future__ import annotations

from app.schemas.project import (
    ProjectRecommendation,
    ProjectRecommendationInput,
    ProjectRecommendationResult,
    ProjectReviewInput,
    ProjectReviewResult,
    ProjectReviewScore,
    ProjectTableSchema,
    SchemaColumn,
)

LEVEL_BY_NAME = {
    "Beginner": 1,
    "Intermediate": 2,
    "Advanced": 3,
    "Production-style": 4,
}

LEVEL_NAMES = {
    1: "Beginner",
    2: "Intermediate",
    3: "Advanced",
    4: "Production-style",
}

CORE_REVIEW_CRITERIA = (
    "Architecture",
    "Scalability",
    "Performance",
    "Data Quality",
    "Security",
    "Cost",
    "Monitoring",
    "Error handling",
    "Maintainability",
)


def recommend_projects(recommendation_input: ProjectRecommendationInput) -> ProjectRecommendationResult:
    """Generate four personalized portfolio projects from learner context."""
    start_level = LEVEL_BY_NAME[recommendation_input.learner_skill_level]
    learned = set(recommendation_input.technologies_learned)
    gaps = recommendation_input.missing_skills
    recommendations = tuple(
        _build_project(level, recommendation_input, learned, gaps)
        for level in (1, 2, 3, 4)
    )
    return ProjectRecommendationResult(
        target_role=recommendation_input.target_role.strip(),
        recommended_start_level=start_level,
        missing_skills_to_practice=gaps,
        recommendations=recommendations,
    )


def review_project(review_input: ProjectReviewInput) -> ProjectReviewResult:
    """Score a learner project against a production-minded data engineering rubric."""
    scores = tuple(_score_criterion(criterion, review_input) for criterion in CORE_REVIEW_CRITERIA)
    overall = round(sum(score.score for score in scores) / len(scores), 1)
    priority_improvements = tuple(
        improvement
        for score in sorted(scores, key=lambda item: item.score)
        for improvement in score.improvements[:1]
    )[:5]
    return ProjectReviewResult(
        project_name=review_input.project_name.strip(),
        target_role=review_input.target_role.strip(),
        overall_score=overall,
        readiness=_readiness(overall),
        scores=scores,
        priority_improvements=priority_improvements,
        resume_readiness=_resume_readiness(overall),
        interview_guidance=_interview_guidance(review_input, scores),
    )


def _build_project(
    level: int,
    recommendation_input: ProjectRecommendationInput,
    learned: set[str],
    gaps: tuple[str, ...],
) -> ProjectRecommendation:
    role = recommendation_input.target_role.strip()
    cloud = _cloud(recommendation_input.preferred_cloud)
    phase = recommendation_input.current_roadmap_phase
    technologies = _technologies_for_level(level, learned, gaps, cloud)
    theme = _theme_for_role(role, level)
    level_name = LEVEL_NAMES[level]
    return ProjectRecommendation(
        project_name=f"{level_name} {theme['name']}",
        level=level,
        level_name=level_name,
        fit_reason=_fit_reason(level, recommendation_input, technologies),
        business_problem=theme["business_problem"],
        data_source=theme["data_source"],
        architecture=_architecture_for_level(level, cloud),
        technologies=technologies,
        schema=_schema_for_level(level, theme["entity"]),
        data_flow=_data_flow_for_level(level),
        etl_steps=_etl_steps_for_level(level),
        data_quality_checks=_quality_checks_for_level(level),
        error_handling=_error_handling_for_level(level),
        orchestration=_orchestration_for_level(level),
        monitoring=_monitoring_for_level(level),
        deployment=_deployment_for_level(level, cloud),
        github_structure=_github_structure_for_level(level),
        resume_bullets=_resume_bullets(role, level, theme["entity"], technologies),
        interview_explanation=_interview_explanation(role, level, theme["entity"], phase, gaps),
    )


def _theme_for_role(target_role: str, level: int) -> dict[str, str]:
    normalized_role = target_role.lower()
    if "analytics" in normalized_role:
        themes = {
            1: {
                "name": "Sales Analytics Warehouse",
                "entity": "orders",
                "business_problem": "Help a revenue team understand order trends, refund rates, and top-performing products from raw sales exports.",
                "data_source": "CSV exports from an ecommerce orders system plus a products lookup table.",
            },
            2: {
                "name": "Marketing Attribution Mart",
                "entity": "campaigns",
                "business_problem": "Unify campaign spend and web conversion data so analysts can compare cost per acquisition by channel.",
                "data_source": "Public ad-spend CSV files, Google Analytics sample exports, and a channel mapping seed file.",
            },
            3: {
                "name": "Subscription Metrics Platform",
                "entity": "subscriptions",
                "business_problem": "Build reliable MRR, churn, cohort retention, and expansion metrics from product and billing events.",
                "data_source": "Synthetic Stripe-like invoices, product events, and customer dimension snapshots.",
            },
            4: {
                "name": "Executive Metrics Lakehouse",
                "entity": "metrics",
                "business_problem": "Serve trusted company KPIs with lineage, quality gates, backfills, and stakeholder-ready data contracts.",
                "data_source": "Batch files, application database extracts, and event streams from a simulated SaaS business.",
            },
        }
    else:
        themes = {
            1: {
                "name": "Batch Orders Pipeline",
                "entity": "orders",
                "business_problem": "Load messy order files into clean analytical tables so operations can track delayed shipments and revenue.",
                "data_source": "Kaggle-style retail CSV files or generated daily order extracts.",
            },
            2: {
                "name": "API to Warehouse Pipeline",
                "entity": "events",
                "business_problem": "Collect product activity from an API and create query-ready event tables for growth and product analysis.",
                "data_source": "REST API responses from a public API or a local FastAPI mock service.",
            },
            3: {
                "name": "Spark Lakehouse Pipeline",
                "entity": "transactions",
                "business_problem": "Process large transaction data and produce partitioned, optimized datasets for fraud and finance reporting.",
                "data_source": "Generated multi-million-row transaction files with reference customer and merchant data.",
            },
            4: {
                "name": "Production Data Platform",
                "entity": "customer_activity",
                "business_problem": "Operate a production-style batch and streaming platform with quality gates, recovery, monitoring, and deployment automation.",
                "data_source": "Simulated CDC records, event streams, and daily object-storage drops.",
            },
        }
    return themes[level]


def _technologies_for_level(level: int, learned: set[str], gaps: tuple[str, ...], cloud: str) -> tuple[str, ...]:
    defaults = {
        1: ("Python", "SQL", "Pandas", "SQLite", "pytest"),
        2: ("Python", "SQL", "PostgreSQL", "dbt", "Airflow", "Docker"),
        3: ("Python", "PySpark", "Parquet", "Data Lake", "Airflow", "Docker"),
        4: ("Python", "PySpark", "Airflow", "Docker", "CI/CD", cloud, "Great Expectations", "Terraform"),
    }
    selected = list(defaults[level])
    for technology in learned:
        if technology not in selected and _technology_fits_level(technology, level):
            selected.append(technology)
    for skill in gaps:
        if len(selected) >= 10:
            break
        if skill not in selected and _technology_fits_level(skill, level):
            selected.append(skill)
    return tuple(selected)


def _technology_fits_level(technology: str, level: int) -> bool:
    advanced = {"PySpark", "Spark Optimization", "CI/CD", "Terraform", "Kubernetes"}
    if level <= 2 and technology in advanced:
        return False
    return True


def _architecture_for_level(level: int, cloud: str) -> tuple[str, ...]:
    architectures = {
        1: ("Raw CSV landing folder", "Python extraction script", "SQLite staging tables", "SQL analytics views"),
        2: ("API ingestion container", "PostgreSQL raw schema", "dbt staging and marts", "Airflow DAG for scheduled runs"),
        3: ("Object storage landing zone", "Spark transformation jobs", "Partitioned Parquet lake", "Warehouse-ready aggregated outputs"),
        4: (
            f"{cloud} object storage landing zone",
            "CDC and event ingestion layer",
            "Spark processing with bronze, silver, and gold datasets",
            "Airflow orchestration with backfills",
            "CI/CD deployment pipeline",
        ),
    }
    return architectures[level]


def _schema_for_level(level: int, entity: str) -> tuple[ProjectTableSchema, ...]:
    raw_columns = (
        SchemaColumn(name=f"{entity}_id", data_type="string", description="Source-system identifier."),
        SchemaColumn(name="source_file", data_type="string", description="Input file or source batch name."),
        SchemaColumn(name="ingested_at", data_type="timestamp", description="Time the record entered the pipeline."),
    )
    clean_columns = (
        SchemaColumn(name=f"{entity}_key", data_type="string", description="Canonical analytics key."),
        SchemaColumn(name="event_date", data_type="date", description="Business date used for partitioning and reporting."),
        SchemaColumn(name="status", data_type="string", description="Validated lifecycle or processing status."),
        SchemaColumn(name="amount", data_type="decimal", description="Metric value for reporting where applicable."),
    )
    mart_columns = (
        SchemaColumn(name="date_key", data_type="date", description="Reporting date."),
        SchemaColumn(name="dimension_name", data_type="string", description="Primary reporting dimension."),
        SchemaColumn(name="record_count", data_type="integer", description="Number of source records."),
        SchemaColumn(name="total_amount", data_type="decimal", description="Aggregated business metric."),
    )
    tables = [
        ProjectTableSchema(table_name=f"raw_{entity}", grain="One record per ingested source row.", columns=raw_columns),
        ProjectTableSchema(table_name=f"clean_{entity}", grain="One validated record per business entity event.", columns=clean_columns),
    ]
    if level >= 2:
        tables.append(ProjectTableSchema(table_name=f"mart_{entity}_daily", grain="One row per date and reporting dimension.", columns=mart_columns))
    if level >= 4:
        tables.append(
            ProjectTableSchema(
                table_name="dq_audit_log",
                grain="One row per data quality check execution.",
                columns=(
                    SchemaColumn(name="check_name", data_type="string", description="Quality rule name."),
                    SchemaColumn(name="status", data_type="string", description="Pass, warn, or fail."),
                    SchemaColumn(name="failed_count", data_type="integer", description="Number of invalid records."),
                ),
            )
        )
    return tuple(tables)


def _data_flow_for_level(level: int) -> tuple[str, ...]:
    steps = [
        "Land source data without mutation.",
        "Validate required fields and data types.",
        "Transform raw records into clean, typed tables.",
        "Publish analytics-ready outputs with reproducible SQL queries.",
    ]
    if level >= 2:
        steps.append("Schedule the pipeline and preserve run metadata for each load.")
    if level >= 3:
        steps.append("Partition and optimize datasets for incremental processing.")
    if level >= 4:
        steps.append("Promote changes through dev and prod environments with rollback notes.")
    return tuple(steps)


def _etl_steps_for_level(level: int) -> tuple[str, ...]:
    steps = [
        "Extract source files or API payloads into a raw zone.",
        "Profile columns and reject records with missing identifiers.",
        "Standardize timestamps, statuses, and numeric fields.",
        "Load curated tables and validate row counts.",
    ]
    if level >= 2:
        steps.append("Build dimensional marts with tests for uniqueness and relationships.")
    if level >= 3:
        steps.append("Run incremental Spark jobs with partition pruning and late-arriving-data handling.")
    if level >= 4:
        steps.append("Support backfills, replay, schema evolution, and automated deployment checks.")
    return tuple(steps)


def _quality_checks_for_level(level: int) -> tuple[str, ...]:
    checks = [
        "Required primary identifiers are not null.",
        "Duplicate business keys are quarantined.",
        "Record counts match expected source totals.",
        "Dates and numeric values stay within accepted ranges.",
    ]
    if level >= 2:
        checks.append("Foreign-key relationships and accepted values are tested.")
    if level >= 3:
        checks.append("Freshness and volume anomaly checks run by partition.")
    if level >= 4:
        checks.append("Failing critical checks block deployment or downstream publication.")
    return tuple(checks)


def _error_handling_for_level(level: int) -> tuple[str, ...]:
    handling = [
        "Write invalid records to a quarantine table with failure reasons.",
        "Use idempotent loads so retries do not duplicate data.",
        "Log pipeline run status, row counts, and exception messages.",
    ]
    if level >= 2:
        handling.append("Retry transient API or database failures with bounded attempts.")
    if level >= 4:
        handling.append("Define runbook steps for failed DAGs, partial loads, and rollback decisions.")
    return tuple(handling)


def _orchestration_for_level(level: int) -> str:
    if level == 1:
        return "A Makefile or Python CLI command runs extract, transform, quality checks, and load in order."
    if level == 2:
        return "Airflow DAG with extract, stage, transform, test, and publish tasks plus retry policies."
    if level == 3:
        return "Airflow orchestrates Spark submit tasks with partition parameters and backfill support."
    return "Airflow coordinates ingestion, Spark processing, quality gates, deployment checks, backfills, and alerting."


def _monitoring_for_level(level: int) -> tuple[str, ...]:
    monitoring = [
        "Track run duration, row counts, rejected records, and freshness.",
        "Write a daily summary table for successful and failed runs.",
    ]
    if level >= 2:
        monitoring.append("Add Airflow task alerts for retries and failures.")
    if level >= 4:
        monitoring.append("Expose service-level indicators for freshness, completeness, and failed critical checks.")
    return tuple(monitoring)


def _deployment_for_level(level: int, cloud: str) -> tuple[str, ...]:
    deployment = {
        1: ("Document local setup with requirements.txt and seed data.", "Run tests before pushing to GitHub."),
        2: ("Package the pipeline with Docker Compose.", "Include environment variables and local Postgres setup."),
        3: ("Run Spark jobs locally or in a managed notebook environment.", "Store outputs in partitioned Parquet paths."),
        4: (f"Deploy storage, compute, and secrets in {cloud}.", "Use CI/CD checks for tests, linting, and DAG validation."),
    }
    return deployment[level]


def _github_structure_for_level(level: int) -> tuple[str, ...]:
    structure = [
        "README.md",
        "requirements.txt",
        "src/ingestion/",
        "src/transforms/",
        "tests/",
        "data/sample/",
    ]
    if level >= 2:
        structure.extend(["dags/", "dbt_project.yml", "models/staging/", "models/marts/", "docker-compose.yml"])
    if level >= 3:
        structure.extend(["spark/jobs/", "configs/", "notebooks/"])
    if level >= 4:
        structure.extend(["infra/", ".github/workflows/", "docs/runbook.md", "docs/data_contracts.md"])
    return tuple(structure)


def _resume_bullets(target_role: str, level: int, entity: str, technologies: tuple[str, ...]) -> tuple[str, ...]:
    tech_summary = ", ".join(technologies[:5])
    bullets = [
        f"Built a Level {level} data engineering project for {target_role} workflows using {tech_summary}.",
        f"Designed raw, clean, and reporting schemas for {entity} data with automated quality checks.",
    ]
    if level >= 3:
        bullets.append("Optimized partitioned data processing and documented scalability tradeoffs for larger workloads.")
    if level >= 4:
        bullets.append("Implemented production-style orchestration, monitoring, deployment, error handling, and runbook practices.")
    return tuple(bullets)


def _interview_explanation(target_role: str, level: int, entity: str, phase: int, gaps: tuple[str, ...]) -> str:
    gap_sentence = " It intentionally practices " + ", ".join(gaps[:3]) + "." if gaps else ""
    return (
        f"Explain this as a Level {level} {target_role} portfolio project: source {entity} data lands raw, "
        "is validated, transformed into reliable analytical tables, tested, orchestrated, and monitored. "
        f"Tie the design to roadmap phase {phase}, then discuss tradeoffs around reliability, scale, and recovery."
        f"{gap_sentence}"
    )


def _fit_reason(level: int, recommendation_input: ProjectRecommendationInput, technologies: tuple[str, ...]) -> str:
    start_level = LEVEL_BY_NAME[recommendation_input.learner_skill_level]
    if level < start_level:
        position = "reinforces earlier fundamentals"
    elif level == start_level:
        position = "is the best starting point for your current level"
    else:
        position = "is a stretch project for later roadmap phases"
    practiced = ", ".join(recommendation_input.missing_skills[:3]) or "portfolio depth"
    return (
        f"This {position} for phase {recommendation_input.current_roadmap_phase}; it uses "
        f"{', '.join(technologies[:4])} while practicing {practiced}."
    )


def _cloud(preferred_cloud: str | None) -> str:
    if preferred_cloud and preferred_cloud.strip() and preferred_cloud.strip().lower() != "no preference":
        return preferred_cloud.strip()
    return "AWS"


def _score_criterion(criterion: str, review_input: ProjectReviewInput) -> ProjectReviewScore:
    scoring_rules = {
        "Architecture": (
            _score_text(review_input.architecture, ("raw", "stage", "warehouse", "lake", "orchestration", "quality")),
            "Architecture describes source, storage, transformation, and serving layers.",
            "Clarify ingestion, storage, transformation, serving, and dependency boundaries.",
        ),
        "Scalability": (
            _score_text(review_input.architecture + " " + review_input.data_flow, ("partition", "incremental", "parallel", "spark", "backfill")),
            "Design includes scale-aware processing choices.",
            "Add incremental processing, partitioning, and backfill strategy.",
        ),
        "Performance": (
            _score_items(review_input.performance_controls, ("partition", "index", "cache", "cluster", "pruning")),
            "Performance controls are explicit.",
            "Document indexes, partitions, file sizes, query patterns, or Spark optimization choices.",
        ),
        "Data Quality": (
            _score_items(review_input.data_quality_checks, ("not null", "unique", "freshness", "range", "relationship", "volume")),
            "Data quality checks cover critical failure modes.",
            "Add tests for nulls, uniqueness, freshness, referential integrity, and volume anomalies.",
        ),
        "Security": (
            _score_items(review_input.security_controls, ("secret", "iam", "encrypt", "mask", "least privilege")),
            "Security controls are included.",
            "Add secret management, least-privilege access, encryption, and sensitive-data handling.",
        ),
        "Cost": (
            _score_items(review_input.cost_controls, ("budget", "lifecycle", "autoscale", "right-size", "storage")),
            "Cost controls are included.",
            "Add budget limits, right-sized compute, storage lifecycle rules, and cost-aware scheduling.",
        ),
        "Monitoring": (
            _score_text(review_input.monitoring, ("alert", "freshness", "row count", "duration", "failure", "metric")),
            "Monitoring covers run health and data health.",
            "Track freshness, row counts, duration, failures, and alert destinations.",
        ),
        "Error handling": (
            _score_text(review_input.error_handling, ("retry", "retries", "quarantine", "idempotent", "dead letter", "rollback")),
            "Error handling explains retries and bad-record isolation.",
            "Add idempotent retries, quarantine/dead-letter handling, and rollback or replay steps.",
        ),
        "Maintainability": (
            _score_items(review_input.repository_structure, ("readme", "tests", "src", "config", "docs", "dags")),
            "Repository structure supports maintenance.",
            "Add README setup, tests, configs, docs, and clear source-code boundaries.",
        ),
    }
    base_score, strength, improvement = scoring_rules[criterion]
    level_adjusted_score = _level_adjusted_score(base_score, review_input.level)
    return ProjectReviewScore(
        criterion=criterion,
        score=level_adjusted_score,
        strengths=(strength,) if level_adjusted_score >= 7 else (),
        improvements=() if level_adjusted_score >= 7.5 else (improvement,),
    )


def _score_text(text: str, signals: tuple[str, ...]) -> float:
    normalized = text.lower()
    matched = sum(1 for signal in signals if signal in normalized)
    if not text.strip():
        return 2.0
    return round(min(10.0, 4.0 + matched * 1.2), 1)


def _score_items(items: tuple[str, ...], signals: tuple[str, ...]) -> float:
    if not items:
        return 2.0
    normalized_items = " ".join(items).lower()
    matched = sum(1 for signal in signals if signal in normalized_items)
    coverage = min(len(items), 5) * 0.7
    return round(min(10.0, 3.5 + coverage + matched * 0.9), 1)


def _level_adjusted_score(score: float, level: int) -> float:
    if level >= 4:
        return round(max(score - 0.8, 0), 1)
    if level == 1:
        return round(min(score + 0.5, 10), 1)
    return score


def _readiness(score: float) -> str:
    if score >= 8:
        return "portfolio_ready"
    if score >= 6:
        return "needs_targeted_improvements"
    return "needs_major_revision"


def _resume_readiness(score: float) -> str:
    if score >= 8:
        return "Ready to describe on a resume with metrics and tradeoffs."
    if score >= 6:
        return "Add the priority improvements before making it a primary resume project."
    return "Treat this as a learning draft until core architecture, quality, and operations gaps are closed."


def _interview_guidance(review_input: ProjectReviewInput, scores: tuple[ProjectReviewScore, ...]) -> str:
    weakest = min(scores, key=lambda item: item.score)
    return (
        f"When explaining {review_input.project_name}, lead with the business problem, walk through the data flow, "
        f"then be ready to defend {weakest.criterion.lower()} because it is currently the weakest area."
    )
