"""HTTP endpoints exposed by the backend."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database.session import get_db
from app.schemas.health import HealthResponse
from app.schemas.interview import (
    InterviewAnswerResult,
    InterviewAnswerSubmission,
    InterviewQuestion,
    InterviewQuestionRequest,
    InterviewReport,
)
from app.schemas.project import (
    ProjectRecommendationInput,
    ProjectRecommendationResult,
    ProjectReviewInput,
    ProjectReviewResult,
)
from app.services.interview_service import get_interview_question, get_interview_report, submit_interview_answer
from app.services.project_service import recommend_projects, review_project

router = APIRouter()


@router.get("/health", response_model=HealthResponse, tags=["health"])
def health_check() -> HealthResponse:
    """Report that the API process is available."""
    settings = get_settings()
    return HealthResponse(status="ok", environment=settings.environment)


@router.post("/projects/recommendations", response_model=ProjectRecommendationResult, tags=["projects"])
def project_recommendations(recommendation_input: ProjectRecommendationInput) -> ProjectRecommendationResult:
    """Return personalized data engineering project recommendations."""
    return recommend_projects(recommendation_input)


@router.post("/projects/review", response_model=ProjectReviewResult, tags=["projects"])
def project_review(review_input: ProjectReviewInput) -> ProjectReviewResult:
    """Review a learner project against the Module 10 rubric."""
    return review_project(review_input)


@router.post("/interviews/questions", response_model=InterviewQuestion, tags=["interviews"])
def interview_question(question_request: InterviewQuestionRequest) -> InterviewQuestion:
    """Return a targeted data engineering interview question."""
    try:
        return get_interview_question(question_request)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/interviews/answers", response_model=InterviewAnswerResult, tags=["interviews"])
def interview_answer(
    submission: InterviewAnswerSubmission,
    session: Session = Depends(get_db),
) -> InterviewAnswerResult:
    """Evaluate and store a learner interview answer."""
    try:
        return submit_interview_answer(
            session,
            learner_id=submission.learner_id,
            question_id=submission.question_id,
            learner_answer=submission.learner_answer,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.get("/interviews/report/{learner_id}", response_model=InterviewReport, tags=["interviews"])
def interview_report(learner_id: int, session: Session = Depends(get_db)) -> InterviewReport:
    """Return a persisted interview performance report."""
    try:
        return get_interview_report(session, learner_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
