"""Pydantic schemas for coding problems CRUD."""

from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class SampleTestCase(BaseModel):
    input: str
    expected_output: str


class CreateProblemRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    slug: str = Field(..., min_length=1, max_length=255)
    description_md: str
    constraints_md: Optional[str] = None
    difficulty: str = Field("medium")
    topic_tags: List[str] = Field(default_factory=list)
    supported_languages: List[str] = Field(default_factory=lambda: ["python", "javascript"])
    function_signatures: Optional[Dict[str, str]] = None
    sample_test_cases: List[SampleTestCase] = Field(default_factory=list)
    time_limit_ms: int = Field(2000, ge=100, le=30000)
    memory_limit_kb: int = Field(262144, ge=1024)
    expected_time_complexity: Optional[str] = None
    expected_space_complexity: Optional[str] = None
    hint_1: Optional[str] = None
    hint_2: Optional[str] = None
    solution_skeleton: Optional[str] = None
    hidden_test_cases: List[SampleTestCase] = Field(default_factory=list)


class PatchProblemRequest(BaseModel):
    title: Optional[str] = None
    description_md: Optional[str] = None
    constraints_md: Optional[str] = None
    difficulty: Optional[str] = None
    topic_tags: Optional[List[str]] = None
    supported_languages: Optional[List[str]] = None
    function_signatures: Optional[Dict[str, str]] = None
    sample_test_cases: Optional[List[SampleTestCase]] = None
    time_limit_ms: Optional[int] = None
    memory_limit_kb: Optional[int] = None
    expected_time_complexity: Optional[str] = None
    expected_space_complexity: Optional[str] = None
    hint_1: Optional[str] = None
    hint_2: Optional[str] = None
    solution_skeleton: Optional[str] = None
    hidden_test_cases: Optional[List[SampleTestCase]] = None
    is_active: Optional[bool] = None


class ProblemResponse(BaseModel):
    id: str
    title: str
    slug: str
    description_md: str
    constraints_md: Optional[str] = None
    difficulty: str
    topic_tags: List[str]
    supported_languages: List[str]
    function_signatures: Optional[Dict[str, str]] = None
    sample_test_cases: List[SampleTestCase]
    hidden_test_case_count: int
    time_limit_ms: int
    memory_limit_kb: int
    expected_time_complexity: Optional[str] = None
    expected_space_complexity: Optional[str] = None
    version: int
    is_active: bool
    hint_1: Optional[str] = None
    hint_2: Optional[str] = None
    solution_skeleton: Optional[str] = None


class ProblemListItem(BaseModel):
    id: str
    title: str
    slug: str
    difficulty: str
    topic_tags: List[str]
    supported_languages: List[str]
    is_active: bool
