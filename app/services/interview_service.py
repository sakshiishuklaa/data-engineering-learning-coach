"""Module 11 data engineering interview agent."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import InterviewAttempt
from app.schemas.interview import (
    InterviewAnswerResult,
    InterviewEvaluation,
    InterviewQuestion,
    InterviewQuestionRequest,
    InterviewReport,
    InterviewAttemptSummary,
)
from app.services.learner_memory_service import get_learner

FOLLOW_UP_PREFIX = "followup"


QUESTION_BANK: tuple[InterviewQuestion, ...] = (
    InterviewQuestion(
        question_id="sql-junior-joins-aggregation",
        mode="SQL",
        difficulty="Junior",
        question="How would you find each customer whose total order value is greater than 1000?",
        expected_concepts=("JOIN orders to customers", "GROUP BY customer", "SUM aggregation", "HAVING filter"),
    ),
    InterviewQuestion(
        question_id="sql-mid-level-deduplication",
        mode="SQL",
        difficulty="Mid-level",
        question="A table has duplicate events with the same event_id. How would you keep the latest row per event?",
        expected_concepts=("ROW_NUMBER window function", "PARTITION BY event_id", "ORDER BY timestamp descending", "filter rank to one"),
    ),
    InterviewQuestion(
        question_id="sql-senior-performance",
        mode="SQL",
        difficulty="Senior",
        question="An analytics query over a large fact table is slow. How would you diagnose and improve it?",
        expected_concepts=("query execution plan", "partition pruning", "join strategy", "aggregation reduction", "indexing or clustering"),
    ),
    InterviewQuestion(
        question_id="python-junior-file-processing",
        mode="Python",
        difficulty="Junior",
        question="How would you read a CSV file, validate required columns, and write only valid rows?",
        expected_concepts=("CSV or dataframe reading", "required column validation", "row filtering", "write clean output"),
    ),
    InterviewQuestion(
        question_id="python-mid-level-large-files",
        mode="Python",
        difficulty="Mid-level",
        question="How would you process a file that is too large to fit in memory?",
        expected_concepts=("streaming or iteration", "chunked processing", "memory efficiency", "incremental output"),
    ),
    InterviewQuestion(
        question_id="python-senior-pipeline-library",
        mode="Python",
        difficulty="Senior",
        question="How would you design a reusable Python validation library for multiple pipeline stages?",
        expected_concepts=("separation of concerns", "schema or rule abstraction", "testability", "clear error reporting", "configuration"),
    ),
    InterviewQuestion(
        question_id="spark-junior-partitions",
        mode="Spark",
        difficulty="Junior",
        question="Why does Spark split data into partitions, and what can go wrong if partitioning is poor?",
        expected_concepts=("parallel processing", "distributed executors", "too many small partitions", "skewed partitions"),
    ),
    InterviewQuestion(
        question_id="spark-mid-level-shuffle",
        mode="Spark",
        difficulty="Mid-level",
        question="What causes a Spark shuffle, and how would you reduce shuffle cost?",
        expected_concepts=("wide transformations", "data movement across executors", "join or groupBy examples", "broadcast join or repartitioning"),
    ),
    InterviewQuestion(
        question_id="spark-senior-skew",
        mode="Spark",
        difficulty="Senior",
        question="A Spark join has a few tasks running much longer than the rest. How would you investigate and fix it?",
        expected_concepts=("detect data skew", "Spark UI or physical plan", "salting", "broadcast join", "partition tuning"),
    ),
    InterviewQuestion(
        question_id="aws-junior-s3-iam",
        mode="AWS",
        difficulty="Junior",
        question="How would you let a data pipeline write files to S3 securely?",
        expected_concepts=("IAM role", "least privilege", "bucket or prefix permissions", "avoid hardcoded secrets"),
    ),
    InterviewQuestion(
        question_id="aws-mid-level-lakehouse",
        mode="AWS",
        difficulty="Mid-level",
        question="Design an AWS batch pipeline from raw files to analytics-ready tables.",
        expected_concepts=("S3 raw and curated zones", "Glue or Spark processing", "orchestration", "data quality checks", "warehouse or Athena serving"),
    ),
    InterviewQuestion(
        question_id="aws-senior-platform-reliability",
        mode="AWS",
        difficulty="Senior",
        question="How would you make an AWS data platform reliable and cost-aware?",
        expected_concepts=("fault tolerance", "monitoring and alerts", "least privilege security", "cost controls", "backfill strategy"),
    ),
    InterviewQuestion(
        question_id="azure-junior-adls-identity",
        mode="Azure",
        difficulty="Junior",
        question="How would a pipeline securely write data to Azure Data Lake Storage?",
        expected_concepts=("managed identity", "least privilege", "container or path permissions", "avoid hardcoded secrets"),
    ),
    InterviewQuestion(
        question_id="azure-mid-level-batch-pipeline",
        mode="Azure",
        difficulty="Mid-level",
        question="Design an Azure batch pipeline from source files to analytics-ready data.",
        expected_concepts=("ADLS raw and curated zones", "Data Factory or Synapse orchestration", "Databricks or Spark processing", "data quality checks", "serving layer"),
    ),
    InterviewQuestion(
        question_id="azure-senior-platform-reliability",
        mode="Azure",
        difficulty="Senior",
        question="How would you operate a reliable and secure Azure data platform?",
        expected_concepts=("fault tolerance", "monitoring and alerts", "managed identity security", "cost controls", "backfill strategy"),
    ),
    InterviewQuestion(
        question_id="etl-junior-core-flow",
        mode="ETL",
        difficulty="Junior",
        question="Explain extract, transform, and load using an order pipeline example.",
        expected_concepts=("source extraction", "data transformation", "target loading", "basic validation"),
    ),
    InterviewQuestion(
        question_id="etl-mid-level-idempotency",
        mode="ETL",
        difficulty="Mid-level",
        question="How would you make an ETL job safe to rerun after a failure?",
        expected_concepts=("idempotency", "checkpointing or state", "deduplication", "transactional load or upsert", "retry behavior"),
    ),
    InterviewQuestion(
        question_id="etl-senior-late-data",
        mode="ETL",
        difficulty="Senior",
        question="Design an incremental ETL pipeline that handles late-arriving data.",
        expected_concepts=("watermarks", "incremental extraction", "lookback window", "merge or upsert", "backfill strategy"),
    ),
    InterviewQuestion(
        question_id="data-warehousing-junior-facts-dimensions",
        mode="Data Warehousing",
        difficulty="Junior",
        question="What are fact and dimension tables, and why do they matter?",
        expected_concepts=("fact table measurements", "dimension table context", "grain", "analytics queries"),
    ),
    InterviewQuestion(
        question_id="data-warehousing-mid-level-layers",
        mode="Data Warehousing",
        difficulty="Mid-level",
        question="Explain staging, warehouse, and mart layers in a data warehouse.",
        expected_concepts=("staging raw source data", "curated warehouse model", "business-facing marts", "data quality tests", "lineage"),
    ),
    InterviewQuestion(
        question_id="data-warehousing-senior-scd",
        mode="Data Warehousing",
        difficulty="Senior",
        question="How would you model customer attributes that change over time?",
        expected_concepts=("slowly changing dimensions", "type 2 history", "effective dates", "surrogate keys", "business requirements"),
    ),
    InterviewQuestion(
        question_id="system-design-junior-batch-platform",
        mode="System Design",
        difficulty="Junior",
        question="Design a simple batch data platform for daily sales reporting.",
        expected_concepts=("ingestion", "storage", "processing", "serving layer", "monitoring"),
    ),
    InterviewQuestion(
        question_id="system-design-mid-level-events-to-metrics",
        mode="System Design",
        difficulty="Mid-level",
        question="Design a pipeline that ingests product events and publishes daily metrics for analysts.",
        expected_concepts=("event ingestion", "batch or streaming processing", "data quality checks", "warehouse or mart output", "orchestration"),
    ),
    InterviewQuestion(
        question_id="system-design-senior-realtime-analytics",
        mode="System Design",
        difficulty="Senior",
        question="Design a data platform that supports both real-time alerts and historical analytics.",
        expected_concepts=("stream processing", "batch historical storage", "serving paths", "latency tradeoffs", "reliability and replay"),
    ),
    InterviewQuestion(
        question_id="scenario-based-junior-broken-file",
        mode="Scenario-based",
        difficulty="Junior",
        question="A daily CSV arrives with missing columns. What do you do before downstream reports run?",
        expected_concepts=("validate schema", "stop or quarantine bad data", "alert stakeholders", "preserve previous good output"),
    ),
    InterviewQuestion(
        question_id="scenario-based-mid-level-duplicate-load",
        mode="Scenario-based",
        difficulty="Mid-level",
        question="A job accidentally loaded yesterday's data twice. How would you fix the data and prevent recurrence?",
        expected_concepts=("identify duplicate scope", "rollback or delete duplicates", "idempotent load design", "deduplication key", "tests or monitoring"),
    ),
    InterviewQuestion(
        question_id="scenario-based-senior-executive-metric",
        mode="Scenario-based",
        difficulty="Senior",
        question="An executive dashboard metric changed sharply overnight. How would you investigate?",
        expected_concepts=("check pipeline freshness", "compare source and target counts", "review recent code or schema changes", "segment the metric", "communicate impact"),
    ),
)

CONCEPT_ALIASES = {
    "adls raw and curated zones": ("adls", "raw", "curated"),
    "aggregation reduction": ("pre aggregate", "pre-aggregate", "reduce aggregation", "aggregation"),
    "analytics queries": ("analytics", "query", "report"),
    "avoid hardcoded secrets": ("avoid secrets", "no hardcoded", "secrets manager", "environment secrets", "managed secret"),
    "backfill strategy": ("backfill", "replay", "reprocess"),
    "basic validation": ("validation", "validate", "quality check"),
    "batch historical storage": ("historical", "batch", "lake", "warehouse"),
    "broadcast join": ("broadcast", "map side join"),
    "broadcast join or repartitioning": ("broadcast", "repartition", "partition"),
    "bucket or prefix permissions": ("bucket policy", "prefix", "s3 permission", "path permission"),
    "business-facing marts": ("mart", "data mart", "business layer"),
    "checkpointing or state": ("checkpoint", "state", "bookmark", "offset"),
    "clear error reporting": ("error", "exception", "failure reason", "report"),
    "configuration": ("config", "yaml", "settings", "parameter"),
    "container or path permissions": ("container", "path", "acl", "rbac"),
    "cost controls": ("budget", "cost", "right size", "lifecycle", "spot"),
    "csv or dataframe reading": ("csv", "pandas", "dataframe", "read_csv"),
    "curated warehouse model": ("curated", "warehouse", "dimensional"),
    "data movement across executors": ("data movement", "network", "executor", "shuffle"),
    "data quality checks": ("quality", "dq", "validation", "test"),
    "data transformation": ("transform", "clean", "standardize", "derive"),
    "databricks or spark processing": ("databricks", "spark"),
    "data factory or synapse orchestration": ("data factory", "adf", "synapse", "orchestration"),
    "deduplication": ("dedupe", "deduplicate", "duplicate"),
    "deduplication key": ("dedupe key", "deduplication key", "business key", "unique key"),
    "detect data skew": ("skew", "hot key", "long task"),
    "distributed executors": ("executor", "distributed", "cluster"),
    "effective dates": ("effective date", "valid from", "valid_to", "start date", "end date"),
    "event ingestion": ("event", "kafka", "kinesis", "event hub", "ingest"),
    "fact table measurements": ("fact", "measure", "metric"),
    "fault tolerance": ("fault tolerant", "retry", "recover", "availability", "resilient"),
    "filter rank to one": ("rank = 1", "row_number = 1", "rn = 1", "latest row"),
    "grain": ("grain", "one row per"),
    "group by customer": ("group by", "customer"),
    "glue or spark processing": ("glue", "spark", "emr"),
    "having filter": ("having",),
    "iam role": ("iam", "role"),
    "identify duplicate scope": ("scope", "which rows", "duplicate"),
    "idempotency": ("idempotent", "safe to rerun", "same result"),
    "indexing or clustering": ("index", "cluster", "sort key", "clustering"),
    "ingestion": ("ingest", "extract", "source"),
    "incremental extraction": ("incremental", "changed records", "cdc"),
    "incremental output": ("write incrementally", "append", "stream output", "batch output"),
    "join orders to customers": ("join", "orders", "customers"),
    "join or groupby examples": ("join", "groupby", "group by"),
    "join strategy": ("join", "broadcast", "shuffle", "join order"),
    "latency tradeoffs": ("latency", "tradeoff", "sla"),
    "least privilege": ("least privilege", "minimal permission", "only required"),
    "least privilege security": ("least privilege", "iam", "security"),
    "lineage": ("lineage", "trace"),
    "lookback window": ("lookback", "late window", "overlap"),
    "managed identity": ("managed identity", "service principal", "workload identity"),
    "managed identity security": ("managed identity", "service principal", "rbac"),
    "memory efficiency": ("memory", "ram", "not load entire"),
    "merge or upsert": ("merge", "upsert"),
    "monitoring": ("monitor", "alert", "metric"),
    "monitoring and alerts": ("monitor", "alert", "cloudwatch", "azure monitor"),
    "order by timestamp descending": ("order by", "timestamp", "desc", "latest"),
    "orchestration": ("orchestration", "airflow", "schedule", "dag", "data factory"),
    "parallel processing": ("parallel", "concurrent"),
    "partition by event_id": ("partition by", "event_id"),
    "partition pruning": ("partition", "pruning"),
    "partition tuning": ("partition", "repartition", "coalesce"),
    "preserve previous good output": ("previous good", "last good", "do not overwrite", "preserve"),
    "query execution plan": ("execution plan", "explain", "query plan"),
    "reliability and replay": ("replay", "reliable", "recover", "dead letter"),
    "retry behavior": ("retry", "retries"),
    "review recent code or schema changes": ("code change", "schema change", "deployment", "recent change"),
    "rollback or delete duplicates": ("rollback", "delete", "remove duplicate"),
    "row filtering": ("filter", "valid rows", "where"),
    "row_number window function": ("row_number", "window"),
    "s3 raw and curated zones": ("s3", "raw", "curated"),
    "schema or rule abstraction": ("schema", "rule", "abstraction"),
    "segment the metric": ("segment", "break down", "dimension"),
    "separation of concerns": ("separation", "separate", "modular"),
    "serving layer": ("serve", "serving", "warehouse", "dashboard", "bi"),
    "serving paths": ("serving", "api", "warehouse", "dashboard"),
    "slowly changing dimensions": ("scd", "slowly changing"),
    "source extraction": ("extract", "source"),
    "spark ui or physical plan": ("spark ui", "physical plan", "explain"),
    "staging raw source data": ("staging", "raw"),
    "storage": ("storage", "lake", "warehouse", "s3", "adls"),
    "stop or quarantine bad data": ("quarantine", "stop", "fail", "block"),
    "stream processing": ("stream", "real time", "kafka", "kinesis", "event hub"),
    "streaming or iteration": ("stream", "iterate", "generator", "line by line"),
    "sum aggregation": ("sum", "aggregate", "total"),
    "surrogate keys": ("surrogate", "warehouse key"),
    "target loading": ("load", "target", "warehouse"),
    "testability": ("test", "pytest", "unit test"),
    "tests or monitoring": ("test", "monitor", "alert"),
    "too many small partitions": ("small partition", "too many partitions", "small files"),
    "transactional load or upsert": ("transaction", "upsert", "merge"),
    "type 2 history": ("type 2", "history", "version"),
    "validate schema": ("schema", "column", "validate"),
    "warehouse or athena serving": ("athena", "warehouse", "redshift", "serve"),
    "warehouse or mart output": ("warehouse", "mart", "output"),
    "watermarks": ("watermark", "high water mark"),
    "wide transformations": ("wide transformation", "shuffle", "groupby", "join"),
    "write clean output": ("write", "output", "clean"),
}


def list_interview_questions(
    mode: str | None = None,
    difficulty: str | None = None,
) -> tuple[InterviewQuestion, ...]:
    """Return interview questions, optionally filtered by mode and difficulty."""
    return tuple(
        question
        for question in QUESTION_BANK
        if (mode is None or question.mode == mode) and (difficulty is None or question.difficulty == difficulty)
    )


def get_interview_question(request: InterviewQuestionRequest) -> InterviewQuestion:
    """Return a targeted question for the requested mode and difficulty."""
    if request.previous_missing_concepts:
        missing = request.previous_missing_concepts[0]
        return InterviewQuestion(
            question_id=f"{FOLLOW_UP_PREFIX}-{_slug(request.mode)}-{_slug(request.difficulty)}-{_slug(missing)}",
            mode=request.mode,
            difficulty=request.difficulty,
            question=f"Follow-up on your previous answer: how would you handle {missing} in this {request.mode} interview scenario?",
            expected_concepts=(missing, _supporting_concept(request.mode)),
        )

    questions = list_interview_questions(mode=request.mode, difficulty=request.difficulty)
    if not questions:
        raise ValueError(f"No interview question exists for {request.mode} at {request.difficulty} difficulty.")
    return questions[0]


def submit_interview_answer(
    session: Session,
    *,
    learner_id: int,
    question_id: str,
    learner_answer: str,
) -> InterviewAnswerResult:
    """Evaluate and persist one interview answer."""
    if get_learner(session, learner_id) is None:
        raise ValueError(f"Learner {learner_id} does not exist")
    question = get_question_by_id(question_id)
    if question is None:
        raise ValueError(f"Interview question {question_id} does not exist")
    evaluation = evaluate_interview_answer(question, learner_answer)

    attempt = InterviewAttempt(
        learner_id=learner_id,
        mode=question.mode,
        difficulty=question.difficulty,
        question_id=question.question_id,
        question=question.question,
        learner_answer=learner_answer,
        score=evaluation.score,
        evaluation=evaluation.evaluation,
        expected_concepts=list(question.expected_concepts),
        missing_concepts=list(evaluation.missing_concepts),
        improved_interview_answer=evaluation.improved_interview_answer,
        follow_up_question=evaluation.follow_up_question,
    )
    session.add(attempt)
    session.commit()
    session.refresh(attempt)
    return _answer_result(attempt)


def evaluate_interview_answer(question: InterviewQuestion, learner_answer: str) -> InterviewEvaluation:
    """Evaluate an interview answer against the question's expected concepts."""
    cleaned_answer = " ".join(learner_answer.strip().split())
    if not cleaned_answer:
        raise ValueError("Learner answer is required.")

    covered = tuple(concept for concept in question.expected_concepts if _concept_is_present(concept, cleaned_answer))
    missing = tuple(concept for concept in question.expected_concepts if concept not in covered)
    score = _score_answer(question.expected_concepts, covered, cleaned_answer)
    evaluation = _evaluation_text(question, covered, missing, score)
    improved_answer = _improved_answer(question)
    follow_up = _follow_up_question(question, missing, cleaned_answer)
    return InterviewEvaluation(
        score=score,
        evaluation=evaluation,
        missing_concepts=missing,
        improved_interview_answer=improved_answer,
        follow_up_question=follow_up,
    )


