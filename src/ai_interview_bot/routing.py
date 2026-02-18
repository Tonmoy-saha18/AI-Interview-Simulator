"""Routing helpers used by the LangGraph workflow."""

from __future__ import annotations

from .state import InterviewState


def route_after_evaluation(state: InterviewState) -> str:
    """Determine the next node after evaluating an answer.
    
    Returns:
        "finish" - if question limit reached
        "ask_follow_up" - if follow-up is needed (low score and not exceeded max follow-ups)
        "ask_next" - if more questions needed
    
    Note: Only counts main questions (not follow-ups) when checking question limit,
    since follow-ups are nested under their parent questions.
    """
    # Count only main questions (follow-ups are nested, not in qa_history)
    asked = len(state.get("qa_history", []))
    limit = state.get("question_limit", 3)
    
    # Check if we've reached the question limit
    # Note: We only count main questions, not follow-ups
    if asked >= limit:
        return "finish"
    
    # Check if follow-up is needed
    evaluation = state.get("evaluation", {})
    overall_score = evaluation.get("overall_score") or evaluation.get("score", 5)
    follow_up_hint = evaluation.get("follow_up", "")
    
    # Ask follow-up if:
    # 1. Score is low (< 3) OR follow_up hint is provided
    # 2. We haven't exceeded max follow-ups for this question
    # 3. We're not already in a follow-up (to avoid infinite loops)
    is_follow_up = state.get("is_follow_up", False)
    follow_up_count = state.get("follow_up_count", 0)
    max_follow_ups = state.get("max_follow_ups_per_question", 1)
    
    needs_follow_up = (
        (overall_score < 3 or follow_up_hint) 
        and not is_follow_up 
        and follow_up_count < max_follow_ups
    )
    
    if needs_follow_up:
        return "ask_follow_up"
    
    # Otherwise, move to next question
    return "ask_next"


def route_after_follow_up(state: InterviewState) -> str:
    """Determine routing after follow-up question is answered.
    Always goes back to evaluation."""
    return "evaluate_answer"
