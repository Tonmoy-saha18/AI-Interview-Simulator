"""LangGraph node implementations."""

from __future__ import annotations

import json
from typing import Any, Dict

from langchain_core.runnables import Runnable

from .config import PromptBundle, format_history
from .state import EvaluationBreakdown, InterviewState, QARecord


class QuestionNode:
    """Generates the next interview question."""

    def __init__(self, runnable: Runnable, prompts: PromptBundle) -> None:
        self._runnable = runnable
        self._prompts = prompts

    def __call__(self, state: InterviewState) -> InterviewState:
        qa_history = state.get("qa_history", [])
        question_index = state.get("question_index", 0) + 1
        question_limit = state.get("question_limit", 3)

        if question_index > question_limit:
            # Nothing to do, we already hit the limit.
            return state

        formatted_history = format_history(qa_history)
        prompt_inputs = {
            "level": state.get("level", "mid"),
            "role": state.get("role", "Engineer"),
            "candidate_profile": state.get("candidate_profile", ""),
            "formatted_history": formatted_history,
            "next_index": question_index,
        }

        question_text = self._runnable.invoke(prompt_inputs)

        state.update(
            {
                "current_question": question_text.strip(),
                "question_index": question_index,
            }
        )
        return state


class EvaluationNode:
    """Evaluates the candidate's answer and stores the breakdown."""

    def __init__(self, runnable: Runnable) -> None:
        self._runnable = runnable

    def __call__(self, state: InterviewState) -> InterviewState:
        answer = state.get("answer")
        question = state.get("current_question")
        if not question:
            raise ValueError("Cannot evaluate without a current question.")
        if not answer:
            raise ValueError("Cannot evaluate without an answer.")

        prompt_inputs = {
            "role": state.get("role", "Engineer"),
            "candidate_profile": state.get("candidate_profile", ""),
            "question": question,
            "answer": answer,
        }

        raw_response = self._runnable.invoke(prompt_inputs)
        evaluation = _parse_evaluation(raw_response)

        qa_record: QARecord = {
            "question": question,
            "answer": answer,
            "evaluation": evaluation,
        }

        history = state.get("qa_history", [])
        history.append(qa_record)

        state.update(
            {
                "evaluation": evaluation,
                "qa_history": history,
                "answer": "",
            }
        )
        return state


class FeedbackNode:
    """Produces the final interview feedback summary."""

    def __init__(self, runnable: Runnable) -> None:
        self._runnable = runnable

    def __call__(self, state: InterviewState) -> InterviewState:
        history = state.get("qa_history", [])
        formatted_history = format_history(history)
        prompt_inputs = {
            "role": state.get("role", "Engineer"),
            "level": state.get("level", "mid"),
            "formatted_history": formatted_history,
        }
        feedback_text = self._runnable.invoke(prompt_inputs)
        state.update({"feedback": feedback_text.strip()})
        return state


def _parse_evaluation(raw_response: Any) -> EvaluationBreakdown:
    """Attempt to coerce the LLM response into the expected JSON structure."""
    if isinstance(raw_response, dict):
        data = raw_response
    else:
        text = str(raw_response).strip()
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            # Fall back to heuristic parsing.
            data = {"score": 3, "reasoning": text, "strengths": [], "improvements": []}

    score = int(data.get("score", 3))
    score = max(1, min(score, 5))

    evaluation: EvaluationBreakdown = {
        "score": score,
        "reasoning": data.get("reasoning", ""),
        "strengths": data.get("strengths", []),
        "improvements": data.get("improvements", []),
    }

    follow_up = data.get("follow_up")
    if follow_up:
        evaluation["follow_up"] = str(follow_up)
    return evaluation
