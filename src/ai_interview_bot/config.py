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
                    "Respond with the question only."
                ),
            ),
            (
                "human",
                (
                    "Candidate profile:\n{candidate_profile}\n\n"
                    "Previous discussion:\n{formatted_history}\n\n"
                    "Next question number: {next_index}\n"
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
                    "Score each answer on a 1-5 scale and provide structured feedback.\n"
                    "Return valid JSON with the keys: score (int 1-5), reasoning (str), strengths (list[str]), "
                    "improvements (list[str]), follow_up (optional str)."
                ),
            ),
            (
                "human",
                (
                    "Question:\n{question}\n\n"
                    "Answer:\n{answer}\n"
                    "Candidate profile:\n{candidate_profile}"
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
        lines.append(
            f"[Question {idx}] {record['question']}\n"
            f"[Answer] {record['answer']}\n"
            f"[Score] {evaluation.get('score', 'N/A')} - {evaluation.get('reasoning', '')}"
        )
    return "\n\n".join(lines)
