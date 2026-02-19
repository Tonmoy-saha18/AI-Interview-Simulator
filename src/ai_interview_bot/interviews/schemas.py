"""Pydantic request/response schemas for interview endpoints."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class InterviewStartRequest(BaseModel):
    """Payload for starting a new interview session."""

    role: str = Field(..., description="Target job role, e.g. 'Machine Learning Engineer'.")
    level: str = Field("mid", description="Seniority level, e.g. 'junior', 'mid', 'senior'.")
    questions: int = Field(3, ge=1, le=10, description="Total number of questions to ask.")
    candidate_profile: str = Field(
        "",
        description="Optional candidate profile/resume summary to contextualise the interview.",
    )


class AnswerRequest(BaseModel):
    """Payload for submitting an answer to the current interview question."""

    answer: str = Field(..., min_length=1, description="Candidate response to the current question.")
    time_taken: Optional[int] = Field(
        None, ge=0, description="Time taken in seconds (optional, calculated automatically)."
    )
    time_expired: Optional[bool] = Field(None, description="Whether the time limit was exceeded.")


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
