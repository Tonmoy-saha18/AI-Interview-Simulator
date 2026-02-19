"""Service for generating and validating interview links."""

from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..models import InterviewLink, InterviewLinkStatus


class LinkService:
    """Service for managing interview links."""

    @staticmethod
    def generate_token() -> str:
        """Generate a secure random token for interview link."""
        return secrets.token_urlsafe(32)

    @staticmethod
    async def create_interview_link(
        session: AsyncSession,
        hr_email: str,
        candidate_email: str,
        candidate_name: Optional[str],
        role: str,
        level: str,
        question_limit: int,
        expires_in_days: int,
        cv_file_path: Optional[str] = None,
        cv_extracted_data: Optional[dict] = None,
    ) -> InterviewLink:
        """Create a new interview link."""
        token = LinkService.generate_token()
        expires_at = datetime.utcnow() + timedelta(days=expires_in_days)

        interview_link = InterviewLink(
            token=token,
            hr_email=hr_email,
            candidate_email=candidate_email,
            candidate_name=candidate_name,
            role=role,
            level=level,
            question_limit=question_limit,
            expires_at=expires_at,
            cv_file_path=cv_file_path,
            cv_extracted_data=cv_extracted_data,
            status=InterviewLinkStatus.PENDING,
        )

        session.add(interview_link)
        await session.flush()
        await session.refresh(interview_link)

        return interview_link

    @staticmethod
    async def get_link_by_token(
        session: AsyncSession,
        token: str,
    ) -> Optional[InterviewLink]:
        """Get interview link by token."""
        result = await session.execute(
            select(InterviewLink).where(InterviewLink.token == token)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def validate_and_activate_link(
        session: AsyncSession,
        token: str,
    ) -> tuple[bool, Optional[InterviewLink], Optional[str]]:
        """Validate link and activate it if valid.

        Returns:
            (is_valid, interview_link, error_message)
        """
        interview_link = await LinkService.get_link_by_token(session, token)

        if not interview_link:
            return False, None, "Invalid interview link token."

        if interview_link.is_expired():
            interview_link.status = InterviewLinkStatus.EXPIRED
            await session.commit()
            return False, None, "This interview link has expired."

        if interview_link.status == InterviewLinkStatus.COMPLETED:
            return False, None, "This interview has already been completed."

        if interview_link.status == InterviewLinkStatus.EXPIRED:
            return False, None, "This interview link has expired."

        if interview_link.status == InterviewLinkStatus.PENDING:
            interview_link.status = InterviewLinkStatus.IN_PROGRESS
            interview_link.used_at = datetime.utcnow()
            await session.commit()

        return True, interview_link, None

    @staticmethod
    async def mark_interview_completed(
        session: AsyncSession,
        interview_link_id: uuid.UUID,
    ) -> None:
        """Mark interview link as completed."""
        result = await session.execute(
            select(InterviewLink).where(InterviewLink.id == interview_link_id)
        )
        interview_link = result.scalar_one_or_none()

        if interview_link:
            interview_link.status = InterviewLinkStatus.COMPLETED
            await session.commit()

    @staticmethod
    async def get_links_by_hr_email(
        session: AsyncSession,
        hr_email: str,
    ) -> list[InterviewLink]:
        """Get all interview links created by an HR user."""
        result = await session.execute(
            select(InterviewLink)
            .where(InterviewLink.hr_email == hr_email)
            .order_by(InterviewLink.created_at.desc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def get_link_by_id(
        session: AsyncSession,
        link_id: uuid.UUID,
    ) -> Optional[InterviewLink]:
        """Get interview link by ID."""
        result = await session.execute(
            select(InterviewLink).where(InterviewLink.id == link_id)
        )
        return result.scalar_one_or_none()
