"""Routing helpers used by the LangGraph workflow."""

from __future__ import annotations

from .state import InterviewState


def route_after_evaluation(state: InterviewState) -> str:
    """Determine the next node after evaluating an answer."""
    asked = len(state.get("qa_history", []))
    limit = state.get("question_limit", 3)
    return "finish" if asked >= limit else "ask_next"
