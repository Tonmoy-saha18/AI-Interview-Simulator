"""Shared state definitions for the interview LangGraph."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, TypedDict


class EvaluationBreakdown(TypedDict, total=False):
    """Structured evaluation returned by the evaluation node."""

    score: int  # Legacy field, kept for backward compatibility
    overall_score: int  # Weighted average of dimension scores
    technical_depth: int  # 1-5
    communication: int  # 1-5
    problem_solving: int  # 1-5
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
    # Time tracking fields
    question_difficulty: str  # "easy", "medium", "hard"
    question_time_limit: int  # seconds based on difficulty
    answer_start_time: Optional[str]  # ISO timestamp
    answer_time_taken: Optional[int]  # seconds
    total_time_elapsed: int  # cumulative seconds
    time_expired: bool  # True if time limit was exceeded
    # Follow-up question tracking
    is_follow_up: bool  # True if current question is a follow-up
    follow_up_count: int  # Number of follow-ups asked for current question
    max_follow_ups_per_question: int  # Maximum follow-ups allowed (default: 1)


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
            "total_time_elapsed": 0,
            "is_follow_up": False,
            "follow_up_count": 0,
            "max_follow_ups_per_question": 1,
            "time_expired": False,
        }
        state.update(self.extra_context)
        return state
