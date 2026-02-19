"""Interview session management — business logic and state helpers."""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from openai import RateLimitError, APIError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..core.redis import delete_session_state, save_session_state
from ..graph import build_interview_app
from ..graph.state import InterviewConfig, QARecord
from ..graph.stream_utils import extract_interrupt_value, get_state_values, iter_event_values
from ..models import InterviewLink, InterviewResult
from ..models.interview import (
    InterviewFeedback,
    InterviewQuestion,
    InterviewSession,
    SessionStatus,
)
from ..hr.service import LinkService
from .schemas import (
    AnswerRequest,
    EvaluationModel,
    InterviewQuestionDetail,
    InterviewReportResponse,
    InterviewSessionListItem,
    InterviewStartRequest,
    InterviewStepResponse,
    QARecordModel,
)


# ---------------------------------------------------------------------------
# In-memory session wrapper (active LangGraph runs)
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class ActiveSession:
    """Mutable state wrapper for a running interview."""

    app: Any
    config: InterviewConfig
    graph_config: Dict[str, Any]
    db_session_id: UUID
    last_question: Optional[str] = None
    finished: bool = False
    persisted: bool = False
    interview_link_id: Optional[uuid.UUID] = None
    user_id: Optional[UUID] = None
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class InterviewManager:
    """In-memory session registry driving LangGraph runs."""

    def __init__(self) -> None:
        self._sessions: Dict[str, ActiveSession] = {}
        self._lock = asyncio.Lock()

    async def create_session(
        self,
        payload: InterviewStartRequest,
        db: AsyncSession,
        *,
        user_id: Optional[UUID] = None,
        interview_link_id: Optional[UUID] = None,
    ) -> ActiveSession:
        async with self._lock:
            session_uuid = uuid4()
            thread_id = str(session_uuid)

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

            # Persist the session record to the database
            db_session = InterviewSession(
                id=session_uuid,
                user_id=user_id,
                interview_link_id=interview_link_id,
                role=payload.role,
                level=payload.level,
                interview_type=payload.interview_type.value,
                total_questions=payload.questions,
                status=SessionStatus.IN_PROGRESS.value,
            )
            db.add(db_session)
            await db.flush()

            session = ActiveSession(
                app=app,
                config=config,
                graph_config=graph_config,
                db_session_id=session_uuid,
                interview_link_id=interview_link_id,
                user_id=user_id,
            )
            self._sessions[thread_id] = session
            return session

    async def get_session(self, session_id: str) -> ActiveSession:
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
        await delete_session_state(session_id)


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
    session: ActiveSession,
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


async def drive_session(session_id: str, session: ActiveSession) -> InterviewStepResponse:
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

        # Cache current state in Redis for persistence
        state_values = get_state_values(session.app, session.graph_config)
        await save_session_state(session_id, state_values)

        return prepare_response(session_id, session, prompt_hint=prompt_hint)


# ---------------------------------------------------------------------------
# DB persistence for completed sessions
# ---------------------------------------------------------------------------

async def persist_session_completion(
    session: ActiveSession,
    session_id: str,
    db: AsyncSession,
) -> None:
    """Write interview_questions + interview_feedback rows when an interview finishes."""
    if session.persisted:
        return
    session.persisted = True

    state_values = get_state_values(session.app, session.graph_config)
    qa_history: List[Dict[str, Any]] = state_values.get("qa_history", [])
    feedback_text: Optional[str] = state_values.get("feedback")
    total_time = state_values.get("total_time_elapsed", 0)

    db_session_id = session.db_session_id

    # Update session record
    result = await db.execute(
        select(InterviewSession).where(InterviewSession.id == db_session_id)
    )
    db_session = result.scalar_one_or_none()
    if db_session:
        db_session.status = SessionStatus.COMPLETED.value
        db_session.completed_at = datetime.utcnow()
        db_session.total_time_seconds = total_time
        db_session.graph_state = state_values

    # Persist individual questions
    seq = 0
    all_scores: List[Dict[str, Any]] = []
    for qa in qa_history:
        seq += 1
        eval_data = qa.get("evaluation", {})
        score = eval_data.get("overall_score") or eval_data.get("score")

        q = InterviewQuestion(
            session_id=db_session_id,
            sequence_number=seq,
            question_text=qa.get("question", ""),
            question_type="behavioral",
            difficulty=state_values.get("question_difficulty"),
            answer_text=qa.get("answer", ""),
            score=score,
            evaluation_json=eval_data or None,
            time_taken_seconds=eval_data.get("time_taken"),
            time_expired=False,
        )
        db.add(q)
        if eval_data:
            all_scores.append(eval_data)

        # Follow-ups
        for fu in qa.get("follow_ups", []):
            seq += 1
            fu_eval = fu.get("evaluation", {})
            fu_score = fu_eval.get("overall_score") or fu_eval.get("score")
            fu_q = InterviewQuestion(
                session_id=db_session_id,
                sequence_number=seq,
                parent_question_id=q.id,
                question_text=fu.get("question", ""),
                question_type="follow_up",
                difficulty=state_values.get("question_difficulty"),
                answer_text=fu.get("answer", ""),
                score=fu_score,
                evaluation_json=fu_eval or None,
                time_expired=False,
            )
            db.add(fu_q)
            if fu_eval:
                all_scores.append(fu_eval)

    # Compute aggregate scores for feedback record
    overall, tech, comm, ps = _aggregate_scores(all_scores)
    strengths, improvements = _aggregate_feedback_items(all_scores)

    per_question_analysis = [
        {
            "question": qa.get("question", ""),
            "score": (qa.get("evaluation") or {}).get("overall_score"),
            "reasoning": (qa.get("evaluation") or {}).get("reasoning", ""),
        }
        for qa in qa_history
    ]

    fb = InterviewFeedback(
        session_id=db_session_id,
        overall_score=overall,
        technical_depth_score=tech,
        communication_score=comm,
        problem_solving_score=ps,
        summary_text=feedback_text,
        strengths=strengths,
        improvements=improvements,
        per_question_analysis=per_question_analysis,
    )
    db.add(fb)

    await db.flush()

    # Clean up Redis cache
    await delete_session_state(session_id)


