"""Shared advocate logic for the Prosecution and Defence agents.

Both advocates run an identical pipeline — retrieve statutes + precedents, build
the round context (rebutting the opponent's last argument, folding in the judge's
hint), then ask the LLM for a structured Argument. The only differences are the
side label, which opponent to rebut, which strength field the judge hint reads,
the system prompt, and the phase the node advances to. Keeping the logic here
(parameterised by side) means there is one place to fix bugs instead of two that
silently drift apart.
"""
from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage

from graph.state import Argument, GraphState
from utils.llm import get_structured_llm

# Terms that mark a case as raising a constitutional question, so retrieval is
# allowed to pull in Constitution articles (otherwise scoped out by default).
_CONSTITUTIONAL_TERMS = (
    "article", "constitution", "constitutional", "fundamental right",
    "right to life", "personal liberty", "equality before law",
    "freedom of speech", "due process",
)

# The opponent each side rebuts, and the judge-score field that reflects its
# own strength from the previous round.
_OPPONENT = {"prosecution": "defence", "defence": "prosecution"}
_STRENGTH_FIELD = {"prosecution": "prosecution_strength", "defence": "defence_strength"}

# The short code an advocate cites a section by, keyed on source_act. Derived
# from source_act (NOT code_regime) because BNS 2023, BNSS 2023 and BSA 2023 all
# share code_regime "BNS" — labelling a BNSS section "BNS Section 378" would be
# the very wrong-regime citation the audit now rejects.
_CITE_PREFIX = {
    "BNS 2023": "BNS",
    "BNSS 2023": "BNSS",
    "BSA 2023": "BSA",
    "IPC 1860": "IPC",
    "Constitution of India": "Constitution",
}


def _citation_label(chunk) -> str:
    """Exact label an advocate must cite a retrieved chunk by (e.g. 'BNS Section
    303'). Constitution articles are cited as the bare 'Article N'."""
    if chunk.section_id.lower().startswith("article"):
        return chunk.section_id
    prefix = _CITE_PREFIX.get(chunk.source_act, chunk.code_regime)
    return f"{prefix} {chunk.section_id}"


def retrieve_context(case_file, query_extra: str = "") -> str:
    """Retrieve the statutes and precedents both advocates argue from.

    Query the statute index with the offence itself. Role/era words like
    "liability prosecution BNS" are dense-retrieval noise — they pull procedural
    and boilerplate sections ahead of the substantive offence. The regime is
    already applied as a metadata filter, so it doesn't belong in the query text.
    Both advocates retrieve the same offence statutes and precedents; the
    adversarial framing comes from the prompts and rebuttal injection.
    """
    from rag.retriever import retrieve
    from rag.precedent_search import get_precedents

    regime = case_file.code_regime
    base_query = (
        f"{case_file.offence_type} {query_extra}".strip()
        or " ".join(case_file.legal_questions or [])
        or case_file.facts[:200]
    )
    # Pull constitutional articles in only when the case actually raises a
    # constitutional question, so ordinary crimes don't get Article-20 noise.
    case_text = f"{case_file.offence_type} {' '.join(case_file.legal_questions or [])}".lower()
    include_const = any(t in case_text for t in _CONSTITUTIONAL_TERMS)
    # top_k=6 (not 3): the on-point definitional section can rank a few places
    # below near-synonym sections (e.g. for "theft", BNS 305/307 outrank the
    # bare 303 "Theft"), so a tight top_k would omit the section the advocate
    # actually needs and force it to fall back on a remembered (wrong) number.
    chunks = retrieve(base_query, code_regime=regime, top_k=6, include_constitution=include_const)
    statute_text = "\n\n".join(
        f"{_citation_label(c)} — {c.section_title}:\n{c.text[:300]}" for c in chunks
    ) or "No statutes retrieved."

    # Query precedents by the legal issue, not the doubled offence string —
    # the issue (e.g. "circumstantial evidence murder") matches the right ratio,
    # where a coarse offence word pulls the same headline case every time. Each
    # corpus entry is now one concise per-case overview, so we send the full
    # text (no mid-judgment truncation) and keep distinct cases.
    prec_query = " ".join(case_file.legal_questions or []).strip() or case_file.offence_type
    precedents = get_precedents(prec_query)

    distinct: list[dict] = []
    seen_titles: set[str] = set()
    for p in precedents:
        title = p.get("title", "Unknown")
        key = title.strip().lower()
        if key in seen_titles:
            continue
        seen_titles.add(key)
        distinct.append(p)
        # Hard ceiling of 2 distinct cases — each overview is dense, so this
        # keeps the precedent payload to the runtime LLM small and on-point.
        if len(distinct) >= 2:
            break

    prec_text = "\n\n".join(
        f"- {p.get('title', 'Unknown')}: {p.get('content', '')}" for p in distinct
    ) or "No precedents retrieved."

    return (
        "RETRIEVED STATUTES — cite statutes ONLY from this list, using the exact "
        "label shown before each em-dash (e.g. 'BNS Section 303'):\n"
        f"{statute_text}\n\n"
        f"RELEVANT PRECEDENTS:\n{prec_text}"
    )


