"""Pydantic request/response schemas for HR endpoints."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field

from ..interviews.schemas import QARecordModel


class CreateInterviewRequest(BaseModel):
    """Request model for creating interview from CV."""

    hr_email: EmailStr = Field(..., description="HR email address.")
    candidate_email: EmailStr = Field(..., description="Candidate email address.")
    candidate_name: Optional[str] = Field(None, description="Candidate name (optional).")
    role: str = Field(..., description="Target job role.")
    level: str = Field("mid", description="Seniority level: 'junior', 'mid', 'senior'.")
    questions: int = Field(3, ge=1, le=10, description="Number of questions.")
    expires_in_days: int = Field(7, ge=1, le=90, description="Link expiry in days.")


class InterviewLinkResponse(BaseModel):
    """Response model for interview link creation."""

    interview_id: str
    token: str
    interview_link: str
    candidate_email: str
    candidate_name: Optional[str]
    role: str
    level: str
    expires_at: str
    status: str


class InterviewListItem(BaseModel):
    """Model for listing interviews."""

    interview_id: str
    candidate_email: str
    candidate_name: Optional[str]
    role: str
    level: str
    status: str
    created_at: str
    expires_at: str
    used_at: Optional[str]
    has_results: bool = False


class InterviewResultResponse(BaseModel):
    """Response model for interview results."""

    interview_id: str
    candidate_email: str
    candidate_name: Optional[str]
    role: str
    level: str
    final_feedback: Optional[str]
    overall_score: Optional[str]
    qa_history: List[QARecordModel]
    total_time_elapsed: Optional[int]
    completed_at: str
