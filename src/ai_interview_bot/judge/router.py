"""Judge proxy endpoints — run/submit code via the Judge Service."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from .schemas import CodeRunRequest, CodeRunResponse
from .service import run_code, submit_code

router = APIRouter(prefix="/api/v1", tags=["judge"])


@router.post(
    "/interviews/{session_id}/code/run",
    response_model=CodeRunResponse,
)
async def run_code_endpoint(
    session_id: str,
    body: CodeRunRequest,
    db: AsyncSession = Depends(get_db),
) -> CodeRunResponse:
    """Run candidate code against sample test cases."""
    result = await run_code(db, body.code, body.language, body.problem_id)
    return CodeRunResponse(**result)


@router.post(
    "/interviews/{session_id}/code/submit",
    response_model=CodeRunResponse,
)
async def submit_code_endpoint(
    session_id: str,
    body: CodeRunRequest,
    db: AsyncSession = Depends(get_db),
) -> CodeRunResponse:
    """Submit candidate code for full evaluation against all test cases."""
    result = await submit_code(db, body.code, body.language, body.problem_id)
    return CodeRunResponse(**result)
