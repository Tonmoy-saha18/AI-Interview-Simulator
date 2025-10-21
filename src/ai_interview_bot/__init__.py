"""Interview bot built with LangGraph nodes for question generation, evaluation, and feedback."""

from __future__ import annotations

from importlib import import_module
from typing import Any

__all__ = ["build_interview_app"]


def build_interview_app(*args: Any, **kwargs: Any) -> Any:
    """Lazy import wrapper to avoid requiring heavy dependencies at package import time."""
    module = import_module(".graph", __name__)
    return module.build_interview_app(*args, **kwargs)
