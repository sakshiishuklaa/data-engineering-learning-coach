"""Deterministic local resource recommendations for Module 12.2."""

from __future__ import annotations

from app.schemas.resource import ResourceResponse

_RESOURCE_TYPE_PRIORITY = {
    "official documentation": 0,
    "learning resource": 1,
    "practice": 2,
}
_LEVELS = ("beginner", "intermediate", "advanced")


def _resource(
    resource_id: int,
    title: str,
    url: str,
    resource_type: str,
    topic: str,
    difficulty: str,
    source: str,
    description: str,
) -> ResourceResponse:
    return ResourceResponse(
        id=resource_id,
        title=title,
        url=url,
        resource_type=resource_type,
        topic=topic,
        difficulty=difficulty,
        source=source,
        description=description,
    )


RESOURCE_SEED_DATA: tuple[ResourceResponse, ...] = (
    _resource(1, "Python 3 Documentation", "https://docs.python.org/3/", "Official documentation", "Python", "Beginner", "Python", "The official Python language and standard-library documentation."),
    _resource(2, "Python for Everybody", "https://www.py4e.com/", "Learning resource", "Python", "Beginner", "PY4E", "A structured introduction to Python programming."),
    _resource(3, "Exercism Python Track", "https://exercism.org/tracks/python", "Practice", "Python", "Intermediate", "Exercism", "Practice Python through short, testable exercises."),
    _resource(4, "PostgreSQL SQL Documentation", "https://www.postgresql.org/docs/current/tutorial-sql.html", "Official documentation", "SQL", "Beginner", "PostgreSQL", "An official SQL tutorial covering queries, joins, and aggregation."),
    _resource(5, "SQLBolt", "https://sqlbolt.com/", "Learning resource", "SQL", "Beginner", "SQLBolt", "Interactive lessons for learning core SQL concepts."),
    _resource(6, "LeetCode Database Problems", "https://leetcode.com/problemset/database/", "Practice", "SQL", "Advanced", "LeetCode", "SQL practice problems for applying querying and data modeling skills."),
    _resource(7, "Apache Spark Documentation", "https://spark.apache.org/docs/latest/", "Official documentation", "Spark", "Intermediate", "Apache Spark", "The official Apache Spark documentation and programming guides."),
    _resource(8, "Learning Spark", "https://pages.databricks.com/rs/094-YMS-629/images/LearningSpark2.0.pdf", "Learning resource", "Spark", "Intermediate", "Databricks", "A practical guide to Spark concepts and DataFrame-based processing."),
    _resource(9, "Spark Exercises", "https://github.com/databricks-academy/data-engineering-with-databricks", "Practice", "Spark", "Advanced", "Databricks Academy", "Hands-on exercises for building Spark data-engineering workflows."),
    _resource(10, "Apache Airflow Documentation", "https://airflow.apache.org/docs/", "Official documentation", "Airflow", "Intermediate", "Apache Airflow", "The official documentation for authoring and operating Airflow workflows."),
    _resource(11, "Astronomer Airflow Guides", "https://www.astronomer.io/docs/learn/", "Learning resource", "Airflow", "Intermediate", "Astronomer", "Practical guides for learning Airflow concepts and patterns."),
    _resource(12, "Airflow Example DAGs", "https://github.com/apache/airflow/tree/main/airflow/example_dags", "Practice", "Airflow", "Advanced", "Apache Airflow", "Runnable example DAGs for practicing orchestration patterns."),
)


def _normalize(value: str) -> str:
    return " ".join(value.strip().lower().split())


def _level_distance(resource_level: str, learner_level: str) -> int:
    return abs(_LEVELS.index(_normalize(resource_level)) - _LEVELS.index(learner_level))


def recommend_resources(topic: str, learner_level: str) -> list[ResourceResponse]:
    """Return up to three local resources for a topic and learner level.

    Results are ordered by source quality first—official documentation, then
    high-quality learning resources, then practice resources—and by difficulty
    fit within each category.
    """
    normalized_level = _normalize(learner_level)
    if normalized_level not in _LEVELS:
        raise ValueError(f"Unsupported learner level: {learner_level}")

    normalized_topic = _normalize(topic)
    matches = [resource for resource in RESOURCE_SEED_DATA if _normalize(resource.topic) == normalized_topic]
    matches.sort(
        key=lambda resource: (
            _RESOURCE_TYPE_PRIORITY[resource.resource_type.lower()],
            _level_distance(resource.difficulty, normalized_level),
            resource.id,
        )
    )
    return matches[:3]
