"""Interview HTTP endpoints — /api/v1/interviews."""

from __future__ import annotations

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.dependencies import get_current_user, get_optional_user
from ..core.database import get_db
from ..hr.cv_parser import CVParser
from ..hr.service import LinkService
from ..models.user import User
from .schemas import (
    AnswerRequest,
    InterviewReportResponse,
    InterviewSessionListItem,
    InterviewStartRequest,
    InterviewStepResponse,
)
from .service import (
    drive_session,
    get_interview_report,
    list_user_interviews,
    manager,
    persist_session_completion,
    store_interview_results,
)

router = APIRouter(prefix="/api/v1", tags=["interviews"])


# ---------------------------------------------------------------------------
# Core interview flow
# ---------------------------------------------------------------------------

@router.post(
    "/interviews",
    response_model=InterviewStepResponse,
    status_code=status.HTTP_201_CREATED,
)
async def start_interview(
    payload: InterviewStartRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
) -> InterviewStepResponse:
    user_id = current_user.id if current_user else None
    session = await manager.create_session(payload, db, user_id=user_id)
    session_id = session.config.thread_id or ""
    return await drive_session(session_id, session)


@router.post(
    "/interviews/{session_id}/answer",
    response_model=InterviewStepResponse,
)
async def submit_answer(
    session_id: str,
    payload: AnswerRequest,
    db: AsyncSession = Depends(get_db),
) -> InterviewStepResponse:
    session = await manager.get_session(session_id)
    async with session.lock:
        if session.finished:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Interview already completed.",
            )

        update_data = {"answer": payload.answer.strip()}

        if payload.time_expired is not None:
            update_data["time_expired"] = payload.time_expired

        session.app.update_state(session.graph_config, update_data)

    response = await drive_session(session_id, session)

    if response.status == "completed":
        await persist_session_completion(session, session_id, db)
        if session.interview_link_id:
            await store_interview_results(session, session_id, db)

    return response


@router.get(
    "/interviews/{session_id}/state",
    response_model=InterviewStepResponse,
)
async def get_session_state(
    session_id: str,
    db: AsyncSession = Depends(get_db),
) -> InterviewStepResponse:
    session = await manager.get_session(session_id)
    response = await drive_session(session_id, session)

    if response.status == "completed":
        await persist_session_completion(session, session_id, db)
        if session.interview_link_id:
            await store_interview_results(session, session_id, db)

    return response


@router.delete(
    "/interviews/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def end_session(session_id: str) -> None:
    await manager.remove_session(session_id)


# ---------------------------------------------------------------------------
# Candidate link access (public, no auth required)
# ---------------------------------------------------------------------------

@router.get("/interview/{token}", response_model=InterviewStepResponse)
async def access_interview_by_token(
    token: str,
    db: AsyncSession = Depends(get_db),
) -> InterviewStepResponse:
    """Access interview via a token link."""
    is_valid, interview_link, error_msg = await LinkService.validate_and_activate_link(db, token)

    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg or "Invalid or expired interview link.",
        )

    cv_profile = ""
    if interview_link.cv_extracted_data:
        cv_parser = CVParser()
        cv_profile = cv_parser._create_profile_summary(
            interview_link.cv_extracted_data,
            interview_link.cv_extracted_data.get("raw_text", ""),
        )

    payload = InterviewStartRequest(
        role=interview_link.role,
        level=interview_link.level,
        questions=interview_link.question_limit,
        candidate_profile=cv_profile,
    )

    session = await manager.create_session(
        payload,
        db,
        interview_link_id=interview_link.id,
    )
    session_id = session.config.thread_id or ""

    response = await drive_session(session_id, session)

    if response.status == "completed":
        await persist_session_completion(session, session_id, db)
        await store_interview_results(session, session_id, db)

    return response


# ---------------------------------------------------------------------------
# Interview history & report (auth required)
# ---------------------------------------------------------------------------

@router.get(
    "/interviews",
    response_model=List[InterviewSessionListItem],
)
async def list_interviews(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[InterviewSessionListItem]:
    """List the current user's past interview sessions."""
    return await list_user_interviews(db, current_user.id)


@router.get(
    "/interviews/{session_id}/report",
    response_model=InterviewReportResponse,
)
async def interview_report(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InterviewReportResponse:
    """Get a structured feedback report for a completed interview."""
    try:
        sid = UUID(session_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid session ID format.",
        )
    return await get_interview_report(db, sid, user_id=current_user.id)
