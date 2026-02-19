"""Utilities for working with LangGraph stream output."""

from __future__ import annotations

from typing import Any, Dict, Iterable, Mapping, Optional


def iter_event_values(event: Mapping[str, Any]) -> Iterable[Dict[str, Any]]:
    """Yield nested dict payloads from a LangGraph stream event."""
    if not isinstance(event, Mapping):
        return []
    for value in event.values():
        if isinstance(value, Mapping):
            yield dict(value)


def get_state_values(app: Any, graph_config: Dict[str, Any]) -> Dict[str, Any]:
    """Safely read the current state values from the compiled graph."""
    snapshot = getattr(app, "get_state", None)
    if not callable(snapshot):
        return {}
    try:
        current_state = snapshot(graph_config)
    except Exception:
        return {}

    if isinstance(current_state, dict):
        values = current_state.get("values", {}) or {}
    else:
        values = getattr(current_state, "values", {}) or {}
    return dict(values)


def extract_interrupt_value(payload: Any) -> Optional[Any]:
    """Extract the first meaningful interrupt payload from nested data."""
    if payload is None:
        return None
    if isinstance(payload, (list, tuple)):
        for item in payload:
            extracted = extract_interrupt_value(item)
            if extracted is not None:
                return extracted
        return None
    return getattr(payload, "value", payload)
