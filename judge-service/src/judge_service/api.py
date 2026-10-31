"""Judge Service — FastAPI application."""

from __future__ import annotations

from fastapi import FastAPI

from .config import config
from .executor import execute_code
from .models import (
    HealthResponse,
    RunRequest,
    RunResponse,
    SubmitRequest,
)

app = FastAPI(
    title="InterviewIQ Judge Service",
    description="Sandboxed code execution for interview coding challenges.",
    version="0.1.0",
)


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        available_languages=list(config.LANGUAGE_IMAGES.keys()),
    )


@app.post("/run", response_model=RunResponse)
async def run_code(body: RunRequest) -> RunResponse:
    """Run code against sample test cases (candidate-facing)."""
    timeout = body.timeout_seconds or config.RUN_TIMEOUT_SECONDS
    results = await execute_code(body.code, body.language, body.test_cases, timeout)

    passed = sum(1 for r in results if r.passed)
    tle = sum(1 for r in results if r.status == "TLE")
    mle = sum(1 for r in results if r.status == "MLE")
    total = len(results)
    score = (passed / total * 100) if total else 0

    return RunResponse(
        total_test_cases=total,
        passed_count=passed,
        failed_count=total - passed,
        tle_count=tle,
        mle_count=mle,
        results=results,
        score=round(score, 1),
    )


@app.post("/submit", response_model=RunResponse)
async def submit_code(body: SubmitRequest) -> RunResponse:
    """Run code against all hidden test cases (full evaluation)."""
    timeout = body.timeout_seconds or config.SUBMIT_TIMEOUT_PER_CASE
    results = await execute_code(body.code, body.language, body.test_cases, timeout)

    passed = sum(1 for r in results if r.passed)
    tle = sum(1 for r in results if r.status == "TLE")
    mle = sum(1 for r in results if r.status == "MLE")
    total = len(results)
    score = (passed / total * 100) if total else 0

    return RunResponse(
        total_test_cases=total,
        passed_count=passed,
        failed_count=total - passed,
        tle_count=tle,
        mle_count=mle,
        results=results,
        score=round(score, 1),
    )
