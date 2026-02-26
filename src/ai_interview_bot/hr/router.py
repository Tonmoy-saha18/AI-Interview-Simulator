"""HR HTTP endpoints — org-scoped interview link CRUD with JWT auth."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import List, Optional

import aiofiles
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import uuid4

from ..auth.dependencies import require_role
from ..core.config import get_settings
from ..core.database import get_db
from ..models import InterviewLink, InterviewResult
from ..models.user import User, UserRole
from ..interviews.service import serialise_history
from .cv_parser import CVParser
from .email_service import EmailService
from .schemas import (
    InterviewLinkResponse,
    InterviewListItem,
    InterviewResultResponse,
    PatchInterviewRequest,
)
from .service import LinkService

router = APIRouter(prefix="/api/v1/hr", tags=["hr"])

UPLOADS_DIR = Path("uploads/cvs")
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

_hr_dependency = require_role([UserRole.HR, UserRole.ORG_ADMIN, UserRole.PLATFORM_ADMIN])


def _link_to_response(link: InterviewLink, frontend_url: str) -> InterviewLinkResponse:
    interview_url = f"{frontend_url}/interview/{link.token}"
    return InterviewLinkResponse(
        interview_id=str(link.id),
        token=link.token,
        interview_link=interview_url,
        candidate_email=link.candidate_email,
        candidate_name=link.candidate_name,
        role=link.role,
        level=link.level,
        expires_at=link.expires_at.isoformat(),
        status=link.status.value,
        interview_type=link.interview_type,
        notes=link.notes,
        tags=link.tags,
        created_at=link.created_at.isoformat() if link.created_at else None,
    )


@router.post(
    "/interviews",
    response_model=InterviewLinkResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_interview(
    candidate_email: str = Form(...),
    candidate_name: Optional[str] = Form(None),
    role: str = Form(...),
    level: str = Form("mid"),
    questions: int = Form(3),
    expires_in_days: int = Form(7),
    interview_type: str = Form("behavioral"),
    custom_instructions: Optional[str] = Form(None),
    notes: Optional[str] = Form(None),
    cv_file: UploadFile = File(...),
    current_user: User = Depends(_hr_dependency),
    db: AsyncSession = Depends(get_db),
) -> InterviewLinkResponse:
    settings = get_settings()
    max_cv_size_bytes = settings.MAX_CV_FILE_SIZE_MB * 1024 * 1024

    file_extension = Path(cv_file.filename or "").suffix.lower()
    if file_extension not in [".pdf", ".docx", ".doc"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file type. Only PDF and DOCX files are supported.",
        )

    file_content = await cv_file.read()
    if len(file_content) > max_cv_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File size exceeds maximum allowed size of {settings.MAX_CV_FILE_SIZE_MB}MB.",
        )

    file_id = str(uuid4())
    cv_filename = f"{file_id}{file_extension}"
    cv_file_path = UPLOADS_DIR / cv_filename

    async with aiofiles.open(cv_file_path, "wb") as f:
        await f.write(file_content)

    try:
        cv_parser = CVParser()
        cv_data = cv_parser.parse_cv(str(cv_file_path), file_extension)

        interview_link = await LinkService.create_interview_link(
            db,
            hr_email=current_user.email,
            candidate_email=candidate_email,
            candidate_name=candidate_name or cv_data["structured_data"].get("name"),
            role=role,
            level=level,
            question_limit=questions,
            expires_in_days=expires_in_days,
            cv_file_path=str(cv_file_path),
            cv_extracted_data=cv_data["structured_data"],
            organization_id=current_user.organization_id,
            created_by_id=current_user.id,
            interview_type=interview_type,
            custom_instructions=custom_instructions,
            notes=notes,
        )

        await db.commit()

        frontend_url = settings.FRONTEND_URL
        interview_url = f"{frontend_url}/interview/{interview_link.token}"

        email_service = EmailService()
        try:
            email_service.send_interview_invitation(
                candidate_email=candidate_email,
                candidate_name=candidate_name or cv_data["structured_data"].get("name"),
                interview_link=interview_url,
                role=role,
                expires_at=interview_link.expires_at,
            )
        except Exception as e:
            print(f"Failed to send email: {e!s}")

        return _link_to_response(interview_link, frontend_url)
    except HTTPException:
        raise
    except Exception as e:
        if cv_file_path.exists():
            cv_file_path.unlink()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing CV: {e!s}",
        )


@router.get("/interviews", response_model=List[InterviewListItem])
async def list_interviews(
    status_filter: Optional[str] = None,
    current_user: User = Depends(_hr_dependency),
    db: AsyncSession = Depends(get_db),
) -> List[InterviewListItem]:
    if current_user.organization_id:
        links = await LinkService.get_links_by_organization(
            db, current_user.organization_id, status_filter=status_filter
        )
    else:
        links = await LinkService.get_links_by_hr_email(db, current_user.email)

    results = []
    for link in links:
        result_query = await db.execute(
            select(InterviewResult).where(InterviewResult.interview_link_id == link.id)
        )
        has_results = result_query.scalar_one_or_none() is not None

        results.append(
            InterviewListItem(
                interview_id=str(link.id),
                candidate_email=link.candidate_email,
                candidate_name=link.candidate_name,
                role=link.role,
                level=link.level,
                status=link.status.value,
                interview_type=link.interview_type,
                created_at=link.created_at.isoformat(),
                expires_at=link.expires_at.isoformat(),
                used_at=link.used_at.isoformat() if link.used_at else None,
                has_results=has_results,
                notes=link.notes,
                tags=link.tags,
            )
        )
    return results


@router.get("/interviews/{interview_id}", response_model=InterviewLinkResponse)
async def get_interview_details(
    interview_id: str,
    current_user: User = Depends(_hr_dependency),
    db: AsyncSession = Depends(get_db),
) -> InterviewLinkResponse:
    try:
        link_uuid = uuid.UUID(interview_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid interview ID format.",
        )

    link = await LinkService.get_link_by_id(db, link_uuid)
    if not link:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interview not found.")

    if current_user.organization_id and link.organization_id != current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

    return _link_to_response(link, get_settings().FRONTEND_URL)


@router.get("/interviews/{interview_id}/results", response_model=InterviewResultResponse)
async def get_interview_results(
    interview_id: str,
    current_user: User = Depends(_hr_dependency),
    db: AsyncSession = Depends(get_db),
) -> InterviewResultResponse:
    try:
        link_uuid = uuid.UUID(interview_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid interview ID format.",
        )

    link = await LinkService.get_link_by_id(db, link_uuid)
    if not link:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interview not found.")

    if current_user.organization_id and link.organization_id != current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

    result_query = await db.execute(
        select(InterviewResult).where(InterviewResult.interview_link_id == link_uuid)
    )
    result = result_query.scalar_one_or_none()
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Interview results not found. The interview may not be completed yet.",
        )

    qa_history = serialise_history(result.qa_history or [])

    return InterviewResultResponse(
        interview_id=str(link.id),
        candidate_email=link.candidate_email,
        candidate_name=link.candidate_name,
        role=link.role,
        level=link.level,
        final_feedback=result.final_feedback,
        overall_score=result.overall_score,
        qa_history=qa_history,
        total_time_elapsed=result.total_time_elapsed,
        completed_at=result.completed_at.isoformat(),
    )


@router.patch("/interviews/{interview_id}", response_model=InterviewLinkResponse)
async def patch_interview(
    interview_id: str,
    body: PatchInterviewRequest,
    current_user: User = Depends(_hr_dependency),
    db: AsyncSession = Depends(get_db),
) -> InterviewLinkResponse:
    try:
        link_uuid = uuid.UUID(interview_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid interview ID format.",
        )

    link = await LinkService.get_link_by_id(db, link_uuid)
    if not link:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interview not found.")

    if current_user.organization_id and link.organization_id != current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

    if body.revoke:
        link = await LinkService.revoke_link(db, link_uuid)
    else:
        link = await LinkService.patch_link(
            db,
            link_uuid,
            expires_in_days=body.expires_in_days,
            notes=body.notes,
            tags=body.tags,
            custom_instructions=body.custom_instructions,
        )

    if not link:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interview not found.")

    return _link_to_response(link, get_settings().FRONTEND_URL)
