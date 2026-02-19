"""Interview HTTP endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..hr.cv_parser import CVParser
from ..hr.service import LinkService
from .schemas import AnswerRequest, InterviewStartRequest, InterviewStepResponse
from .service import (
    drive_session,
    manager,
    store_interview_results,
)

router = APIRouter(tags=["interviews"])


@router.post("/interviews", response_model=InterviewStepResponse, status_code=status.HTTP_201_CREATED)
async def start_interview(payload: InterviewStartRequest) -> InterviewStepResponse:
    session = await manager.create_session(payload)
    session_id = session.config.thread_id or ""
    return await drive_session(session_id, session)


@router.post("/interviews/{session_id}/answer", response_model=InterviewStepResponse)
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

    if response.status == "completed" and session.interview_link_id:
        await store_interview_results(session, session_id, db)

    return response


@router.get("/interviews/{session_id}", response_model=InterviewStepResponse)
async def get_session_state(
    session_id: str,
    db: AsyncSession = Depends(get_db),
) -> InterviewStepResponse:
    session = await manager.get_session(session_id)
    response = await drive_session(session_id, session)

    if response.status == "completed" and session.interview_link_id:
        await store_interview_results(session, session_id, db)

    return response


@router.delete("/interviews/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def end_session(session_id: str) -> None:
    await manager.remove_session(session_id)


# ---------------------------------------------------------------------------
# Candidate link access
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

    session = await manager.create_session(payload)
    session.interview_link_id = interview_link.id
    session_id = session.config.thread_id or ""

    response = await drive_session(session_id, session)

    if response.status == "completed":
        await store_interview_results(session, session_id, db)

    return response
