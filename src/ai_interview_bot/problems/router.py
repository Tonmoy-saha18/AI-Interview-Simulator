"""Problem bank HTTP endpoints — CRUD for coding problems."""

from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.dependencies import get_current_user, require_role
from ..core.database import get_db
from ..models.user import User, UserRole
from .schemas import (
    CreateProblemRequest,
    PatchProblemRequest,
    ProblemListItem,
    ProblemResponse,
    SampleTestCase,
)
from .service import ProblemService

router = APIRouter(prefix="/api/v1/problems", tags=["problems"])

_admin_dep = require_role([UserRole.PLATFORM_ADMIN, UserRole.ORG_ADMIN])


def _problem_to_list_item(p) -> ProblemListItem:
    return ProblemListItem(
        id=str(p.id),
        title=p.title,
        slug=p.slug,
        difficulty=p.difficulty,
        topic_tags=p.topic_tags or [],
        supported_languages=p.supported_languages or [],
        is_active=p.is_active,
    )


def _problem_to_response(p) -> ProblemResponse:
    return ProblemResponse(
        id=str(p.id),
        title=p.title,
        slug=p.slug,
        description_md=p.description_md,
        constraints_md=p.constraints_md,
        difficulty=p.difficulty,
        topic_tags=p.topic_tags or [],
        supported_languages=p.supported_languages or [],
        function_signatures=p.function_signatures,
        sample_test_cases=[
            SampleTestCase(**tc) for tc in (p.sample_test_cases or [])
        ],
        hidden_test_case_count=p.hidden_test_case_count,
        time_limit_ms=p.time_limit_ms,
        memory_limit_kb=p.memory_limit_kb,
        expected_time_complexity=p.expected_time_complexity,
        expected_space_complexity=p.expected_space_complexity,
        version=p.version,
        is_active=p.is_active,
        hint_1=p.hint_1,
        hint_2=p.hint_2,
        solution_skeleton=p.solution_skeleton,
    )


@router.get("", response_model=List[ProblemListItem])
async def list_problems(
    difficulty: Optional[str] = None,
    topic: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
) -> List[ProblemListItem]:
    problems = await ProblemService.list_problems(db, difficulty=difficulty, topic=topic)
    return [_problem_to_list_item(p) for p in problems]


@router.get("/{problem_id}", response_model=ProblemResponse)
async def get_problem(
    problem_id: str,
    db: AsyncSession = Depends(get_db),
) -> ProblemResponse:
    try:
        pid = UUID(problem_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid problem ID")
    problem = await ProblemService.get_problem(db, pid)
    if not problem:
        raise HTTPException(status_code=404, detail="Problem not found")
    return _problem_to_response(problem)


@router.post("", response_model=ProblemResponse, status_code=status.HTTP_201_CREATED)
async def create_problem(
    body: CreateProblemRequest,
    _user: User = Depends(_admin_dep),
    db: AsyncSession = Depends(get_db),
) -> ProblemResponse:
    problem = await ProblemService.create_problem(db, body)
    return _problem_to_response(problem)


@router.patch("/{problem_id}", response_model=ProblemResponse)
async def patch_problem(
    problem_id: str,
    body: PatchProblemRequest,
    _user: User = Depends(_admin_dep),
    db: AsyncSession = Depends(get_db),
) -> ProblemResponse:
    try:
        pid = UUID(problem_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid problem ID")
    problem = await ProblemService.patch_problem(db, pid, body)
    if not problem:
        raise HTTPException(status_code=404, detail="Problem not found")
    return _problem_to_response(problem)


@router.get("/{problem_id}/hints/{hint_level}")
async def get_hint(
    problem_id: str,
    hint_level: int,
    db: AsyncSession = Depends(get_db),
):
    """Get a progressive hint for a problem (1, 2, or 3 for solution skeleton)."""
    try:
        pid = UUID(problem_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid problem ID")
    problem = await ProblemService.get_problem(db, pid)
    if not problem:
        raise HTTPException(status_code=404, detail="Problem not found")

    hint_map = {1: problem.hint_1, 2: problem.hint_2, 3: problem.solution_skeleton}
    hint = hint_map.get(hint_level)
    if hint is None:
        raise HTTPException(status_code=404, detail="Hint not available at this level")
    return {"hint_level": hint_level, "content": hint}


@router.delete("/{problem_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_problem(
    problem_id: str,
    _user: User = Depends(_admin_dep),
    db: AsyncSession = Depends(get_db),
) -> None:
    try:
        pid = UUID(problem_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid problem ID")
    deleted = await ProblemService.soft_delete(db, pid)
    if not deleted:
        raise HTTPException(status_code=404, detail="Problem not found")
