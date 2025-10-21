"""Shared state definitions for the interview LangGraph."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, TypedDict


class EvaluationBreakdown(TypedDict, total=False):
    """Structured evaluation returned by the evaluation node."""

    score: int
    reasoning: str
    strengths: List[str]
    improvements: List[str]
    follow_up: Optional[str]


class QARecord(TypedDict):
    """Single question/answer/evaluation triple stored in memory."""

    question: str
    answer: str
    evaluation: EvaluationBreakdown


class InterviewState(TypedDict, total=False):
    """State passed between LangGraph nodes."""

    candidate_profile: str
    role: str
    level: str
    current_question: str
    question_index: int
    question_limit: int
    answer: str
    evaluation: EvaluationBreakdown
    qa_history: List[QARecord]
    feedback: str


@dataclass(slots=True)
class InterviewConfig:
    """Runtime configuration for the interview workflow."""

    candidate_profile: str
    role: str
    level: str
    question_limit: int = 3
    thread_id: Optional[str] = None
    extra_context: Dict[str, Any] = field(default_factory=dict)

    def initial_state(self) -> InterviewState:
        """Create the initial state dictionary for the LangGraph app."""
        state: InterviewState = {
            "candidate_profile": self.candidate_profile,
            "role": self.role,
            "level": self.level,
            "question_limit": self.question_limit,
            "question_index": 0,
            "qa_history": [],
        }
        state.update(self.extra_context)
        return state
