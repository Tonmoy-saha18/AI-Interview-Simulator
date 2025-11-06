"""Configuration helpers and prompt templates for the interview bot."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from langchain_core.prompts import ChatPromptTemplate


@dataclass(frozen=True)
class PromptBundle:
    """Container for all prompt templates used by the nodes."""

    question: ChatPromptTemplate
    evaluation: ChatPromptTemplate
    follow_up: ChatPromptTemplate
    feedback: ChatPromptTemplate


def build_default_prompts() -> PromptBundle:
    """Create the default set of prompt templates."""

    question_prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                (
                    "You are an interviewer creating rigorous {level} level {role} interview questions.\n"
                    "Adapt each question using the candidate's profile and previous QA pairs.\n"
                    "Ask one question at a time, ensuring variety across topics.\n"
                    "The question difficulty is: {difficulty}\n"
                    "Respond with the question only."
                ),
            ),
            (
                "human",
                (
                    "Candidate profile:\n{candidate_profile}\n\n"
                    "Previous discussion:\n{formatted_history}\n\n"
                    "Next question number: {next_index}\n"
                    "Difficulty level: {difficulty}\n"
                    "Compose the next question."
                ),
            ),
        ]
    )

    evaluation_prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                (
                    "You are an expert interviewer assessing responses for {role} candidates.\n"
                    "Evaluate the answer across multiple dimensions on a 1-5 scale:\n"
                    "1. technical_depth: Understanding of technical concepts, accuracy, depth\n"
                    "2. communication: Clarity, structure, articulation, ability to explain\n"
                    "3. problem_solving: Approach, reasoning, solution quality, creativity\n\n"
                    "Consider the question difficulty ({difficulty}) when scoring.\n"
                    "If time_expired is True, note that the candidate ran out of time.\n\n"
                    "Return valid JSON with keys:\n"
                    "- overall_score (int 0-5): Weighted average (technical_depth: 40%, communication: 20%, problem_solving: 40%)\n"
                    "- technical_depth (int 0-5)\n"
                    "- communication (int 0-5)\n"
                    "- problem_solving (int 0-5)\n"
                    "- reasoning (str): Detailed assessment\n"
                    "- strengths (list[str]): What they did well\n"
                    "- improvements (list[str]): Areas to improve\n"
                    "- follow_up (str, optional): Suggested follow-up question if score < 3 or answer needs clarification"
                ),
            ),
            (
                "human",
                (
                    "Question:\n{question}\n\n"
                    "Answer:\n{answer}\n\n"
                    "Time taken: {time_taken} seconds\n"
                    "Time expired: {time_expired}\n\n"
                    "Candidate profile:\n{candidate_profile}"
                ),
            ),
        ]
    )

    follow_up_prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                (
                    "You are an interviewer asking a follow-up question to clarify or deepen the candidate's response.\n"
                    "Based on the evaluation, ask a specific follow-up question that will help assess the candidate better.\n"
                    "The follow-up question should be related to the original question but probe deeper.\n"
                    "Keep it concise and focused. Respond with the question only."
                ),
            ),
            (
                "human",
                (
                    "Original Question:\n{original_question}\n\n"
                    "Candidate's Answer:\n{original_answer}\n\n"
                    "Evaluation Feedback:\n{evaluation_reasoning}\n\n"
                    "Follow-up Hint:\n{follow_up_hint}\n\n"
                    "Role: {role}\n"
                    "Difficulty: {difficulty}\n\n"
                    "Generate a follow-up question that will help clarify or assess the candidate's understanding better."
                ),
            ),
        ]
    )

    feedback_prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                (
                    "You are a coaching assistant preparing a concise interview debrief.\n"
                    "Summarise the candidate's performance, referencing their strengths, areas to improve, "
                    "and actionable next steps.\n"
                    "Keep the tone constructive."
                ),
            ),
            (
                "human",
                (
                    "Role: {role}\n"
                    "Level: {level}\n"
                    "Question/Answer/Evaluation history:\n{formatted_history}\n"
                    "Provide a final feedback summary."
                ),
            ),
        ]
    )

    return PromptBundle(
        question=question_prompt,
        evaluation=evaluation_prompt,
        follow_up=follow_up_prompt,
        feedback=feedback_prompt,
    )


from typing import Iterable, Mapping

from .state import QARecord


def format_history(history: Iterable[QARecord]) -> str:
    """Format QA history for prompt injection."""
    if not history:
        return "No questions asked yet."

    lines = []
    for idx, record in enumerate(history, start=1):
        evaluation = record.get("evaluation", {})
        score = evaluation.get("overall_score") or evaluation.get("score", "N/A")
        
        # Include dimension scores if available
        dim_scores = []
        if evaluation.get("technical_depth"):
            dim_scores.append(f"Technical: {evaluation['technical_depth']}/5")
        if evaluation.get("communication"):
            dim_scores.append(f"Communication: {evaluation['communication']}/5")
        if evaluation.get("problem_solving"):
            dim_scores.append(f"Problem Solving: {evaluation['problem_solving']}/5")
        
        score_line = f"[Score] {score}/5"
        if dim_scores:
            score_line += f" ({', '.join(dim_scores)})"
        score_line += f" - {evaluation.get('reasoning', '')}"
        
        lines.append(
            f"[Question {idx}] {record['question']}\n"
            f"[Answer] {record['answer']}\n"
            f"{score_line}"
        )
    return "\n\n".join(lines)
