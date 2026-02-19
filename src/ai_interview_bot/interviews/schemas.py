"""Pydantic request/response schemas for interview endpoints."""

from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class InterviewTypeEnum(str, Enum):
    BEHAVIORAL = "behavioral"
    TECHNICAL = "technical"
    MIXED = "mixed"
    CODING_ONLY = "coding_only"


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class InterviewStartRequest(BaseModel):
    """Payload for starting a new interview session."""

    role: str = Field(..., description="Target job role, e.g. 'Machine Learning Engineer'.")
    level: str = Field("mid", description="Seniority level, e.g. 'junior', 'mid', 'senior'.")
    questions: int = Field(3, ge=1, le=10, description="Total number of questions to ask.")
    candidate_profile: str = Field(
        "",
        description="Optional candidate profile/resume summary to contextualise the interview.",
    )
    interview_type: InterviewTypeEnum = Field(
        InterviewTypeEnum.BEHAVIORAL,
        description="Type of interview: behavioral, technical, mixed, or coding_only.",
    )


class AnswerRequest(BaseModel):
    """Payload for submitting an answer to the current interview question."""

    answer: str = Field(..., min_length=1, description="Candidate response to the current question.")
    time_taken: Optional[int] = Field(
        None, ge=0, description="Time taken in seconds (optional, calculated automatically)."
    )
    time_expired: Optional[bool] = Field(None, description="Whether the time limit was exceeded.")


# ---------------------------------------------------------------------------
# Shared response models
# ---------------------------------------------------------------------------

class EvaluationModel(BaseModel):
    """API representation of the evaluation breakdown."""

    score: int
    overall_score: Optional[int] = None
    technical_depth: Optional[int] = None
    communication: Optional[int] = None
    problem_solving: Optional[int] = None
    reasoning: str = ""
    strengths: List[str] = Field(default_factory=list)
    improvements: List[str] = Field(default_factory=list)
    follow_up: Optional[str] = None


class QARecordModel(BaseModel):
    """API representation of a QA history entry."""

    question: str
    answer: str
    evaluation: Optional[EvaluationModel] = None
    follow_ups: Optional[List["QARecordModel"]] = None


class InterviewStepResponse(BaseModel):
    """Generic response returned after any state transition."""

    session_id: str
    status: str
    question: Optional[str] = None
    question_index: Optional[int] = None
    question_limit: Optional[int] = None
    evaluation: Optional[EvaluationModel] = None
    feedback: Optional[str] = None
    qa_history: List[QARecordModel] = Field(default_factory=list)
    prompt: Optional[str] = None
    question_difficulty: Optional[str] = None
    question_time_limit: Optional[int] = None
    time_elapsed: Optional[int] = None
    time_remaining: Optional[int] = None
    total_time_elapsed: Optional[int] = None
    time_expired: Optional[bool] = None
    is_follow_up: Optional[bool] = None
    follow_up_count: Optional[int] = None


# ---------------------------------------------------------------------------
# Interview history & report schemas (Sprint 3)
# ---------------------------------------------------------------------------

class InterviewSessionListItem(BaseModel):
    """Summary of a past interview session for listing."""

    session_id: str
    role: str
    level: str
    interview_type: str
    total_questions: int
    status: str
    overall_score: Optional[int] = None
    started_at: str
    completed_at: Optional[str] = None
    total_time_seconds: Optional[int] = None


class InterviewQuestionDetail(BaseModel):
    """Detailed view of a single question within a report."""

    question_id: str
    sequence_number: int
    question_text: str
    question_type: Optional[str] = None
    difficulty: Optional[str] = None
    answer_text: Optional[str] = None
    score: Optional[int] = None
    evaluation: Optional[EvaluationModel] = None
    time_taken_seconds: Optional[int] = None
    time_expired: bool = False
    follow_ups: List["InterviewQuestionDetail"] = Field(default_factory=list)


class InterviewReportResponse(BaseModel):
    """Full structured report for a completed interview session."""

    session_id: str
    role: str
    level: str
    interview_type: str
    total_questions: int
    status: str
    started_at: str
    completed_at: Optional[str] = None
    total_time_seconds: Optional[int] = None

    overall_score: Optional[int] = None
    technical_depth_score: Optional[int] = None
    communication_score: Optional[int] = None
    problem_solving_score: Optional[int] = None
    summary_text: Optional[str] = None
    strengths: List[str] = Field(default_factory=list)
    improvements: List[str] = Field(default_factory=list)

    questions: List[InterviewQuestionDetail] = Field(default_factory=list)
    qa_history: List[QARecordModel] = Field(default_factory=list)
