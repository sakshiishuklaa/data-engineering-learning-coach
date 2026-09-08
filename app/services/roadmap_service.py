"""LLM-powered personalized roadmap generation with validation gates."""

from __future__ import annotations

import re
from typing import Any, Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Learner, LearnerSkill
from app.schemas.assessment import AssessmentResult
from app.schemas.roadmap import (
    LearningPriority,
    PersonalizedRoadmap,
    RoadmapGenerationInput,
    RoadmapGenerationResult,
)
from app.schemas.skill_gap import LearnerSkillInput, SkillGapAnalysisInput
from app.services.skill_gap_service import SKILL_CATEGORIES, analyze_skill_gaps, canonical_skill_name
from app.services.assessment_service import level_for_score


class RoadmapLLMClient(Protocol):
    """Boundary for a structured-output LLM adapter."""

    def generate_roadmap(self, *, prompt: str, response_model: type[PersonalizedRoadmap]) -> Any:
        """Return data that can be parsed as ``PersonalizedRoadmap``."""


PRIORITY_BY_GAP_PRIORITY: dict[str, LearningPriority] = {
    "Critical": "MUST_LEARN",
    "High": "MUST_LEARN",
    "Medium": "GOOD_TO_LEARN",
    "Low": "OPTIONAL",
}


def _safe_roadmap_generation_error(error: Exception) -> str:
    """Preserve useful diagnostics while removing credentials and secret values."""
    message = str(error)
    message = re.sub(
        r"(?i)\b[A-Z][A-Z0-9_]*(?:KEY|TOKEN|SECRET|PASSWORD|CREDENTIALS?)\b\s*=\s*[^\s,;]+",
        "[REDACTED_SENSITIVE_SETTING]",
        message,
    )
    message = re.sub(r"(?i)\bBearer\s+[^\s,;]+", "Bearer [REDACTED]", message)
    message = re.sub(
        r"(?i)\b(api[_ -]?key|authorization|token|secret|credential|password)\b\s*[:=]\s*[^\s,;]+",
        r"\1=[REDACTED]",
        message,
    )
    message = re.sub(
        r"\b(?:AIza[0-9A-Za-z_-]{20,}|sk-[0-9A-Za-z_-]{16,}|eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+)\b",
        "[REDACTED_TOKEN]",
        message,
    )
    message = message.replace("\x00", "")[:300]
    return f"{type(error).__name__}: {message or 'No diagnostic details available.'}"


def generate_personalized_roadmap(
    generation_input: RoadmapGenerationInput,
    llm_client: RoadmapLLMClient,
) -> RoadmapGenerationResult:
    """Generate a roadmap through a structured LLM boundary and validate it."""
    prompt = build_roadmap_prompt(generation_input)
    try:
        raw_roadmap = llm_client.generate_roadmap(prompt=prompt, response_model=PersonalizedRoadmap)
        roadmap = raw_roadmap if isinstance(raw_roadmap, PersonalizedRoadmap) else PersonalizedRoadmap.model_validate(raw_roadmap)
    except Exception as error:
        return RoadmapGenerationResult(success=False, error=_safe_roadmap_generation_error(error))

    validation_errors = validate_roadmap(roadmap, generation_input)
    if validation_errors:
        return RoadmapGenerationResult(
            success=False,
            error="Generated roadmap failed validation.",
            validation_errors=tuple(validation_errors),
        )
    return RoadmapGenerationResult(success=True, roadmap=roadmap)


