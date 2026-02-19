"""Auth HTTP endpoints — placeholder for Sprint 2.

Will include: register, login, refresh, logout, profile (me).
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/auth", tags=["auth"])
