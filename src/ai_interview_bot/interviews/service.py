"""Interview session management — business logic and state helpers."""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import HTTPException, status
from openai import RateLimitError, APIError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..graph import build_interview_app
from ..graph.state import InterviewConfig, QARecord
from ..graph.stream_utils import extract_interrupt_value, get_state_values, iter_event_values
from ..models import InterviewLink, InterviewResult
from ..hr.service import LinkService
from .schemas import (
    AnswerRequest,
    EvaluationModel,
    InterviewStartRequest,
    InterviewStepResponse,
    QARecordModel,
)


@dataclass(slots=True)
class InterviewSession:
    """Mutable state wrapper for a running interview."""

    app: Any
    config: InterviewConfig
    graph_config: Dict[str, Any]
    last_question: Optional[str] = None
    finished: bool = False
    interview_link_id: Optional[uuid.UUID] = None
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class InterviewManager:
    """In-memory session registry driving LangGraph runs."""

    def __init__(self) -> None:
        self._sessions: Dict[str, InterviewSession] = {}
        self._lock = asyncio.Lock()

    async def create_session(self, payload: InterviewStartRequest) -> InterviewSession:
        async with self._lock:
            thread_id = str(uuid4())
            config = InterviewConfig(
                candidate_profile=payload.candidate_profile,
                role=payload.role,
                level=payload.level,
                question_limit=payload.questions,
                thread_id=thread_id,
            )
            app = build_interview_app()
            graph_config = {"configurable": {"thread_id": thread_id}}
            app.update_state(graph_config, config.initial_state())
            session = InterviewSession(app=app, config=config, graph_config=graph_config)
            self._sessions[thread_id] = session
            return session

    async def get_session(self, session_id: str) -> InterviewSession:
        async with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Interview session '{session_id}' was not found.",
                )
            return session

    async def remove_session(self, session_id: str) -> None:
        async with self._lock:
            self._sessions.pop(session_id, None)


manager = InterviewManager()


# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------

def serialise_evaluation(data: Optional[Dict[str, Any]]) -> Optional[EvaluationModel]:
    if not data:
        return None
    return EvaluationModel(
        score=int(data.get("score", data.get("overall_score", 0))),
        overall_score=data.get("overall_score"),
        technical_depth=data.get("technical_depth"),
        communication=data.get("communication"),
        problem_solving=data.get("problem_solving"),
        reasoning=str(data.get("reasoning", "")),
        strengths=list(data.get("strengths") or []),
        improvements=list(data.get("improvements") or []),
        follow_up=data.get("follow_up"),
    )


def serialise_history(history: List[QARecord]) -> List[QARecordModel]:
    """Serialize QA history including nested follow-up questions."""
    records: List[QARecordModel] = []
    for item in history:
        follow_ups = item.get("follow_ups")
        follow_ups_models = None
        if follow_ups:
            follow_ups_models = [
                QARecordModel(
                    question=fu.get("question", ""),
                    answer=fu.get("answer", ""),
                    evaluation=serialise_evaluation(fu.get("evaluation")),
                )
                for fu in follow_ups
            ]

        records.append(
            QARecordModel(
                question=item.get("question", ""),
                answer=item.get("answer", ""),
                evaluation=serialise_evaluation(item.get("evaluation")),
                follow_ups=follow_ups_models,
            )
        )
    return records


# ---------------------------------------------------------------------------
# Session helpers
# ---------------------------------------------------------------------------

