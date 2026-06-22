"""Judge agent — scores each round and decides whether to loop or proceed."""
from __future__ import annotations

import os

from langchain_core.messages import HumanMessage, SystemMessage

from agents.prompts import JUDGE_SYSTEM, VERDICT_SYSTEM
from graph.state import GraphState, JudgeScore, Verdict
from utils.llm import get_structured_llm


def _format_transcript(transcript: list[dict]) -> str:
    lines = []
    for arg in transcript:
        lines.append(
            f"[Round {arg.get('round_number')} — {arg.get('side', '').upper()}]\n"
            f"Claims: {arg.get('claims', [])}\n"
            f"Statutes: {arg.get('statutes_cited', [])}\n"
            f"Precedents: {arg.get('precedents_cited', [])}\n"
            f"Rebuttals: {arg.get('rebuttals', [])}\n"
        )
    return "\n".join(lines)


def judge_node(state: GraphState) -> dict:
    """LangGraph node: Judge evaluates the round and decides next step."""
    structured_llm = get_structured_llm(JudgeScore)

    _MAX_ROUNDS = int(os.getenv("MOOT_COURT_MAX_ROUNDS", "5"))
    current_round = state.get("current_round", 1)
    transcript = state.get("round_transcript", [])
    case_file = state["case_file"]

    # Round-level transcript only (current round arguments)
    round_transcript = [
        a for a in transcript if a.get("round_number") == current_round
    ]

    rounds_remaining = _MAX_ROUNDS - current_round

    # Prior scores context — forces the judge to compare, not repeat
    prior_scores_text = ""
    all_scores = state.get("judge_scores", [])
    if all_scores:
        prior_lines = []
        for s in all_scores:
            prior_lines.append(
                f"  Round {s.get('round_number')}: "
                f"Prosecution {s.get('prosecution_strength')}/10, "
                f"Defence {s.get('defence_strength')}/10 "
                f"(decision: {s.get('decision')})"
            )
        prior_scores_text = (
            "\nYour prior scores for reference:\n" + "\n".join(prior_lines) +
            "\nIf you award the same score again, explain WHY the argument quality was identical.\n"
        )

    # reasoning MUST come before score fields — forces chain-of-thought before committing to numbers.
    _schema = (
        "{\n"
        f'  "round_number": {current_round},\n'
        '  "reasoning": "EVALUATE FIRST (required): '
        '(a) List specific claims prosecution made and rate them — are they fact-grounded? statutes cited correctly? '
        '(b) List specific claims defence made and rate them similarly. '
        '(c) Compare rebuttal quality — who engaged with the opponent\'s actual points? '
        '(d) State the final score each side deserves and WHY it differs from any prior round score.",\n'
        '  "prosecution_strength": 5,\n'
        '  "defence_strength": 5,\n'
        '  "weak_side": "balanced",\n'
        '  "uncited_statutes": ["statute that should have been cited but wasn\'t"],\n'
        '  "decision": "another_round"\n'
        "}\n"
        "\nREPLACE prosecution_strength=5 and defence_strength=5 with your actual scores "
        "derived from the reasoning above. The two sides MUST receive different scores unless "
        "you can explain in reasoning why both argued at exactly the same level."
    )

    messages = [
        SystemMessage(content=JUDGE_SYSTEM),
        HumanMessage(
            content=(
                f"Score Round {current_round} of the moot court.\n\n"
                f"Case: {case_file.facts[:600]}\n"
                f"Legal questions: {case_file.legal_questions}\n"
                f"Code regime: {case_file.code_regime}\n\n"
                f"{prior_scores_text}\n"
                f"--- Round {current_round} arguments to evaluate ---\n"
                f"{_format_transcript(round_transcript)}\n"
                f"--- End of arguments ---\n\n"
                f"Round {current_round} of {_MAX_ROUNDS} maximum. "
                f"Rounds remaining after this: {rounds_remaining}.\n"
                f"{'FINAL ROUND — you MUST set decision to proceed_to_verdict.' if rounds_remaining == 0 else 'Rounds remain — default to another_round unless both sides scored 8+.'}\n\n"
                f"Return ONLY a valid JSON object:\n{_schema}"
            )
        ),
    ]

    score: JudgeScore = structured_llm.invoke(messages)
    score.round_number = current_round

    # Hard cap — never trust the LLM to self-terminate on the final round.
    if current_round >= _MAX_ROUNDS:
        score.decision = "proceed_to_verdict"

    # Compute win_probability deterministically from cumulative score differentials.
    # Start at 50 (neutral) and add 5 percentage points per score-point advantage
    # for every round played so far (including this one). This ensures the probability
    # actually moves each round instead of being re-anchored by the LLM every time.
    all_rounds_so_far = all_scores + [score.model_dump()]
    running_wp = 50
    for s in all_rounds_so_far:
        running_wp += (s.get("prosecution_strength", 5) - s.get("defence_strength", 5)) * 5
    score.win_probability = max(5, min(95, round(running_wp)))

    # Early exit — case is decisively one-sided, further rounds won't change the outcome.
    if score.win_probability >= 80 or score.win_probability <= 20:
        score.decision = "proceed_to_verdict"

    next_round = current_round + 1 if score.decision == "another_round" else current_round

    return {
        "judge_scores": [score.model_dump()],
        "current_round": next_round,
        "current_phase": "audit" if score.decision == "proceed_to_verdict" else "argue",
    }