def _aggregate_scores(
    evals: List[Dict[str, Any]],
) -> tuple[Optional[int], Optional[int], Optional[int], Optional[int]]:
    """Compute average scores across all evaluations, scaled to 0-100."""
    if not evals:
        return None, None, None, None

    tech_scores = [e["technical_depth"] for e in evals if e.get("technical_depth")]
    comm_scores = [e["communication"] for e in evals if e.get("communication")]
    ps_scores = [e["problem_solving"] for e in evals if e.get("problem_solving")]
    overall_scores = [e.get("overall_score") or e.get("score") for e in evals]
    overall_scores = [s for s in overall_scores if s is not None]

    def avg_pct(scores: List[int]) -> Optional[int]:
        if not scores:
            return None
        return round((sum(scores) / len(scores) / 5) * 100)

    return (
        avg_pct(overall_scores),
        avg_pct(tech_scores),
        avg_pct(comm_scores),
        avg_pct(ps_scores),
    )


def _aggregate_feedback_items(
    evals: List[Dict[str, Any]],
) -> tuple[List[str], List[str]]:
    strengths: List[str] = []
    improvements: List[str] = []
    seen_s: set[str] = set()
    seen_i: set[str] = set()
    for e in evals:
        for s in e.get("strengths") or []:
            if s not in seen_s:
                strengths.append(s)
                seen_s.add(s)
        for i in e.get("improvements") or []:
            if i not in seen_i:
                improvements.append(i)
                seen_i.add(i)
    return strengths, improvements


async def store_interview_results(
    session: ActiveSession,
    session_id: str,
    db: AsyncSession,
) -> None:
    """Persist interview results in the legacy table if linked to an interview_link."""
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

    await db.flush()
    await LinkService.mark_interview_completed(db, session.interview_link_id)


# ---------------------------------------------------------------------------
# History & report queries
# ---------------------------------------------------------------------------

async def list_user_interviews(
    db: AsyncSession,
    user_id: UUID,
) -> List[InterviewSessionListItem]:
    """Return all interview sessions for a given user, newest first."""
    result = await db.execute(
        select(InterviewSession)
        .options(selectinload(InterviewSession.feedback))
        .where(InterviewSession.user_id == user_id)
        .order_by(InterviewSession.started_at.desc())
    )
    sessions = result.scalars().all()

    items: List[InterviewSessionListItem] = []
    for s in sessions:
        overall_score = s.feedback.overall_score if s.feedback else None
        items.append(
            InterviewSessionListItem(
                session_id=str(s.id),
                role=s.role,
                level=s.level,
                interview_type=s.interview_type,
                total_questions=s.total_questions,
                status=s.status,
                overall_score=overall_score,
                started_at=s.started_at.isoformat(),
                completed_at=s.completed_at.isoformat() if s.completed_at else None,
                total_time_seconds=s.total_time_seconds,
            )
        )
    return items


async def get_interview_report(
    db: AsyncSession,
    session_id: UUID,
    user_id: Optional[UUID] = None,
) -> InterviewReportResponse:
    """Build a full structured report for a session."""
    query = (
        select(InterviewSession)
        .options(
            selectinload(InterviewSession.feedback),
            selectinload(InterviewSession.questions),
        )
        .where(InterviewSession.id == session_id)
    )
    if user_id is not None:
        query = query.where(InterviewSession.user_id == user_id)

    result = await db.execute(query)
    s = result.scalar_one_or_none()

    if not s:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Interview session not found.",
        )

    # Build question details from DB rows
    question_map: Dict[UUID, InterviewQuestionDetail] = {}
    top_level: List[InterviewQuestionDetail] = []

    for q in sorted(s.questions, key=lambda x: x.sequence_number):
        detail = InterviewQuestionDetail(
            question_id=str(q.id),
            sequence_number=q.sequence_number,
            question_text=q.question_text,
            question_type=q.question_type,
            difficulty=q.difficulty,
            answer_text=q.answer_text,
            score=q.score,
            evaluation=serialise_evaluation(q.evaluation_json) if q.evaluation_json else None,
            time_taken_seconds=q.time_taken_seconds,
            time_expired=q.time_expired,
        )
        question_map[q.id] = detail
        if q.parent_question_id and q.parent_question_id in question_map:
            question_map[q.parent_question_id].follow_ups.append(detail)
        else:
            top_level.append(detail)

    fb = s.feedback
    qa_history = serialise_history(s.graph_state.get("qa_history", [])) if s.graph_state else []

    return InterviewReportResponse(
        session_id=str(s.id),
        role=s.role,
        level=s.level,
        interview_type=s.interview_type,
        total_questions=s.total_questions,
        status=s.status,
        started_at=s.started_at.isoformat(),
        completed_at=s.completed_at.isoformat() if s.completed_at else None,
        total_time_seconds=s.total_time_seconds,
        overall_score=fb.overall_score if fb else None,
        technical_depth_score=fb.technical_depth_score if fb else None,
        communication_score=fb.communication_score if fb else None,
        problem_solving_score=fb.problem_solving_score if fb else None,
        summary_text=fb.summary_text if fb else None,
        strengths=fb.strengths or [] if fb else [],
        improvements=fb.improvements or [] if fb else [],
        questions=top_level,
        qa_history=qa_history,
    )