def get_interview_report(session: Session, learner_id: int) -> InterviewReport:
    """Create an interview performance report from stored attempts."""
    if get_learner(session, learner_id) is None:
        raise ValueError(f"Learner {learner_id} does not exist")
    attempts = list(
        session.scalars(
            select(InterviewAttempt)
            .where(InterviewAttempt.learner_id == learner_id)
            .order_by(InterviewAttempt.created_at.desc(), InterviewAttempt.id.desc())
        )
    )
    if not attempts:
        return InterviewReport(
            learner_id=learner_id,
            strengths=(),
            weaknesses=("No interview attempts are stored yet.",),
            topics_to_revise=(),
            average_score=0,
            recommended_next_topics=("Start with a Junior SQL or Python interview question to establish a baseline.",),
            attempts=(),
        )

    average = round(sum(attempt.score for attempt in attempts) / len(attempts), 1)
    by_mode: dict[str, list[InterviewAttempt]] = defaultdict(list)
    for attempt in attempts:
        by_mode[attempt.mode].append(attempt)

    strengths = tuple(
        f"{mode}: average {round(sum(item.score for item in items) / len(items), 1)}/10"
        for mode, items in sorted(by_mode.items())
        if sum(item.score for item in items) / len(items) >= 7.5
    )
    weaknesses = tuple(
        f"{mode}: average {round(sum(item.score for item in items) / len(items), 1)}/10"
        for mode, items in sorted(by_mode.items())
        if sum(item.score for item in items) / len(items) < 7
    )

    missing_counter = Counter(
        concept
        for attempt in attempts
        for concept in attempt.missing_concepts
    )
    topics_to_revise = tuple(concept for concept, _ in missing_counter.most_common(7))
    recommended = _recommended_next_topics(attempts, topics_to_revise)
    summaries = tuple(_attempt_summary(attempt) for attempt in attempts)

    return InterviewReport(
        learner_id=learner_id,
        strengths=strengths or ("Answers are developing; no consistently strong mode yet.",),
        weaknesses=weaknesses or ("No major weak interview mode is currently visible.",),
        topics_to_revise=topics_to_revise,
        average_score=average,
        recommended_next_topics=recommended,
        attempts=summaries,
    )


