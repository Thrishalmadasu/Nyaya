"""Build and compile the AI Moot Court LangGraph StateGraph."""
from __future__ import annotations

from langgraph.graph import END, START, StateGraph
from langgraph.checkpoint.memory import MemorySaver

from graph.state import GraphState
from graph.edges import auditor_routing, hitl_routing, judge_routing


def _hitl_node(state: GraphState) -> dict:
    """Human-in-the-loop gate — uses LangGraph interrupt so the graph suspends.

    In interactive mode (CLI), the graph is resumed by the runner after the
    human types 'approve' or 'reject'.
    In non-interactive mode (eval), hitl_approved is pre-set in the state.
    """
    from langgraph.types import interrupt

    verdict_draft = state.get("verdict")
    audit = state.get("audit_result", {})

    prompt_text = (
        "\n" + "=" * 60 + "\n"
        "⚖️  HUMAN REVIEW REQUIRED\n"
        "=" * 60 + "\n"
        f"Audit passed: {state.get('audit_passed')}\n"
        f"Audit notes: {audit.get('audit_notes', '') if audit else ''}\n"
        f"Hallucinated citations: {audit.get('hallucinated_citations', []) if audit else []}\n\n"
        "Type 'approve' to accept the verdict, or 'reject' to hear another round of argument.\n"
    )

    decision = interrupt({"prompt": prompt_text, "verdict_draft": verdict_draft})

    approved = str(decision).strip().lower() == "approve"
    result: dict = {"hitl_approved": approved, "current_phase": "hitl"}
    if not approved:
        # "Hear another round": advance the round counter so the advocates argue
        # a fresh round before the gate reappears, rather than re-scoring the
        # round already shown.
        result["current_round"] = state.get("current_round", 1) + 1
    return result


def build_graph(checkpointer=None) -> StateGraph:
    """Construct and compile the moot court StateGraph."""
    graph = StateGraph(GraphState)

    # ── Import all node functions ──────────────────────────────────────────
    from agents.clerk import clerk_node
    from agents.prosecution import prosecution_node
    from agents.defence import defence_node
    from agents.judge import judge_node, verdict_node
    from agents.auditor import auditor_node

    # ── Register nodes ─────────────────────────────────────────────────────
    graph.add_node("clerk_node", clerk_node)
    graph.add_node("prosecution_node", prosecution_node)
    graph.add_node("defence_node", defence_node)
    graph.add_node("judge_node", judge_node)
    graph.add_node("auditor_node", auditor_node)
    graph.add_node("hitl_node", _hitl_node)
    graph.add_node("verdict_node", verdict_node)

    # ── Edges ──────────────────────────────────────────────────────────────
    graph.add_edge(START, "clerk_node")
    graph.add_edge("clerk_node", "prosecution_node")
    graph.add_edge("prosecution_node", "defence_node")
    graph.add_edge("defence_node", "judge_node")

    # Conditional: Judge decides loop vs proceed
    graph.add_conditional_edges(
        "judge_node",
        judge_routing,
        {
            "prosecution_node": "prosecution_node",
            "auditor_node": "auditor_node",
        },
    )

    # Conditional: Auditor decides clean vs re-argue
    graph.add_conditional_edges(
        "auditor_node",
        auditor_routing,
        {
            "prosecution_node": "prosecution_node",
            "hitl_node": "hitl_node",
        },
    )

    # Conditional: HITL decides approve vs reject
    graph.add_conditional_edges(
        "hitl_node",
        hitl_routing,
        {
            "verdict_node": "verdict_node",
            "prosecution_node": "prosecution_node",
        },
    )

    graph.add_edge("verdict_node", END)

    return graph.compile(
        checkpointer=checkpointer or MemorySaver(),
        interrupt_before=["hitl_node"],
    )


# Module-level compiled graph (lazy — avoids import-time LLM calls)
_compiled_graph = None


def get_graph():
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_graph()
    return _compiled_graph