def _compact_transcript(transcript: list[dict]) -> str:
    """One line per argument — enough context for verdict without burning tokens."""
    lines = []
    for arg in transcript:
        side     = arg.get("side", "?").upper()
        rn       = arg.get("round_number", "?")
        claims   = arg.get("claims") or []
        statutes = arg.get("statutes_cited") or []
        precs    = arg.get("precedents_cited") or []
        snippet  = (str(claims[0])[:50] + "…") if claims else "—"
        stat_str = ", ".join(str(s) for s in statutes[:2]) or "—"
        prec_str = (str(precs[0])[:40] + "…") if precs else "—"
        lines.append(f"R{rn} {side}: {snippet} [stat: {stat_str}] [prec: {prec_str}]")
    return "\n".join(lines)


def verdict_node(state: GraphState) -> dict:
    """LangGraph node: Judge renders the final verdict after HITL approval."""
    structured_llm = get_structured_llm(Verdict)

    transcript = state.get("round_transcript", [])
    scores = state.get("judge_scores", [])
    case_file = state["case_file"]

    p_scores = [s.get("prosecution_strength", 5) for s in scores]
    d_scores = [s.get("defence_strength", 5) for s in scores]
    p_avg = sum(p_scores) / len(p_scores) if p_scores else 5
    d_avg = sum(d_scores) / len(d_scores) if d_scores else 5

    # Compact score summary — one short line per round
    score_lines = "\n".join(
        f"  R{s.get('round_number')}: P={s.get('prosecution_strength')}/10 "
        f"D={s.get('defence_strength')}/10"
        for s in scores
    )

    _schema = (
        "{\n"
        '  "reasoning": "Which side proved their case and why — cite the key statutes and facts.",\n'
        '  "ruling": "liable or not_liable or inconclusive",\n'
        '  "confidence": 5,\n'
        '  "statutes_relied_on": ["up to 4 statutes actually cited in the trial"],\n'
        '  "precedents_relied_on": ["up to 3 precedents actually cited"],\n'
        '  "dissent_notes": "any caveats",\n'
        '  "disclaimer": "This is an AI-generated educational simulation. It does NOT constitute legal advice. Consult a qualified advocate."\n'
        "}\n"
        "\nReplace confidence=5 with your actual 1-10 score. "
        "ruling must be exactly 'liable', 'not_liable', or 'inconclusive'."
    )

    messages = [
        SystemMessage(content=VERDICT_SYSTEM),
        HumanMessage(
            content=(
                f"Render the final verdict.\n\n"
                f"Facts: {case_file.facts[:300]}\n"
                f"Regime: {case_file.code_regime}\n\n"
                f"Trial ({len(scores)} rounds):\n{_compact_transcript(transcript)}\n\n"
                f"Scores:\n{score_lines}\n"
                f"Prosecution avg {p_avg:.1f}/10 · Defence avg {d_avg:.1f}/10\n\n"
                f"Return ONLY valid JSON:\n{_schema}"
            )
        ),
    ]

    verdict: Verdict = structured_llm.invoke(messages)

    # Override LLM confidence with a value derived from the final win_probability.
    # The LLM anchors to ~8 regardless of case strength; win_probability is the
    # ground truth we computed round-by-round.
    final_wp = scores[-1].get("win_probability", 50) if scores else 50
    derived_confidence = min(10, max(1, round(abs(final_wp - 50) / 5)))
    verdict.confidence = derived_confidence

    return {
        "verdict": verdict.model_dump(),
        "current_phase": "done",
    }