def get_question_by_id(question_id: str) -> InterviewQuestion | None:
    """Find a static interview question by id."""
    return next((question for question in QUESTION_BANK if question.question_id == question_id), None)


def _answer_result(attempt: InterviewAttempt) -> InterviewAnswerResult:
    question = InterviewQuestion(
        question_id=attempt.question_id,
        mode=attempt.mode,  # type: ignore[arg-type]
        difficulty=attempt.difficulty,  # type: ignore[arg-type]
        question=attempt.question,
        expected_concepts=tuple(attempt.expected_concepts),
    )
    evaluation = InterviewEvaluation(
        score=attempt.score,
        evaluation=attempt.evaluation,
        missing_concepts=tuple(attempt.missing_concepts),
        improved_interview_answer=attempt.improved_interview_answer,
        follow_up_question=attempt.follow_up_question,
    )
    return InterviewAnswerResult(
        attempt_id=attempt.id,
        learner_id=attempt.learner_id,
        question=question,
        learner_answer=attempt.learner_answer,
        evaluation=evaluation,
        created_at=attempt.created_at,
    )


def _attempt_summary(attempt: InterviewAttempt) -> InterviewAttemptSummary:
    return InterviewAttemptSummary(
        attempt_id=attempt.id,
        mode=attempt.mode,  # type: ignore[arg-type]
        difficulty=attempt.difficulty,  # type: ignore[arg-type]
        question=attempt.question,
        score=attempt.score,
        missing_concepts=tuple(attempt.missing_concepts),
        created_at=attempt.created_at,
    )