def build_context(state: GraphState, side: str, rag_context: str) -> str:
    """Assemble the full prompt context for ``side`` this round."""
    case_file = state["case_file"]
    regime = case_file.code_regime
    round_num = state["current_round"]
    transcript = state.get("round_transcript", [])
    opponent = _OPPONENT[side]

    opponent_arg = ""
    if transcript:
        last_opp = next(
            (a for a in reversed(transcript) if a.get("side") == opponent), None
        )
        if last_opp:
            opponent_arg = (
                f"\n\n{opponent.capitalize()}'s argument to rebut:\n"
                f"Claims: {last_opp.get('claims', [])}\n"
                f"Statutes: {last_opp.get('statutes_cited', [])}\n"
                f"Precedents: {last_opp.get('precedents_cited', [])}"
            )

    judge_hint = ""
    scores = state.get("judge_scores", [])
    if scores:
        last = scores[-1]
        judge_hint = (
            f"\n\nJudge's note from last round:\n"
            f"Statutes you should cite: {last.get('uncited_statutes', [])}\n"
            f"Your strength score was {last.get(_STRENGTH_FIELD[side])}/10."
        )

    return (
        f"Code regime: {regime}\n"
        f"Round: {round_num}\n"
        f"Facts: {case_file.facts}\n"
        f"Legal questions: {case_file.legal_questions}\n\n"
        f"{rag_context}"
        f"{opponent_arg}{judge_hint}"
    )


def run_advocate(state: GraphState, *, side: str, system_prompt: str, next_phase: str) -> dict:
    """Run one advocate round for ``side`` and return the graph-state update."""
    case_file = state["case_file"]
    round_num = state["current_round"]

    rag_context = retrieve_context(case_file)
    context = build_context(state, side, rag_context)

    structured_llm = get_structured_llm(Argument)

    _schema = (
        '{"side": "' + side + '", "round_number": ' + str(round_num) + ', '
        '"claims": ["<specific fact-grounded claim>", "<second claim>"], '
        '"statutes_cited": ["<Act Section Number>"], '
        '"precedents_cited": ["<Real Case Name v Real Party (Year)>"], '
        f'"rebuttals": ["<specific rebuttal to {_OPPONENT[side]} point>"], '
        '"summary": "<one-line summary>"}'
    )

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(
            content=(
                f"Prepare your Round {round_num} {side} argument.\n\n"
                f"{context}\n\n"
                f"Return ONLY a valid JSON object with exactly this structure:\n{_schema}\n"
                f"statutes_cited MUST contain at least 2 section labels copied exactly "
                f"from the RETRIEVED STATUTES list above (each looks like 'BNS Section 303'); "
                f"use only labels that appear in that list. claims must be a list of strings."
            )
        ),
    ]

    argument: Argument = structured_llm.invoke(messages)
    argument.side = side
    argument.round_number = round_num

    return {
        "round_transcript": [argument.model_dump()],
        "current_phase": next_phase,
    }