def generate_personalized_roadmap_for_learner(
    session: Session,
    learner_id: int,
    llm_client: RoadmapLLMClient,
) -> RoadmapGenerationResult:
    """Build roadmap inputs from persisted learner data and generate a roadmap."""
    learner = session.scalar(
        select(Learner)
        .where(Learner.id == learner_id)
        .options(
            selectinload(Learner.onboarding_profile),
            selectinload(Learner.skills).selectinload(LearnerSkill.skill),
        )
    )
    if learner is None:
        raise ValueError(f"Learner {learner_id} does not exist")
    if learner.onboarding_profile is None:
        raise ValueError(f"Learner {learner_id} has no onboarding profile")

    profile = learner.onboarding_profile
    skill_inputs: list[LearnerSkillInput] = []
    for learner_skill in learner.skills:
        skill_name = canonical_skill_name(learner_skill.skill.name)
        if skill_name not in SKILL_CATEGORIES:
            continue
        skill_inputs.append(LearnerSkillInput(skill=skill_name, current_score=learner_skill.proficiency_score))

    skill_gap_analysis = analyze_skill_gaps(
        SkillGapAnalysisInput(
            learner_profile={
                "current_role": profile.current_role,
                "experience_years": profile.experience_years,
                "target_company_type": profile.target_company_type,
                "preferred_cloud": profile.preferred_cloud,
                "learning_preference": profile.learning_preference,
            },
            learner_skills=skill_inputs,
            target_role=profile.target_role,
            target_timeline=profile.target_timeline,
            study_hours_per_week=profile.study_hours_per_week,
        )
    )
    skill_assessment = tuple(
        AssessmentResult(
            skill=node.skill,
            current_score=node.current_score,
            target_score=node.target_score,
            gap=node.gap,
            level=level_for_score(node.current_score),
            priority=node.priority,
            confidence="Low",
            evidence_sources=("Self report",),
        )
        for node in skill_gap_analysis.nodes
        if node.current_score >= 1
        and any(skill.skill == node.skill for skill in skill_inputs)
    )
    generation_input = RoadmapGenerationInput(
        learner_profile={
            "current_role": profile.current_role,
            "experience_years": profile.experience_years,
            "target_company_type": profile.target_company_type,
            "preferred_cloud": profile.preferred_cloud,
            "learning_preference": profile.learning_preference,
        },
        skill_assessment=skill_assessment,
        skill_gap_analysis=skill_gap_analysis,
        target_role=profile.target_role,
        target_timeline=profile.target_timeline,
        weekly_study_hours=profile.study_hours_per_week,
    )
    return generate_personalized_roadmap(generation_input, llm_client)


def build_roadmap_prompt(generation_input: RoadmapGenerationInput) -> str:
    """Create a constrained prompt for a structured-output LLM adapter."""
    skill_gaps = [
        {
            "skill": node.skill,
            "gap": node.gap,
            "priority": PRIORITY_BY_GAP_PRIORITY[node.priority],
            "prerequisites": node.prerequisites,
            "estimated_hours": node.estimated_hours,
            "ready_to_learn": node.ready_to_learn,
        }
        for node in generation_input.skill_gap_analysis.nodes
        if node.gap > 0
    ]
    known_skills = [
        node.skill
        for node in generation_input.skill_gap_analysis.nodes
        if node.gap == 0 or node.current_score >= node.target_score
    ]
    allowed_topics = [item["skill"] for item in skill_gaps]
    must_learn_topics = [item["skill"] for item in skill_gaps if item["priority"] == "MUST_LEARN"]
    good_to_learn_topics = [item["skill"] for item in skill_gaps if item["priority"] == "GOOD_TO_LEARN"]
    return (
        "Generate a personalized data-engineering learning roadmap as structured JSON only. "
        "Use the supplied response_model/Pydantic schema. Do not include prose outside the JSON. "
        "Rules: do not teach everything simultaneously; respect prerequisites; skip known topics; "
        "prioritize MUST_LEARN skills; keep the plan realistic for the target timeline and weekly hours; "
        "include hands-on exercises, progressively harder mini projects, interview questions, and completion criteria; "
        "clearly mark each phase priority as MUST_LEARN, GOOD_TO_LEARN, or OPTIONAL. "
        "Preserve each learner-specific skill priority exactly as supplied in the skill gaps. "
        "MUST_LEARN means only the skills the application identifies as MUST_LEARN for this learner. "
        "GOOD_TO_LEARN skills are useful but are not required MUST_LEARN skills; never promote them to MUST_LEARN "
        "merely because they are generally important for a Data Engineer. "
        "Use only the canonical topic names listed in the skill gaps; do not invent alternative names such as "
        "Advanced SQL, PySpark DataFrames, or Data Transformations. "
        "Include every listed MUST_LEARN skill somewhere in the roadmap. "
        "For each topic, use its listed prerequisites exactly and place each prerequisite in an earlier phase "
        "or treat it as already-known; never teach a topic before its prerequisites.\n"
        f"Target role: {generation_input.target_role}\n"
        f"Target timeline: {generation_input.target_timeline} "
        f"({generation_input.skill_gap_analysis.timeline_weeks} weeks)\n"
        f"Weekly study hours: {generation_input.weekly_study_hours}\n"
        f"Learner profile: {generation_input.learner_profile.model_dump_json()}\n"
        f"Known skills to skip as topics: {known_skills}\n"
        f"Canonical allowed topic names: {allowed_topics}\n"
        f"MUST_LEARN skills that must all be covered: {must_learn_topics}\n"
        f"GOOD_TO_LEARN skills to keep in their supplied priority: {good_to_learn_topics}\n"
        f"Skill gaps to plan: {skill_gaps}\n"
        f"Roadmap JSON schema: {PersonalizedRoadmap.model_json_schema()}"
    )


