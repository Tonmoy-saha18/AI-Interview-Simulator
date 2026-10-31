"""Pydantic schemas for judge proxy endpoints."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class CodeRunRequest(BaseModel):
    code: str = Field(..., min_length=1)
    language: str
    problem_id: str


class TestCaseResult(BaseModel):
    input: str
    expected_output: str
    actual_output: str
    passed: bool
    execution_time_ms: float
    memory_used_kb: Optional[int] = None
    error: Optional[str] = None
    status: str = "ok"


class CodeRunResponse(BaseModel):
    total_test_cases: int
    passed_count: int
    failed_count: int
    tle_count: int = 0
    mle_count: int = 0
    results: List[TestCaseResult]
    score: float
