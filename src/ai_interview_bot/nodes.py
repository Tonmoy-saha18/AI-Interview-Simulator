"""LangGraph node implementations."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict

from langchain_core.runnables import Runnable

from .config import PromptBundle, format_history
from .state import EvaluationBreakdown, InterviewState, QARecord


class QuestionNode:
    """Generates the next interview question with difficulty and time limits."""

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

        # Determine difficulty based on question index and level
        difficulty = self._determine_difficulty(state, question_index)
        
        # Set time limit based on difficulty
        time_limits = {
            "easy": 120,    # 2 minutes
            "medium": 300,  # 5 minutes
            "hard": 600,    # 10 minutes
        }
        time_limit = time_limits.get(difficulty, 300)

        formatted_history = format_history(qa_history)
        prompt_inputs = {
            "level": state.get("level", "mid"),
            "role": state.get("role", "Engineer"),
            "candidate_profile": state.get("candidate_profile", ""),
            "formatted_history": formatted_history,
            "next_index": question_index,
            "difficulty": difficulty,
        }

        question_text = self._runnable.invoke(prompt_inputs)

        # Reset follow-up tracking for new question
        is_follow_up = state.get("is_follow_up", False)
        if not is_follow_up:
            state.update({"follow_up_count": 0})

        state.update(
            {
                "current_question": question_text.strip(),
                "question_index": question_index,
                "question_difficulty": difficulty,
                "question_time_limit": time_limit,
                "answer_start_time": datetime.now().isoformat(),
                "time_expired": False,
                "is_follow_up": False,  # Reset for new questions
            }
        )
        return state

    def _determine_difficulty(self, state: InterviewState, question_index: int) -> str:
        """Determine question difficulty based on index and level."""
        level = state.get("level", "mid").lower()
        question_limit = state.get("question_limit", 3)
        
        # Progressive difficulty: earlier questions easier, later questions harder
        if question_limit <= 3:
            # For 3 questions: easy, medium, hard
            if question_index == 1:
                return "easy"
            elif question_index == 2:
                return "medium"
            else:
                return "hard"
        else:
            # For more questions, distribute difficulty
            if question_index <= question_limit // 3:
                return "easy"
            elif question_index <= 2 * question_limit // 3:
                return "medium"
            else:
                return "hard"


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

        # Calculate time taken
        time_taken = None
        time_expired = state.get("time_expired", False)
        answer_start_time_str = state.get("answer_start_time")
        
        if answer_start_time_str:
            try:
                start_time = datetime.fromisoformat(answer_start_time_str)
                elapsed = datetime.now() - start_time
                time_taken = int(elapsed.total_seconds())
                
                # Check if time limit was exceeded
                time_limit = state.get("question_time_limit", 300)
                if time_taken > time_limit:
                    time_expired = True
            except (ValueError, TypeError):
                pass

        prompt_inputs = {
            "role": state.get("role", "Engineer"),
            "candidate_profile": state.get("candidate_profile", ""),
            "question": question,
            "answer": answer,
            "difficulty": state.get("question_difficulty", "medium"),
            "time_taken": time_taken if time_taken else "unknown",
            "time_expired": time_expired,
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

        # Update total time elapsed
        total_time = state.get("total_time_elapsed", 0)
        if time_taken:
            total_time += time_taken

        state.update(
            {
                "evaluation": evaluation,
                "qa_history": history,
                "answer": "",
                "answer_time_taken": time_taken,
                "total_time_elapsed": total_time,
                "time_expired": time_expired,
            }
        )
        return state


class FollowUpQuestionNode:
    """Generates follow-up questions when an answer needs clarification."""

    def __init__(self, runnable: Runnable, prompts: PromptBundle) -> None:
        self._runnable = runnable
        self._prompts = prompts

    def __call__(self, state: InterviewState) -> InterviewState:
        evaluation = state.get("evaluation", {})
        follow_up_hint = evaluation.get("follow_up", "")
        
        # Get the original question and answer from history
        qa_history = state.get("qa_history", [])
        if not qa_history:
            # No history, can't generate follow-up
            return state
        
        last_record = qa_history[-1]
        original_question = last_record.get("question", "")
        original_answer = last_record.get("answer", "")
        
        if not follow_up_hint:
            # No follow-up hint, generate a general clarification question
            follow_up_hint = "The answer could use more detail or clarification."

        prompt_inputs = {
            "original_question": original_question,
            "original_answer": original_answer,
            "evaluation_reasoning": evaluation.get("reasoning", ""),
            "follow_up_hint": follow_up_hint,
            "role": state.get("role", "Engineer"),
            "difficulty": state.get("question_difficulty", "medium"),
        }

        # Build chain: prompt -> LLM -> parser (same pattern as QuestionNode)
        from langchain_core.output_parsers import StrOutputParser
        follow_up_chain = self._prompts.follow_up | self._runnable | StrOutputParser()
        follow_up_question = follow_up_chain.invoke(prompt_inputs)

        # Update follow-up count
        follow_up_count = state.get("follow_up_count", 0) + 1
        
        # Set time limit for follow-up (shorter than original)
        time_limits = {
            "easy": 60,    # 1 minute
            "medium": 120,  # 2 minutes
            "hard": 180,    # 3 minutes
        }
        difficulty = state.get("question_difficulty", "medium")
        time_limit = time_limits.get(difficulty, 120)

        state.update({
            "current_question": follow_up_question.strip(),
            "is_follow_up": True,
            "follow_up_count": follow_up_count,
            "question_time_limit": time_limit,
            "answer_start_time": datetime.now().isoformat(),
            "time_expired": False,
        })
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
    """Parse evaluation with multi-dimensional scores."""
    if isinstance(raw_response, dict):
        data = raw_response
    else:
        text = str(raw_response).strip()
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            # Fall back to heuristic parsing.
            data = {
                "overall_score": 3,
                "technical_depth": 3,
                "communication": 3,
                "problem_solving": 3,
                "reasoning": text,
                "strengths": [],
                "improvements": []
            }

    # Extract dimension scores
    technical_depth = _clamp_score(data.get("technical_depth", data.get("score", 3)))
    communication = _clamp_score(data.get("communication", data.get("score", 3)))
    problem_solving = _clamp_score(data.get("problem_solving", data.get("score", 3)))
    
    # Calculate overall score (weighted average)
    # Technical depth and problem solving are more important
    weights = {
        "technical_depth": 0.4,
        "communication": 0.2,
        "problem_solving": 0.4,
    }
    overall_score = int(round(
        technical_depth * weights["technical_depth"] +
        communication * weights["communication"] +
        problem_solving * weights["problem_solving"]
    ))

    evaluation: EvaluationBreakdown = {
        "overall_score": overall_score,
        "technical_depth": technical_depth,
        "communication": communication,
        "problem_solving": problem_solving,
        "reasoning": data.get("reasoning", ""),
        "strengths": data.get("strengths", []),
        "improvements": data.get("improvements", []),
    }

    # Legacy support
    evaluation["score"] = overall_score

    follow_up = data.get("follow_up")
    if follow_up:
        evaluation["follow_up"] = str(follow_up)
    return evaluation


def _clamp_score(score: Any) -> int:
    """Clamp score to 1-5 range."""
    try:
        score = int(score)
        return max(1, min(score, 5))
    except (ValueError, TypeError):
        return 3
