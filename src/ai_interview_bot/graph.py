"""LangGraph workflow definition for the interview bot."""

from __future__ import annotations

from typing import Optional

from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import Runnable
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from .config import PromptBundle, build_default_prompts
from .nodes import EvaluationNode, FeedbackNode, QuestionNode
from .routing import route_after_evaluation
from .state import InterviewState


def _build_question_chain(llm: Runnable, prompts: PromptBundle) -> Runnable:
    return prompts.question | llm | StrOutputParser()


def _build_evaluation_chain(llm: Runnable, prompts: PromptBundle) -> Runnable:
    return prompts.evaluation | llm | StrOutputParser()


def _build_feedback_chain(llm: Runnable, prompts: PromptBundle) -> Runnable:
    return prompts.feedback | llm | StrOutputParser()


def build_interview_app(
    llm: Optional[Runnable] = None,
    prompts: Optional[PromptBundle] = None,
    interrupt_after_question: bool = True,
) -> CompiledStateGraph:
    """Create and compile the LangGraph application.

    Parameters
    ----------
    llm:
        LangChain-compatible chat runnable. Defaults to `ChatOpenAI` (gpt-4o-mini).
    prompts:
        Optional custom prompt templates.
    interrupt_after_question:
        When true, the compiled graph interrupts after the question node, allowing
        external systems (CLI, web UI) to gather the candidate's answer before
        resuming execution.
    """

    prompts = prompts or build_default_prompts()
    llm = llm or ChatOpenAI(model="gpt-4o-mini", temperature=0.4)

    question_node = QuestionNode(_build_question_chain(llm, prompts), prompts)
    evaluation_node = EvaluationNode(_build_evaluation_chain(llm, prompts))
    feedback_node = FeedbackNode(_build_feedback_chain(llm, prompts))

    graph = StateGraph(InterviewState)
    graph.add_node("generate_question", question_node)
    graph.add_node("evaluate_answer", evaluation_node)
    graph.add_node("generate_feedback", feedback_node)

    graph.set_entry_point("generate_question")
    graph.add_edge("generate_question", "evaluate_answer")
    graph.add_conditional_edges(
        "evaluate_answer",
        route_after_evaluation,
        {
            "ask_next": "generate_question",
            "finish": "generate_feedback",
        },
    )
    graph.add_edge("generate_feedback", END)

    checkpointer = MemorySaver()
    if interrupt_after_question:
        app = graph.compile(
            checkpointer=checkpointer,
            interrupt_after=["generate_question"],
        )
    else:
        app = graph.compile(checkpointer=checkpointer)
    return app