def prepare_response(
    session_id: str,
    session: InterviewSession,
    *,
    prompt_hint: Optional[str],
) -> InterviewStepResponse:
    state_values = get_state_values(session.app, session.graph_config)
    question = state_values.get("current_question")
    question_index = state_values.get("question_index")
    question_limit = state_values.get("question_limit") or session.config.question_limit
    feedback = state_values.get("feedback")
    evaluation = state_values.get("evaluation")
    qa_history = state_values.get("qa_history", [])

    session.last_question = question or session.last_question
    session.finished = bool(feedback)

    if isinstance(prompt_hint, str):
        prompt_hint_value = prompt_hint.strip()
    elif prompt_hint is not None:
        prompt_hint_value = str(prompt_hint)
    else:
        prompt_hint_value = None

    if session.finished:
        status_value = "completed"
    elif question:
        status_value = "awaiting_answer"
    else:
        status_value = "in_progress"

    if session.finished:
        prompt_value = None
    else:
        prompt_value = prompt_hint_value or question or session.last_question

    time_elapsed = None
    time_remaining = None
    answer_start_time_str = state_values.get("answer_start_time")
    question_time_limit = state_values.get("question_time_limit")

    if answer_start_time_str and question_time_limit:
        try:
            start_time = datetime.fromisoformat(answer_start_time_str)
            elapsed = datetime.now() - start_time
            time_elapsed = int(elapsed.total_seconds())
            time_remaining = max(0, question_time_limit - time_elapsed)
        except (ValueError, TypeError):
            pass

    return InterviewStepResponse(
        session_id=session_id,
        status=status_value,
        question=question if not session.finished else None,
        question_index=question_index,
        question_limit=question_limit,
        evaluation=serialise_evaluation(evaluation),
        feedback=feedback,
        qa_history=serialise_history(qa_history),
        prompt=prompt_value,
        question_difficulty=state_values.get("question_difficulty"),
        question_time_limit=question_time_limit,
        time_elapsed=time_elapsed,
        time_remaining=time_remaining,
        total_time_elapsed=state_values.get("total_time_elapsed"),
        time_expired=state_values.get("time_expired"),
        is_follow_up=state_values.get("is_follow_up"),
        follow_up_count=state_values.get("follow_up_count"),
    )


async def drive_session(session_id: str, session: InterviewSession) -> InterviewStepResponse:
    """Stream the LangGraph until it interrupts or finishes."""
    prompt_hint: Optional[str] = None
    async with session.lock:
        if session.finished:
            return prepare_response(session_id, session, prompt_hint=None)

        try:
            for event in session.app.stream(None, config=session.graph_config):
                for payload in iter_event_values(event):
                    if "current_question" in payload:
                        session.last_question = payload["current_question"]
                if "__interrupt__" in event:
                    prompt_hint = extract_interrupt_value(event.get("__interrupt__"))
                    break
        except RateLimitError as e:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(
                    "OpenAI API rate limit exceeded. Please check your API quota "
                    f"and billing details. Original error: {e!s}"
                ),
            )
        except APIError as e:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"OpenAI API error: {e!s}",
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"An unexpected error occurred: {e!s}",
            )

        return prepare_response(session_id, session, prompt_hint=prompt_hint)


async def store_interview_results(
    session: InterviewSession,
    session_id: str,
    db: AsyncSession,
) -> None:
    """Persist interview results in the database if linked to an interview_link."""
    if not session.interview_link_id:
        return

    state_values = get_state_values(session.app, session.graph_config)
    feedback = state_values.get("feedback")
    qa_history = state_values.get("qa_history", [])
    total_time_elapsed = state_values.get("total_time_elapsed", 0)

    scores = []
    for qa in qa_history:
        eval_data = qa.get("evaluation", {})
        overall_score = eval_data.get("overall_score") or eval_data.get("score")
        if overall_score is not None:
            scores.append(overall_score)

    overall_score_str = None
    if scores:
        avg_score = sum(scores) / len(scores)
        overall_score_str = f"{avg_score:.1f}/5"

    existing_result = await db.execute(
        select(InterviewResult).where(InterviewResult.session_id == session_id)
    )
    result = existing_result.scalar_one_or_none()

    if result:
        result.final_feedback = feedback
        result.overall_score = overall_score_str
        result.qa_history = qa_history
        result.total_time_elapsed = total_time_elapsed
    else:
        result = InterviewResult(
            interview_link_id=session.interview_link_id,
            session_id=session_id,
            final_feedback=feedback,
            overall_score=overall_score_str,
            qa_history=qa_history,
            total_time_elapsed=total_time_elapsed,
        )
        db.add(result)

    await db.commit()
    await LinkService.mark_interview_completed(db, session.interview_link_id)
