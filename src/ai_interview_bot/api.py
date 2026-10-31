"""FastAPI application — mounts all domain routers."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .core.config import get_settings
from .core.redis import close_redis

from .interviews.router import router as interviews_router
from .hr.router import router as hr_router
from .auth.router import router as auth_router
from .judge.router import router as judge_router
from .problems.router import router as problems_router


@asynccontextmanager
async def lifespan(application: FastAPI):
    yield
    await close_redis()


settings = get_settings()

app = FastAPI(
    title="AI Interview Simulator API",
    description="HTTP interface for running AI-powered interview simulations.",
    version="0.3.0",
    lifespan=lifespan,
)

# CORS ------------------------------------------------------------------
allow_origins = settings.ALLOW_ORIGINS
if allow_origins:
    origins = [o.strip() for o in allow_origins.split(",") if o.strip()]
    if origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_methods=["*"],
            allow_headers=["*"],
            allow_credentials=True,
        )

# Routers ---------------------------------------------------------------
app.include_router(interviews_router)
app.include_router(hr_router)
app.include_router(auth_router)
app.include_router(judge_router)
app.include_router(problems_router)
