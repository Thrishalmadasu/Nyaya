"""Prosecution Advocate agent — argues for liability."""
from __future__ import annotations

from agents.advocate import run_advocate
from agents.prompts import PROSECUTION_SYSTEM
from graph.state import GraphState


def prosecution_node(state: GraphState) -> dict:
    """LangGraph node: Prosecution advocate argues for liability."""
    return run_advocate(
        state,
        side="prosecution",
        system_prompt=PROSECUTION_SYSTEM,
        next_phase="argue",
    )
