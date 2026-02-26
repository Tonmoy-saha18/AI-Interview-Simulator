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


class QARecord(TypedDict, total=False):
    """Single question/answer/evaluation triple stored in memory."""

    question: str
    answer: str
    evaluation: EvaluationBreakdown
    follow_ups: List["QARecord"]


class ComplexityAnalysis(TypedDict, total=False):
    """Result of LLM-based Big-O analysis."""

    estimated_time_complexity: str
    estimated_space_complexity: str
    reasoning: str
    meets_expected: bool


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
    question_difficulty: str
    question_time_limit: int
    answer_start_time: Optional[str]
    answer_time_taken: Optional[int]
    total_time_elapsed: int
    time_expired: bool
    is_follow_up: bool
    follow_up_count: int
    max_follow_ups_per_question: int

    # Coding question fields (Phase 2)
    question_type: str  # "behavioral" | "coding"
    current_problem_id: Optional[str]
    current_problem_data: Optional[Dict[str, Any]]
    code_submission: Optional[str]
    code_language: Optional[str]
    code_results: Optional[Dict[str, Any]]
    complexity_analysis: Optional[ComplexityAnalysis]
    hints_used: int


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
