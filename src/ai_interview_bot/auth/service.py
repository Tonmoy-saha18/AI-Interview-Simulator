"""Auth business logic — registration, login, token management."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
)
from ..models.organization import Organization
from ..models.user import User, UserRole


def _slugify(name: str) -> str:
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", slug).strip("-")
    return slug


class AuthService:
    @staticmethod
    async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
        result = await db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_user_by_id(db: AsyncSession, user_id: UUID) -> Optional[User]:
        result = await db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def register(
        db: AsyncSession,
        email: str,
        password: str,
        role: str = UserRole.CANDIDATE,
        display_name: Optional[str] = None,
        organization_name: Optional[str] = None,
    ) -> User:
        existing = await AuthService.get_user_by_email(db, email)
        if existing:
            raise ValueError("A user with this email already exists.")

        if role not in (UserRole.CANDIDATE, UserRole.HR):
            raise ValueError("Invalid role. Must be 'candidate' or 'hr'.")

        org: Optional[Organization] = None
        if role == UserRole.HR:
            if not organization_name:
                raise ValueError("Organization name is required for HR users.")
            slug = _slugify(organization_name)
            result = await db.execute(select(Organization).where(Organization.slug == slug))
            org = result.scalar_one_or_none()
            if org is None:
                org = Organization(name=organization_name, slug=slug)
                db.add(org)
                await db.flush()

        user = User(
            email=email,
            password_hash=hash_password(password),
            display_name=display_name,
            role=role,
            organization_id=org.id if org else None,
        )
        db.add(user)
        await db.flush()
        return user

    @staticmethod
    async def authenticate(db: AsyncSession, email: str, password: str) -> Optional[User]:
        user = await AuthService.get_user_by_email(db, email)
        if user is None or not verify_password(password, user.password_hash):
            return None
        if not user.is_active:
            return None
        user.last_login_at = datetime.now(timezone.utc)
        await db.flush()
        return user

    @staticmethod
    def create_tokens(user: User) -> tuple[str, str]:
        payload = {"sub": str(user.id), "email": user.email, "role": user.role}
        access = create_access_token(payload)
        refresh = create_refresh_token(payload)
        return access, refresh

    @staticmethod
    async def update_profile(
        db: AsyncSession,
        user: User,
        display_name: Optional[str] = None,
        email: Optional[str] = None,
    ) -> User:
        if display_name is not None:
            user.display_name = display_name
        if email is not None and email != user.email:
            existing = await AuthService.get_user_by_email(db, email)
            if existing:
                raise ValueError("A user with this email already exists.")
            user.email = email
            user.email_verified = False
        user.updated_at = datetime.now(timezone.utc)
        await db.flush()
        return user
