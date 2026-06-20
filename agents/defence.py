"""Defence Advocate agent — argues against liability."""
from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage

from agents.prompts import DEFENCE_SYSTEM
from graph.state import Argument, GraphState
from utils.llm import get_structured_llm


def _retrieve_context(case_file, query_extra: str = "") -> str:
    from rag.retriever import retrieve
    from rag.precedent_search import search_precedents

    regime = case_file.code_regime
    base_query = f"{case_file.offence_type} {query_extra} defence acquittal mens rea {regime}"
    chunks = retrieve(base_query, code_regime=regime, top_k=3)
    statute_text = "\n\n".join(
        f"[{c.source_act} — {c.section_id}]\n{c.text[:400]}" for c in chunks
    ) or "No statutes retrieved."

    precedents = search_precedents(f"Indian criminal law {case_file.offence_type} acquittal defence")
    prec_text = "\n".join(
        f"- {p.get('title', 'Unknown')}: {p.get('content', '')[:100]}"
        for p in precedents[:2]
    ) or "No precedents retrieved."

    return f"RETRIEVED STATUTES:\n{statute_text}\n\nRELEVANT PRECEDENTS:\n{prec_text}"


def _build_context(state: GraphState, rag_context: str) -> str:
    case_file = state["case_file"]
    regime = case_file.code_regime
    round_num = state["current_round"]
    transcript = state.get("round_transcript", [])

    prosecution_arg = ""
    if transcript:
        last_pros = next(
            (a for a in reversed(transcript) if a.get("side") == "prosecution"), None
        )
        if last_pros:
            prosecution_arg = (
                f"\n\nProsecution's argument to rebut:\n"
                f"Claims: {last_pros.get('claims', [])}\n"
                f"Statutes: {last_pros.get('statutes_cited', [])}\n"
                f"Precedents: {last_pros.get('precedents_cited', [])}"
            )

    judge_hint = ""
    scores = state.get("judge_scores", [])
    if scores:
        last = scores[-1]
        judge_hint = (
            f"\n\nJudge's note from last round:\n"
            f"Statutes you should cite: {last.get('uncited_statutes', [])}\n"
            f"Your strength score was {last.get('defence_strength')}/10."
        )

    return (
        f"Code regime: {regime}\n"
        f"Round: {round_num}\n"
        f"Facts: {case_file.facts}\n"
        f"Legal questions: {case_file.legal_questions}\n\n"
        f"{rag_context}"
        f"{prosecution_arg}{judge_hint}"
    )


def defence_node(state: GraphState) -> dict:
    """LangGraph node: Defence advocate argues against liability."""
    case_file = state["case_file"]
    round_num = state["current_round"]

    rag_context = _retrieve_context(case_file)
    context = _build_context(state, rag_context)

    structured_llm = get_structured_llm(Argument)

    _schema = (
        '{"side": "defence", "round_number": ' + str(round_num) + ', '
        '"claims": ["claim 1", "claim 2"], '
        '"statutes_cited": ["BNS Section 35", "Article 21"], '
        '"precedents_cited": ["Case Name v State (Year)"], '
        '"rebuttals": ["counter to prosecution argument"], '
        '"summary": "one-line summary"}'
    )

    messages = [
        SystemMessage(content=DEFENCE_SYSTEM),
        HumanMessage(
            content=(
                f"Prepare your Round {round_num} defence argument.\n\n"
                f"{context}\n\n"
                f"Return ONLY a valid JSON object with exactly this structure:\n{_schema}\n"
                f"statutes_cited must be plain strings like 'BNS Section 35'. "
                f"claims must be a list of strings."
            )
        ),
    ]

    argument: Argument = structured_llm.invoke(messages)
    argument.side = "defence"
    argument.round_number = round_num

    return {
        "round_transcript": [argument.model_dump()],
        "current_phase": "judge",
    }
