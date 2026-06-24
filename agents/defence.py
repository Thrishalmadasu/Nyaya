"""Defence Advocate agent — argues against liability."""
from __future__ import annotations

from agents.advocate import run_advocate
from agents.prompts import DEFENCE_SYSTEM
from graph.state import GraphState


def defence_node(state: GraphState) -> dict:
    """LangGraph node: Defence advocate argues against liability."""
    return run_advocate(
        state,
        side="defence",
        system_prompt=DEFENCE_SYSTEM,
        next_phase="judge",
    )