def validate_roadmap(roadmap: PersonalizedRoadmap, generation_input: RoadmapGenerationInput) -> list[str]:
    """Check generated roadmap against dependency, priority, and capacity rules."""
    errors: list[str] = []
    gap_nodes = {node.skill: node for node in generation_input.skill_gap_analysis.nodes}
    priority_by_skill = {skill: PRIORITY_BY_GAP_PRIORITY[node.priority] for skill, node in gap_nodes.items() if node.gap > 0}
    allowed_topics = set(priority_by_skill)
    known_topics = {skill for skill, node in gap_nodes.items() if node.gap == 0 or node.current_score >= node.target_score}
    planned_topics: list[str] = []
    completed_topics = set(known_topics)

    if roadmap.timeline_weeks != generation_input.skill_gap_analysis.timeline_weeks:
        errors.append("Roadmap timeline_weeks must match the skill gap analysis timeline.")
    if roadmap.study_hours_per_week != generation_input.weekly_study_hours:
        errors.append("Roadmap study_hours_per_week must match the requested weekly study hours.")
    if roadmap.total_estimated_weeks > generation_input.skill_gap_analysis.timeline_weeks:
        errors.append("Roadmap exceeds the requested target timeline.")

    for phase in roadmap.phases:
        if len(phase.topics) > 4:
            errors.append(f"Phase {phase.phase} teaches too many topics simultaneously.")
        for topic in phase.topics:
            if topic in known_topics:
                errors.append(f"Phase {phase.phase} includes already-known topic: {topic}.")
            if topic not in allowed_topics:
                errors.append(f"Phase {phase.phase} includes unsupported topic: {topic}.")
                continue
            planned_topics.append(topic)
            if phase.priority != priority_by_skill[topic]:
                errors.append(f"Phase {phase.phase} marks {topic} as {phase.priority}, expected {priority_by_skill[topic]}.")
            missing_prerequisites = [
                prerequisite
                for prerequisite in gap_nodes[topic].prerequisites
                if prerequisite not in completed_topics
            ]
            if missing_prerequisites:
                errors.append(
                    f"Phase {phase.phase} teaches {topic} before prerequisites: {', '.join(missing_prerequisites)}."
                )
        completed_topics.update(topic for topic in phase.topics if topic in allowed_topics)

    planned_topic_set = set(planned_topics)
    missing_must_learn = {
        skill for skill, priority in priority_by_skill.items() if priority == "MUST_LEARN" and skill not in planned_topic_set
    }
    if missing_must_learn:
        errors.append(f"Roadmap omits MUST_LEARN skills: {', '.join(sorted(missing_must_learn))}.")

    must_learn_phase_numbers = [
        phase.phase for phase in roadmap.phases for topic in phase.topics if priority_by_skill.get(topic) == "MUST_LEARN"
    ]
    optional_phase_numbers = [
        phase.phase for phase in roadmap.phases for topic in phase.topics if priority_by_skill.get(topic) == "OPTIONAL"
    ]
    if must_learn_phase_numbers and optional_phase_numbers and min(optional_phase_numbers) < max(must_learn_phase_numbers):
        errors.append("OPTIONAL topics appear before all MUST_LEARN topics are scheduled.")

    return errors
