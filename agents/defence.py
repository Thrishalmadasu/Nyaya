"""Defence Advocate agent — argues against liability."""
from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage

from agents.prompts import DEFENCE_SYSTEM
from graph.state import Argument, GraphState
from utils.llm import get_structured_llm

# Terms that mark a case as raising a constitutional question, so retrieval is
# allowed to pull in Constitution articles (otherwise scoped out by default).
_CONSTITUTIONAL_TERMS = (
    "article", "constitution", "constitutional", "fundamental right",
    "right to life", "personal liberty", "equality before law",
    "freedom of speech", "due process",
)


def _retrieve_context(case_file, query_extra: str = "") -> str:
    from rag.retriever import retrieve
    from rag.precedent_search import get_precedents

    regime = case_file.code_regime
    # Query the statute index with the offence itself. Role/era words like
    # "defence acquittal mens rea BNS" are dense-retrieval noise — they pull
    # procedural and boilerplate sections ahead of the substantive offence. The
    # regime is already applied as a metadata filter, so it doesn't belong in
    # the query text. Both advocates retrieve the same offence statutes; the
    # adversarial framing comes from the prompts and rebuttal injection.
    base_query = (
        f"{case_file.offence_type} {query_extra}".strip()
        or " ".join(case_file.legal_questions or [])
        or case_file.facts[:200]
    )
    # Pull constitutional articles in only when the case actually raises a
    # constitutional question, so ordinary crimes don't get Article-20 noise.
    case_text = f"{case_file.offence_type} {' '.join(case_file.legal_questions or [])}".lower()
    include_const = any(t in case_text for t in _CONSTITUTIONAL_TERMS)
    chunks = retrieve(base_query, code_regime=regime, top_k=3, include_constitution=include_const)
    statute_text = "\n\n".join(
        f"[{c.source_act} — {c.section_id}]\n{c.text[:400]}" for c in chunks
    ) or "No statutes retrieved."

    # Neutral, offence-based query — both advocates retrieve the same precedents;
    # the adversarial framing comes from the prompts, not a biased search term.
    precedents = get_precedents(f"{case_file.offence_type} {base_query}".strip())
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
        '"claims": ["<specific fact-grounded claim>", "<second claim>"], '
        '"statutes_cited": ["<Act Section Number>"], '
        '"precedents_cited": ["<Real Case Name v Real Party (Year)>"], '
        '"rebuttals": ["<specific rebuttal to prosecution point>"], '
        '"summary": "<one-line summary>"}'
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
