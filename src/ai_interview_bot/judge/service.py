"""Client that proxies code execution requests to the standalone Judge Service."""

from __future__ import annotations

import logging
from typing import Any, Dict, List
from uuid import UUID

import httpx
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..core.config import get_settings
from ..models.coding import CodeTestCase, CodingProblem

logger = logging.getLogger(__name__)


async def _call_judge(endpoint: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Make an HTTP call to the Judge Service."""
    settings = get_settings()
    url = f"{settings.JUDGE_SERVICE_URL}{endpoint}"

    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            logger.error("Judge returned %s: %s", e.response.status_code, e.response.text)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Judge Service error: {e.response.text}",
            )
        except httpx.ConnectError:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Judge Service is unavailable. Please try again later.",
            )


async def _fetch_problem_and_cases(
    db: AsyncSession,
    problem_id: str,
    *,
    sample_only: bool = False,
) -> tuple[CodingProblem, List[Dict[str, str]]]:
    """Load a problem and its test cases from the DB."""
    try:
        pid = UUID(problem_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid problem ID format")

    result = await db.execute(
        select(CodingProblem)
        .options(selectinload(CodingProblem.test_cases))
        .where(CodingProblem.id == pid)
    )
    problem = result.scalar_one_or_none()
    if not problem:
        raise HTTPException(status_code=404, detail="Problem not found")

    if sample_only:
        cases = [
            {"input": tc.input, "expected_output": tc.expected_output}
            for tc in sorted(problem.test_cases, key=lambda t: t.ordinal)
            if tc.is_sample
        ]
        if not cases and problem.sample_test_cases:
            cases = problem.sample_test_cases
    else:
        cases = [
            {"input": tc.input, "expected_output": tc.expected_output}
            for tc in sorted(problem.test_cases, key=lambda t: t.ordinal)
        ]

    return problem, cases


async def run_code(
    db: AsyncSession,
    code: str,
    language: str,
    problem_id: str,
) -> Dict[str, Any]:
    """Run code against sample test cases only (for 'Run' button)."""
    problem, test_cases = await _fetch_problem_and_cases(db, problem_id, sample_only=True)

    payload = {
        "code": code,
        "language": language,
        "test_cases": test_cases,
        "timeout_seconds": problem.time_limit_ms // 1000 + 2,
    }

    return await _call_judge("/run", payload)


async def submit_code(
    db: AsyncSession,
    code: str,
    language: str,
    problem_id: str,
) -> Dict[str, Any]:
    """Run code against all test cases (for 'Submit' button)."""
    problem, test_cases = await _fetch_problem_and_cases(db, problem_id, sample_only=False)

    payload = {
        "code": code,
        "language": language,
        "test_cases": test_cases,
        "timeout_seconds": problem.time_limit_ms // 1000 + 2,
    }

    return await _call_judge("/submit", payload)