def _concept_is_present(concept: str, answer: str) -> bool:
    answer_lower = answer.lower()
    aliases = CONCEPT_ALIASES.get(concept.lower(), ())
    if any(alias in answer_lower for alias in aliases):
        return True
    words = _keywords(concept)
    if not words:
        return False
    return all(word in answer_lower for word in words)


def _score_answer(expected_concepts: tuple[str, ...], covered: tuple[str, ...], answer: str) -> float:
    coverage = len(covered) / len(expected_concepts)
    detail_bonus = 1.0 if len(answer.split()) >= 35 else 0.5 if len(answer.split()) >= 18 else 0.0
    structure_bonus = 0.5 if any(marker in answer.lower() for marker in ("first", "then", "finally", "because")) else 0.0
    score = coverage * 8.5 + detail_bonus + structure_bonus
    return round(min(score, 10), 1)


def _evaluation_text(
    question: InterviewQuestion,
    covered: tuple[str, ...],
    missing: tuple[str, ...],
    score: float,
) -> str:
    if score >= 8:
        level = "Strong"
    elif score >= 6:
        level = "Partially complete"
    else:
        level = "Needs work"
    covered_text = ", ".join(covered) if covered else "no key rubric concepts clearly"
    missing_text = ", ".join(missing) if missing else "no major expected concepts"
    return (
        f"{level} {question.mode} answer. You covered {covered_text}. "
        f"The answer is missing {missing_text}."
    )


