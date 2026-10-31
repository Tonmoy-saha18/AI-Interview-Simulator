"""Pydantic request/response schemas for auth endpoints."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    display_name: Optional[str] = Field(None, max_length=255)
    role: str = Field("candidate", pattern=r"^(candidate|hr)$")
    organization_name: Optional[str] = Field(
        None,
        max_length=255,
        description="Required for HR users; creates or joins an organization.",
    )


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: str
    email: str
    display_name: Optional[str]
    role: str
    organization_id: Optional[str]
    organization_name: Optional[str] = None
    email_verified: bool
    is_active: bool
    created_at: str


class UpdateProfileRequest(BaseModel):
    display_name: Optional[str] = Field(None, max_length=255)
    email: Optional[EmailStr] = None
