"""Judge agent — scores each round and decides whether to loop or proceed."""
from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage

from agents.prompts import JUDGE_SYSTEM, VERDICT_SYSTEM
from graph.config import get_max_rounds
from graph.state import GraphState, JudgeScore, Verdict
from utils.llm import get_judge_structured_llm

# Percentage points of win probability per point of average strength margin.
# At 7, a ~3-point average lead reaches the 70/30 early-exit threshold, while a
# 1-point lean reads as ~57% — "leaning", not decisive.
_WIN_PROB_MARGIN_SCALE = 7

# Win probability at/above which the case is decisively one-sided and the trial
# exits to verdict early (the low side mirror is 100 - this). At 70 with the
# scale above, an average strength lead of ~3 points (e.g. 8 vs 5) ends the
# trial; genuinely close cases (within ~2 points) keep arguing up to the cap.
_EARLY_EXIT_WP = 70


def win_probability(prosecution_mean: float, defence_mean: float) -> int:
    """Running merits balance as a 5–95 win probability for the prosecution.

    Pure function of the average per-round strength margin so it is trivially
    testable and reused by both ``judge_node`` and the early-exit check.
    """
    return max(5, min(95, round(50 + (prosecution_mean - defence_mean) * _WIN_PROB_MARGIN_SCALE)))


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
    structured_llm = get_judge_structured_llm(JudgeScore)

    _MAX_ROUNDS = get_max_rounds()
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
        '  "reasoning": "DECIDE WHO IS WINNING THE CASE (required): '
        '(a) Identify any dispositive or threshold issue in play (admissibility, unlawful procedure, burden of proof, a complete defence) and which side it favours. '
        '(b) For each side, state whether the elements of the offence are made out or defeated on the facts. '
        '(c) Weigh the balance — who is currently winning on the merits, and can the other side still recover? '
        '(d) Give each side a case-strength score (1-10) reflecting that balance, and explain any change from the prior round.",\n'
        '  "prosecution_strength": 5,\n'
        '  "defence_strength": 5,\n'
        '  "weak_side": "balanced",\n'
        '  "uncited_statutes": ["statute that should have been cited but wasn\'t"],\n'
        '  "decision": "another_round"\n'
        "}\n"
        "\nREPLACE prosecution_strength=5 and defence_strength=5 with scores reflecting which side "
        "is winning the CASE (a side holding a dispositive point scores high, its opponent low, "
        "however polished the opponent's arguments). The two scores MUST differ unless the merits "
        "are genuinely even."
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
                f"{'FINAL ROUND — you MUST set decision to proceed_to_verdict.' if rounds_remaining <= 0 else 'Rounds remain — set proceed_to_verdict if one side now leads the other by 3+ points (clearly winning and the opponent cannot recover); otherwise another_round.'}\n\n"
                f"Return ONLY a valid JSON object:\n{_schema}"
            )
        ),
    ]

    score: JudgeScore = structured_llm.invoke(messages)
    score.round_number = current_round

    # Hard cap — never trust the LLM to self-terminate on the final round.
    if current_round >= _MAX_ROUNDS:
        score.decision = "proceed_to_verdict"

    # Win probability is the running BALANCE of the case — the average per-round
    # strength margin mapped onto a 5-95 scale — not a cumulative tally. A steady
    # modest edge therefore reads as "leaning" rather than runaway to 95%, keeping
    # it consistent with the margin-based confidence and the verdict's own tone.
    # (A cumulative sum let a small sustained edge balloon to 95% over many rounds
    # while confidence stayed "moderate", which looked contradictory.)
    # De-duplicate by round first: if a round was re-scored, the new score must
    # REPLACE the prior entry rather than be averaged in twice.
    by_round: dict = {}
    for s in all_scores + [score.model_dump()]:
        by_round[s.get("round_number")] = s
    rounds_so_far = list(by_round.values())
    rounds_count = len(rounds_so_far)
    prosecution_mean = sum(s.get("prosecution_strength", 5) for s in rounds_so_far) / rounds_count
    defence_mean = sum(s.get("defence_strength", 5) for s in rounds_so_far) / rounds_count
    score.win_probability = win_probability(prosecution_mean, defence_mean)

    # Early exit — case is decisively one-sided, further rounds won't change the outcome.
    if score.win_probability >= _EARLY_EXIT_WP or score.win_probability <= 100 - _EARLY_EXIT_WP:
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


def confidence_from_margin(prosecution_avg: float, defence_avg: float) -> int:
    """Map the average per-round strength margin to a 1-10 confidence score.

    Confidence must reflect how decisively one side outscored the other across
    the whole trial. We deliberately do NOT derive it from the final
    win_probability: win_probability is gated to terminate the trial the moment
    it reaches 70, and because it moves in fixed steps it clusters near that
    threshold for most decisive cases — collapsing confidence to a near-constant.
    The average margin keeps full resolution and is unaffected by where the
    early-exit happened to fire.

    The scale aligns with the verdict's confidence buckets: a 1-point average
    margin reads as "low", 2 as "moderate", 3 as "high", 4+ as "overwhelming".
    """
    margin = abs(prosecution_avg - defence_avg)
    return min(10, max(1, round(1 + margin * 2)))


def verdict_node(state: GraphState) -> dict:
    """LangGraph node: Judge renders the final verdict after HITL approval."""
    structured_llm = get_judge_structured_llm(Verdict)

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

    # Running merits-based win probability after the final round — the ruling must
    # be consistent with which side this says prevailed (the scores already weight
    # dispositive points), so the verdict and the displayed probability agree.
    final_wp = scores[-1].get("win_probability", 50) if scores else 50

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
                f"Prosecution avg {p_avg:.1f}/10 · Defence avg {d_avg:.1f}/10\n"
                f"Running win probability after the final round: prosecution {final_wp}% / "
                f"defence {100 - final_wp}%.\n"
                f"Your ruling MUST be consistent with this balance — prosecution ahead (>55%) → "
                f"'liable', defence ahead (<45%) → 'not_liable', otherwise 'inconclusive'. If you "
                f"depart from it, explain why in dissent_notes.\n\n"
                f"Return ONLY valid JSON:\n{_schema}"
            )
        ),
    ]

    verdict: Verdict = structured_llm.invoke(messages)

    # Override LLM confidence. The LLM anchors to ~8 regardless of case strength,
    # so we compute it from the average per-round strength margin instead — see
    # confidence_from_margin for why this beats deriving it from win_probability.
    verdict.confidence = confidence_from_margin(p_avg, d_avg)

    return {
        "verdict": verdict.model_dump(),
        "current_phase": "done",
    }