def _improved_answer(question: InterviewQuestion) -> str:
    concepts = "; ".join(question.expected_concepts)
    return (
        f"I would answer by framing the problem, then covering these points: {concepts}. "
        f"For {question.mode}, I would connect the design choice to reliability, correctness, and operational tradeoffs, "
        "then finish with how I would validate the result in production."
    )


def _follow_up_question(question: InterviewQuestion, missing: tuple[str, ...], answer: str) -> str:
    if missing:
        concept = missing[0]
        return f"You mentioned your approach; now go deeper on {concept}. How would you apply it in this exact situation?"
    if "cost" in answer.lower():
        return f"Good cost awareness. What reliability tradeoff would you watch for in this {question.mode} design?"
    if "test" in answer.lower() or "quality" in answer.lower():
        return f"Good validation focus. What failure mode would your {question.mode} solution still need to handle?"
    return f"Strong answer. What edge case or scaling limit would you discuss next for this {question.mode} problem?"


def _recommended_next_topics(attempts: list[InterviewAttempt], topics_to_revise: tuple[str, ...]) -> tuple[str, ...]:
    recommendations = list(topics_to_revise[:5])
    weakest_attempt = min(attempts, key=lambda attempt: attempt.score)
    mode_topic = f"{weakest_attempt.mode} {weakest_attempt.difficulty} interview practice"
    if mode_topic not in recommendations:
        recommendations.append(mode_topic)
    return tuple(recommendations[:5])


def _supporting_concept(mode: str) -> str:
    support_by_mode = {
        "SQL": "query correctness",
        "Python": "testability",
        "Spark": "performance tradeoffs",
        "AWS": "least privilege",
        "Azure": "managed identity security",
        "ETL": "idempotency",
        "Data Warehousing": "grain",
        "System Design": "reliability and replay",
        "Scenario-based": "communicate impact",
    }
    return support_by_mode[mode]


def _keywords(text: str) -> tuple[str, ...]:
    ignored = {"a", "an", "and", "or", "the", "to", "of", "by", "with", "for", "per", "into"}
    return tuple(word for word in _tokens(text) if len(word) > 2 and word not in ignored)


def _tokens(text: str) -> Iterable[str]:
    current = []
    for character in text.lower():
        if character.isalnum() or character == "_":
            current.append(character)
        elif current:
            yield "".join(current)
            current = []
    if current:
        yield "".join(current)


def _slug(value: str) -> str:
    return "-".join(_tokens(value))
