"""Application settings loaded from environment variables."""

from __future__ import annotations

import os
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


class Settings:
    """Centralised application settings."""

    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@localhost/ai_interview_db",
    )
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    DATABASE_ECHO: bool = os.getenv("DATABASE_ECHO", "false").lower() == "true"

    FRONTEND_URL: str = os.getenv(
        "FRONTEND_URL", os.getenv("BASE_URL", "http://localhost:8080")
    ).rstrip("/")

    ALLOW_ORIGINS: str = os.getenv("AI_INTERVIEW_ALLOW_ORIGINS", "*")

    MAX_CV_FILE_SIZE_MB: int = int(os.getenv("MAX_CV_FILE_SIZE_MB", "10"))


@lru_cache
def get_settings() -> Settings:
    """Return a cached singleton of application settings."""
    return Settings()
