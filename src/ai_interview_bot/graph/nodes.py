"""LangGraph node implementations."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict

from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import Runnable

from .prompts import PromptBundle, format_history
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
            return state

        difficulty = self._determine_difficulty(state, question_index)

        time_limits = {
            "easy": 120,
            "medium": 300,
            "hard": 600,
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
                "is_follow_up": False,
            }
        )
        return state

    def _determine_difficulty(self, state: InterviewState, question_index: int) -> str:
        question_limit = state.get("question_limit", 3)

        if question_limit <= 3:
            if question_index == 1:
                return "easy"
            elif question_index == 2:
                return "medium"
            else:
                return "hard"
        else:
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

        time_taken = None
        time_expired = state.get("time_expired", False)
        answer_start_time_str = state.get("answer_start_time")

        if answer_start_time_str:
            try:
                start_time = datetime.fromisoformat(answer_start_time_str)
                elapsed = datetime.now() - start_time
                time_taken = int(elapsed.total_seconds())

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
        is_follow_up = state.get("is_follow_up", False)

        if is_follow_up and history:
            last_record = history[-1]
            if "follow_ups" not in last_record:
                last_record["follow_ups"] = []
            last_record["follow_ups"].append(qa_record)
        else:
            history.append(qa_record)

        total_time = state.get("total_time_elapsed", 0)
        if time_taken:
            total_time += time_taken

        update_data: Dict[str, Any] = {
            "evaluation": evaluation,
            "qa_history": history,
            "answer": "",
            "answer_time_taken": time_taken,
            "total_time_elapsed": total_time,
            "time_expired": time_expired,
        }

        if is_follow_up:
            update_data["is_follow_up"] = False

        state.update(update_data)
        return state


class FollowUpQuestionNode:
    """Generates follow-up questions when an answer needs clarification."""

    def __init__(self, runnable: Runnable, prompts: PromptBundle) -> None:
        self._runnable = runnable
        self._prompts = prompts

    def __call__(self, state: InterviewState) -> InterviewState:
        evaluation = state.get("evaluation", {})
        follow_up_hint = evaluation.get("follow_up", "")

        qa_history = state.get("qa_history", [])
        if not qa_history:
            return state

        last_record = qa_history[-1]
        original_question = last_record.get("question", "")
        original_answer = last_record.get("answer", "")

        if not follow_up_hint:
            follow_up_hint = "The answer could use more detail or clarification."

        prompt_inputs = {
            "original_question": original_question,
            "original_answer": original_answer,
            "evaluation_reasoning": evaluation.get("reasoning", ""),
            "follow_up_hint": follow_up_hint,
            "role": state.get("role", "Engineer"),
            "difficulty": state.get("question_difficulty", "medium"),
        }

        follow_up_chain = self._prompts.follow_up | self._runnable | StrOutputParser()
        follow_up_question = follow_up_chain.invoke(prompt_inputs)

        follow_up_count = state.get("follow_up_count", 0) + 1

        time_limits = {
            "easy": 60,
            "medium": 120,
            "hard": 180,
        }
        difficulty = state.get("question_difficulty", "medium")
        time_limit = time_limits.get(difficulty, 120)

        state.update(
            {
                "current_question": follow_up_question.strip(),
                "is_follow_up": True,
                "follow_up_count": follow_up_count,
                "question_time_limit": time_limit,
                "answer_start_time": datetime.now().isoformat(),
                "time_expired": False,
            }
        )
        return state


class ComplexityAnalysisNode:
    """Performs LLM-based Big-O analysis on submitted code."""

    def __init__(self, runnable: Runnable) -> None:
        self._runnable = runnable

    def __call__(self, state: InterviewState) -> InterviewState:
        code = state.get("code_submission")
        problem_data = state.get("current_problem_data")
        code_results = state.get("code_results")

        if not code or not problem_data:
            return state

        prompt_inputs = {
            "problem_title": problem_data.get("title", "Unknown"),
            "expected_time": problem_data.get("expected_time_complexity", "unknown"),
            "expected_space": problem_data.get("expected_space_complexity", "unknown"),
            "language": state.get("code_language", "unknown"),
            "code": code,
        }

        raw_response = self._runnable.invoke(prompt_inputs)
        analysis = _parse_complexity(raw_response)

        # Composite score: correctness 70% + complexity match 30%
        correctness_score = 0
        if code_results:
            total = code_results.get("total_test_cases", 1)
            passed = code_results.get("passed_count", 0)
            correctness_score = (passed / total) * 100 if total else 0

        complexity_score = 100 if analysis.get("meets_expected", False) else 50
        composite = correctness_score * 0.7 + complexity_score * 0.3

        eval_data = state.get("evaluation", {})
        eval_data["code_correctness_score"] = round(correctness_score, 1)
        eval_data["complexity_score"] = round(complexity_score, 1)
        eval_data["composite_score"] = round(composite, 1)

        state.update({
            "complexity_analysis": analysis,
            "evaluation": eval_data,
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
            data = {
                "overall_score": 3,
                "technical_depth": 3,
                "communication": 3,
                "problem_solving": 3,
                "reasoning": text,
                "strengths": [],
                "improvements": [],
            }

    technical_depth = _clamp_score(data.get("technical_depth", data.get("score", 3)))
    communication = _clamp_score(data.get("communication", data.get("score", 3)))
    problem_solving = _clamp_score(data.get("problem_solving", data.get("score", 3)))

    weights = {
        "technical_depth": 0.4,
        "communication": 0.2,
        "problem_solving": 0.4,
    }
    overall_score = int(
        round(
            technical_depth * weights["technical_depth"]
            + communication * weights["communication"]
            + problem_solving * weights["problem_solving"]
        )
    )

    evaluation: EvaluationBreakdown = {
        "overall_score": overall_score,
        "technical_depth": technical_depth,
        "communication": communication,
        "problem_solving": problem_solving,
        "reasoning": data.get("reasoning", ""),
        "strengths": data.get("strengths", []),
        "improvements": data.get("improvements", []),
    }

    evaluation["score"] = overall_score

    follow_up = data.get("follow_up")
    if follow_up:
        evaluation["follow_up"] = str(follow_up)
    return evaluation


def _parse_complexity(raw_response: Any) -> Dict[str, Any]:
    """Parse complexity analysis response from LLM."""
    if isinstance(raw_response, dict):
        return raw_response

    text = str(raw_response).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {
            "estimated_time_complexity": "unknown",
            "estimated_space_complexity": "unknown",
            "reasoning": text,
            "meets_expected": False,
        }


def _clamp_score(score: Any) -> int:
    """Clamp score to 1-5 range."""
    try:
        score = int(score)
        return max(1, min(score, 5))
    except (ValueError, TypeError):
        return 3
