"""Command-line interface for running the interview bot."""

from __future__ import annotations

import argparse
import os
import sys
import textwrap
from typing import Iterable, Optional
from uuid import uuid4

from dotenv import load_dotenv
from langgraph.errors import GraphInterrupt

from .graph import build_interview_app
from .state import InterviewConfig
from .stream_utils import extract_interrupt_value, get_state_values, iter_event_values


def run_cli(argv: Iterable[str] | None = None) -> int:
    """Entry point invoked from ``python -m ai_interview_bot.cli``."""

    parser = argparse.ArgumentParser(
        prog="ai-interview-bot",
        description="Interactive interview simulator powered by LangGraph.",
    )
    parser.add_argument("--role", required=True, help="Target job role, e.g. 'Machine Learning Engineer'.")
    parser.add_argument("--level", default="mid", help="Seniority level, e.g. 'junior', 'mid', 'senior'.")
    parser.add_argument(
        "--questions",
        type=int,
        default=3,
        help="Number of interview questions to ask before generating feedback.",
    )
    parser.add_argument(
        "--profile",
        default="",
        help="Candidate profile or summary text that helps tailor the questions.",
    )

    args = parser.parse_args(list(argv) if argv is not None else None)

    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("OPENAI_API_KEY is not set. Please configure your environment first.", file=sys.stderr)
        return 1

    config = InterviewConfig(
        candidate_profile=args.profile,
        role=args.role,
        level=args.level,
        question_limit=args.questions,
        thread_id=str(uuid4()),
    )

    app = build_interview_app()
    graph_config = {"configurable": {"thread_id": config.thread_id}}
    app.update_state(graph_config, config.initial_state())

    banner = textwrap.dedent(
        f"""
        [Interview] Starting {args.level.title()} {args.role} interview.
        The bot will ask {args.questions} question(s) and then deliver feedback.
        """
    ).strip()
    print(banner)

    last_question: Optional[str] = None

    while True:
        interrupted = False
        try:
            for event in app.stream(None, config=graph_config):
                for payload in iter_event_values(event):
                    if "current_question" in payload:
                        last_question = payload["current_question"]
                        question_number = payload.get(
                            "question_index",
                            len(payload.get("qa_history", [])) + 1,
                        )
                        print(f"\nQuestion {question_number}: {payload['current_question']}")
                    if "evaluation" in payload:
                        evaluation = payload["evaluation"]
                        print("-" * 60)
                        print(f"Score: {evaluation.get('score', 'N/A')}/5")
                        if evaluation.get("strengths"):
                            print("Strengths:")
                            for item in evaluation["strengths"]:
                                print(f"  - {item}")
                        if evaluation.get("improvements"):
                            print("Areas to improve:")
                            for item in evaluation["improvements"]:
                                print(f"  - {item}")
                        if evaluation.get("follow_up"):
                            print(f"Suggested follow-up: {evaluation['follow_up']}")
                    if "feedback" in payload:
                        print("\nFinal feedback:\n")
                        print(payload["feedback"])
                        print("\nInterview complete.")
                        return 0
                if "__interrupt__" in event:
                    interrupted = True
                    state_values = get_state_values(app, graph_config)
                    question_text = state_values.get("current_question") or last_question
                    prompt_hint = extract_interrupt_value(event.get("__interrupt__"))
                    prompt_text = (
                        str(prompt_hint).strip()
                        if isinstance(prompt_hint, str) and prompt_hint.strip()
                        else (question_text or "Please provide your answer:")
                    )
                    answer = input(f"\n{prompt_text}\n> ").strip()
                    app.update_state(
                        graph_config,
                        {
                            "answer": answer,
                        },
                    )
                    break
            # Stream finished without reaching feedback.
            if not interrupted:
                return 0
        except GraphInterrupt as interruption:
            interrupted = True
            state_values = get_state_values(app, graph_config)
            question_text = state_values.get("current_question") or last_question
            prompt_hint = extract_interrupt_value(interruption.args if interruption.args else None)
            prompt_text = (
                str(prompt_hint).strip()
                if isinstance(prompt_hint, str) and prompt_hint.strip()
                else (question_text or "Please provide your answer:")
            )
            answer = input(f"\n{prompt_text}\n> ").strip()
            app.update_state(
                graph_config,
                {
                    "answer": answer,
                },
            )
        if interrupted:
            continue
        return 0


if __name__ == "__main__":
    raise SystemExit(run_cli())
