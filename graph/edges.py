from __future__ import annotations

import os
from typing import Literal

from graph.state import GraphState


def judge_routing(state: GraphState) -> Literal["prosecution_node", "auditor_node"]:
    """Route after the Judge scores a round.

    Loops back for another round unless the Judge decided 'proceed_to_verdict'
    OR the hard MAX_ROUNDS cap is reached.

    The confidence-threshold early-stop is intentionally removed — it was
    causing the routing to ignore the judge's own 'another_round' decision
    whenever max(prosecution, defence) happened to equal the threshold score.
    The judge's decision field is the sole authority for continuing vs stopping.
    MAX_ROUNDS is the only hard override.

    Env vars are read inside the function (not at module level) so that
    load_dotenv() in app.py is guaranteed to have run first.
    """
    max_rounds = int(os.getenv("MOOT_COURT_MAX_ROUNDS", "5"))

    scores = state.get("judge_scores", [])
    if not scores:
        return "prosecution_node"

    last_score = scores[-1]
    decision = last_score.get("decision", "proceed_to_verdict")

    # current_round was already incremented by judge_node when decision == "another_round",
    # so it represents the NEXT round about to be argued.
    # We continue as long as that next round is still within the cap.
    current_round = state.get("current_round", 1)

    if decision == "another_round" and current_round <= max_rounds:
        return "prosecution_node"
    # If the judge said another_round but the cap is already exceeded,
    # force auditor. judge_node applies the same cap so this is a
    # defence-in-depth guard only.
    return "auditor_node"


def hitl_routing(state: GraphState) -> Literal["verdict_node", "prosecution_node"]:
    """Route after human review.

    Human approved → finalise verdict.
    Human rejected ("hear another round") → send the advocates back to argue a
    fresh round (prosecution → defence → judge), then return to the gate. We
    route to prosecution rather than back to the Judge so the trial gains a
    genuinely new round of argument instead of re-scoring the round just shown
    — re-scoring appended a duplicate score for the same round and double-counted
    its strength differential in the win-probability calculation.
    """
    if state.get("hitl_approved", False):
        return "verdict_node"
    return "prosecution_node"
