"""Pydantic request/response models for the Judge Service."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class TestCase(BaseModel):
    input: str
    expected_output: str


class RunRequest(BaseModel):
    code: str
    language: str
    test_cases: List[TestCase]
    timeout_seconds: Optional[int] = None


class TestCaseResult(BaseModel):
    input: str
    expected_output: str
    actual_output: str
    passed: bool
    execution_time_ms: float
    memory_used_kb: Optional[int] = None
    error: Optional[str] = None
    status: str = "ok"  # ok | TLE | MLE | RE (runtime error)


class RunResponse(BaseModel):
    total_test_cases: int
    passed_count: int
    failed_count: int
    tle_count: int = 0
    mle_count: int = 0
    results: List[TestCaseResult]
    score: float = Field(description="Percentage of tests passed (0-100)")


class SubmitRequest(RunRequest):
    """Same as RunRequest but semantically runs all hidden test cases."""
    pass


class HealthResponse(BaseModel):
    status: str = "ok"
    available_languages: List[str]
