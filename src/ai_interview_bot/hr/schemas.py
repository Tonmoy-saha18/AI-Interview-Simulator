"""Pydantic request/response schemas for HR endpoints."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field

from ..interviews.schemas import QARecordModel


class CreateInterviewRequest(BaseModel):
    """Request model for creating interview from CV."""

    candidate_email: EmailStr = Field(..., description="Candidate email address.")
    candidate_name: Optional[str] = Field(None, description="Candidate name (optional).")
    role: str = Field(..., description="Target job role.")
    level: str = Field("mid", description="Seniority level: 'junior', 'mid', 'senior'.")
    questions: int = Field(3, ge=1, le=10, description="Number of questions.")
    expires_in_days: int = Field(7, ge=1, le=90, description="Link expiry in days.")
    interview_type: str = Field("behavioral", description="Type of interview.")
    custom_instructions: Optional[str] = Field(None, description="Custom instructions for the AI interviewer.")
    notes: Optional[str] = Field(None, description="HR-only notes about this interview.")
    tags: Optional[List[str]] = Field(None, description="Tags for filtering/categorisation.")


class PatchInterviewRequest(BaseModel):
    """Request model for updating an existing interview link."""

    expires_in_days: Optional[int] = Field(None, ge=1, le=90, description="Extend expiry.")
    notes: Optional[str] = Field(None, description="Update notes.")
    tags: Optional[List[str]] = Field(None, description="Update tags.")
    custom_instructions: Optional[str] = Field(None, description="Update custom instructions.")
    revoke: Optional[bool] = Field(None, description="Set to true to revoke the link.")


class InterviewLinkResponse(BaseModel):
    """Response model for interview link creation."""

    interview_id: str
    token: str
    interview_link: str
    candidate_email: str
    candidate_name: Optional[str] = None
    role: str
    level: str
    expires_at: str
    status: str
    interview_type: Optional[str] = None
    notes: Optional[str] = None
    tags: Optional[List[str]] = None
    created_at: Optional[str] = None


class InterviewListItem(BaseModel):
    """Model for listing interviews."""

    interview_id: str
    candidate_email: str
    candidate_name: Optional[str] = None
    role: str
    level: str
    status: str
    interview_type: Optional[str] = None
    created_at: str
    expires_at: str
    used_at: Optional[str] = None
    has_results: bool = False
    notes: Optional[str] = None
    tags: Optional[List[str]] = None


class InterviewResultResponse(BaseModel):
    """Response model for interview results."""

    interview_id: str
    candidate_email: str
    candidate_name: Optional[str] = None
    role: str
    level: str
    final_feedback: Optional[str] = None
    overall_score: Optional[str] = None
    qa_history: List[QARecordModel]
    total_time_elapsed: Optional[int] = None
    completed_at: str
