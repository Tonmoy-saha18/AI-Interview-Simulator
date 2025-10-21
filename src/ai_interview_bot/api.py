"""FastAPI application exposing the interview workflow."""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from uuid import uuid4

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .graph import build_interview_app
from .state import InterviewConfig, QARecord
from .stream_utils import extract_interrupt_value, get_state_values, iter_event_values


class InterviewStartRequest(BaseModel):
    """Payload for starting a new interview session."""

    role: str = Field(..., description="Target job role, e.g. 'Machine Learning Engineer'.")
    level: str = Field("mid", description="Seniority level, e.g. 'junior', 'mid', 'senior'.")
    questions: int = Field(3, ge=1, le=10, description="Total number of questions to ask.")
    candidate_profile: str = Field(
        "",
        description="Optional candidate profile/resume summary to contextualise the interview.",
    )


class AnswerRequest(BaseModel):
    """Payload for submitting an answer to the current interview question."""

    answer: str = Field(..., min_length=1, description="Candidate response to the current question.")


class EvaluationModel(BaseModel):
    """API representation of the evaluation breakdown."""

    score: int
    reasoning: str = ""
    strengths: List[str] = Field(default_factory=list)
    improvements: List[str] = Field(default_factory=list)
    follow_up: Optional[str] = None


class QARecordModel(BaseModel):
    """API representation of the QA history."""

    question: str
    answer: str
    evaluation: Optional[EvaluationModel] = None


class InterviewStepResponse(BaseModel):
    """Generic response returned after any state transition."""

    session_id: str
    status: str
    question: Optional[str] = None
    question_index: Optional[int] = None
    question_limit: Optional[int] = None
    evaluation: Optional[EvaluationModel] = None
    feedback: Optional[str] = None
    qa_history: List[QARecordModel] = Field(default_factory=list)
    prompt: Optional[str] = None


@dataclass(slots=True)
class InterviewSession:
    """Mutable state wrapper for a running interview."""

    app: Any
    config: InterviewConfig
    graph_config: Dict[str, Any]
    last_question: Optional[str] = None
    finished: bool = False
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

load_dotenv()

app = FastAPI(
    title="AI Interview Simulator API",
    description="HTTP interface for running AI-powered interview simulations.",
    version="0.1.0",
)

allow_origins = os.getenv("AI_INTERVIEW_ALLOW_ORIGINS", "*")
if allow_origins:
    origins = [origin.strip() for origin in allow_origins.split(",") if origin.strip()]
    if origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_methods=["*"],
            allow_headers=["*"],
            allow_credentials=True,
        )


def _serialise_evaluation(data: Optional[Dict[str, Any]]) -> Optional[EvaluationModel]:
    if not data:
        return None
    return EvaluationModel(
        score=int(data.get("score", 0)),
        reasoning=str(data.get("reasoning", "")),
        strengths=list(data.get("strengths") or []),
        improvements=list(data.get("improvements") or []),
        follow_up=data.get("follow_up"),
    )


def _serialise_history(history: List[QARecord]) -> List[QARecordModel]:
    records: List[QARecordModel] = []
    for item in history:
        records.append(
            QARecordModel(
                question=item.get("question", ""),
                answer=item.get("answer", ""),
                evaluation=_serialise_evaluation(item.get("evaluation")),
            )
        )
    return records


def _prepare_response(
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

    return InterviewStepResponse(
        session_id=session_id,
        status=status_value,
        question=question if not session.finished else None,
        question_index=question_index,
        question_limit=question_limit,
        evaluation=_serialise_evaluation(evaluation),
        feedback=feedback,
        qa_history=_serialise_history(qa_history),
        prompt=prompt_value,
    )


async def _drive_session(session_id: str, session: InterviewSession) -> InterviewStepResponse:
    prompt_hint: Optional[str] = None
    async with session.lock:
        if session.finished:
            return _prepare_response(session_id, session, prompt_hint=None)

        for event in session.app.stream(None, config=session.graph_config):
            for payload in iter_event_values(event):
                if "current_question" in payload:
                    session.last_question = payload["current_question"]
            if "__interrupt__" in event:
                prompt_hint = extract_interrupt_value(event.get("__interrupt__"))
                break

        return _prepare_response(session_id, session, prompt_hint=prompt_hint)


@app.post("/interviews", response_model=InterviewStepResponse, status_code=status.HTTP_201_CREATED)
async def start_interview(payload: InterviewStartRequest) -> InterviewStepResponse:
    session = await manager.create_session(payload)
    session_id = session.config.thread_id or ""
    response = await _drive_session(session_id, session)
    return response


@app.post(
    "/interviews/{session_id}/answer",
    response_model=InterviewStepResponse,
)
async def submit_answer(session_id: str, payload: AnswerRequest) -> InterviewStepResponse:
    session = await manager.get_session(session_id)
    async with session.lock:
        if session.finished:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Interview already completed.",
            )
        session.app.update_state(
            session.graph_config,
            {
                "answer": payload.answer.strip(),
            },
        )
    response = await _drive_session(session_id, session)
    return response


@app.get("/interviews/{session_id}", response_model=InterviewStepResponse)
async def get_session_state(session_id: str) -> InterviewStepResponse:
    session = await manager.get_session(session_id)
    return await _drive_session(session_id, session)


@app.delete("/interviews/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def end_session(session_id: str) -> None:
    await manager.remove_session(session_id)
