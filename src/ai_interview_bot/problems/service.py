"""Business logic for the coding problem bank."""

from __future__ import annotations

import uuid
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models.coding import CodeTestCase, CodingProblem
from .schemas import CreateProblemRequest, PatchProblemRequest, SampleTestCase


class ProblemService:

    @staticmethod
    async def list_problems(
        db: AsyncSession,
        *,
        difficulty: Optional[str] = None,
        topic: Optional[str] = None,
        active_only: bool = True,
    ) -> List[CodingProblem]:
        query = select(CodingProblem).order_by(CodingProblem.created_at.desc())
        if active_only:
            query = query.where(CodingProblem.is_active == True)  # noqa: E712
        if difficulty:
            query = query.where(CodingProblem.difficulty == difficulty)
        if topic:
            query = query.where(CodingProblem.topic_tags.any(topic))
        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def get_problem(
        db: AsyncSession,
        problem_id: uuid.UUID,
    ) -> Optional[CodingProblem]:
        result = await db.execute(
            select(CodingProblem)
            .options(selectinload(CodingProblem.test_cases))
            .where(CodingProblem.id == problem_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_problem_by_slug(
        db: AsyncSession,
        slug: str,
    ) -> Optional[CodingProblem]:
        result = await db.execute(
            select(CodingProblem)
            .options(selectinload(CodingProblem.test_cases))
            .where(CodingProblem.slug == slug)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def create_problem(
        db: AsyncSession,
        body: CreateProblemRequest,
    ) -> CodingProblem:
        sample_json = [tc.model_dump() for tc in body.sample_test_cases]

        problem = CodingProblem(
            title=body.title,
            slug=body.slug,
            description_md=body.description_md,
            constraints_md=body.constraints_md,
            difficulty=body.difficulty,
            topic_tags=body.topic_tags,
            supported_languages=body.supported_languages,
            function_signatures=body.function_signatures,
            sample_test_cases=sample_json,
            hidden_test_case_count=len(body.hidden_test_cases),
            time_limit_ms=body.time_limit_ms,
            memory_limit_kb=body.memory_limit_kb,
            expected_time_complexity=body.expected_time_complexity,
            expected_space_complexity=body.expected_space_complexity,
            hint_1=body.hint_1,
            hint_2=body.hint_2,
            solution_skeleton=body.solution_skeleton,
        )
        db.add(problem)
        await db.flush()
        await db.refresh(problem)

        ordinal = 0
        for tc in body.sample_test_cases:
            ordinal += 1
            db.add(CodeTestCase(
                problem_id=problem.id,
                input=tc.input,
                expected_output=tc.expected_output,
                is_sample=True,
                ordinal=ordinal,
            ))

        for tc in body.hidden_test_cases:
            ordinal += 1
            db.add(CodeTestCase(
                problem_id=problem.id,
                input=tc.input,
                expected_output=tc.expected_output,
                is_sample=False,
                ordinal=ordinal,
            ))

        await db.flush()
        return problem

    @staticmethod
    async def patch_problem(
        db: AsyncSession,
        problem_id: uuid.UUID,
        body: PatchProblemRequest,
    ) -> Optional[CodingProblem]:
        problem = await ProblemService.get_problem(db, problem_id)
        if not problem:
            return None

        problem.version += 1

        for field_name in [
            "title", "description_md", "constraints_md", "difficulty",
            "topic_tags", "supported_languages", "function_signatures",
            "time_limit_ms", "memory_limit_kb",
            "expected_time_complexity", "expected_space_complexity",
            "hint_1", "hint_2", "solution_skeleton", "is_active",
        ]:
            val = getattr(body, field_name, None)
            if val is not None:
                setattr(problem, field_name, val)

        if body.sample_test_cases is not None:
            problem.sample_test_cases = [tc.model_dump() for tc in body.sample_test_cases]

        if body.hidden_test_cases is not None:
            for tc in list(problem.test_cases):
                await db.delete(tc)
            await db.flush()

            ordinal = 0
            all_samples = body.sample_test_cases or [
                SampleTestCase(**tc) for tc in (problem.sample_test_cases or [])
            ]
            for tc in all_samples:
                ordinal += 1
                db.add(CodeTestCase(
                    problem_id=problem.id,
                    problem_version=problem.version,
                    input=tc.input,
                    expected_output=tc.expected_output,
                    is_sample=True,
                    ordinal=ordinal,
                ))
            for tc in body.hidden_test_cases:
                ordinal += 1
                db.add(CodeTestCase(
                    problem_id=problem.id,
                    problem_version=problem.version,
                    input=tc.input,
                    expected_output=tc.expected_output,
                    is_sample=False,
                    ordinal=ordinal,
                ))
            problem.hidden_test_case_count = len(body.hidden_test_cases)

        await db.flush()
        await db.refresh(problem)
        return problem

    @staticmethod
    async def soft_delete(
        db: AsyncSession,
        problem_id: uuid.UUID,
    ) -> bool:
        problem = await ProblemService.get_problem(db, problem_id)
        if not problem:
            return False
        problem.is_active = False
        await db.flush()
        return True
