"""Clerk / Intake agent — parses raw facts into a structured CaseFile."""
from __future__ import annotations

from datetime import date, datetime

from langchain_core.messages import HumanMessage, SystemMessage

from agents.prompts import CLERK_SYSTEM
from graph.state import CaseFile, GraphState
from utils.llm import get_structured_llm


_BNS_CUTOVER = date(2024, 7, 1)

# Formats accepted from the UI free-text field
_DATE_FMTS = ["%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%B %d, %Y", "%d %B %Y"]


def _parse_date_strict(s: str) -> date:
    """Parse an explicit date string; raise ValueError if unrecognised."""
    for fmt in _DATE_FMTS:
        try:
            return datetime.strptime(s.strip(), fmt).date()
        except ValueError:
            pass
    raise ValueError(f"Unrecognised date format: {s!r}")


def _regime_from_date(d: date) -> str:
    return "BNS" if d >= _BNS_CUTOVER else "IPC"


def clerk_node(state: GraphState) -> dict:
    """LangGraph node: parse the user's fact-scenario into a CaseFile."""
    facts_raw: str = state.get("facts_raw", "")
    offence_date_str: str | None = state.get("offence_date")

    # Determine code regime from the explicitly provided date (no guessing).
    if offence_date_str:
        offence_date = _parse_date_strict(offence_date_str)
        code_regime = _regime_from_date(offence_date)
    else:
        raise ValueError("offence_date is required — it must be provided before the graph is run.")

    structured_llm = get_structured_llm(CaseFile)

    _schema_hint = (
        '{"facts": "...", "legal_questions": ["...", "..."], '
        f'"code_regime": "{code_regime}", "offence_date": "{offence_date_str}", '
        '"accused_name": "...", "offence_type": "..."}'
    )

    messages = [
        SystemMessage(content=CLERK_SYSTEM),
        HumanMessage(
            content=(
                f"Parse the following fact-scenario into a structured CaseFile.\n"
                f"Return ONLY a valid JSON object with exactly these keys:\n"
                f"{_schema_hint}\n\n"
                f"The offence date is {offence_date_str} and the code regime is {code_regime} "
                f"(already determined — do NOT change these values).\n\n"
                f"FACT SCENARIO:\n{facts_raw}"
            )
        ),
    ]

    case_file: CaseFile = structured_llm.invoke(messages)

    # Enforce deterministic values — LLM must not override these
    case_file.offence_date = offence_date_str
    case_file.code_regime = code_regime

    return {
        "case_file": case_file,
        "current_round": 1,
        "current_phase": "argue",
        "round_transcript": [],
        "judge_scores": [],
        "audit_result": None,
        "audit_passed": False,
        "hitl_approved": False,
        "verdict": None,
        "error": None,
    }
