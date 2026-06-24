from __future__ import annotations

from typing import Annotated, Literal
from typing_extensions import TypedDict

from pydantic import BaseModel, Field, model_validator
import operator


class CaseFile(BaseModel):
    facts: str
    legal_questions: list[str]
    code_regime: Literal["BNS", "IPC"] = "BNS"
    offence_date: str | None = Field(
        default=None,
        description="ISO date string YYYY-MM-DD, or null if unknown",
    )
    accused_name: str = "Accused"
    offence_type: str = ""

    @model_validator(mode="before")
    @classmethod
    def _unwrap_nested(cls, data: object) -> object:
        """Handle models that return {"case_file": {...}} or use alias field names."""
        if not isinstance(data, dict):
            return data
        # Unwrap outer container key
        for key in ("case_file", "CaseFile", "casefile"):
            if key in data and isinstance(data[key], dict):
                data = data[key]
                break
        # Alias normalisation for common misnamings
        if "facts" not in data:
            for alt in ("core_facts", "summary", "fact_summary", "case_facts"):
                if alt in data:
                    data = dict(data)
                    data["facts"] = data.pop(alt)
                    break
        if "offence_type" not in data:
            for alt in ("type_of_offence", "offence", "charge"):
                if alt in data:
                    data = dict(data)
                    data["offence_type"] = data.pop(alt)
                    break
        return data


class Argument(BaseModel):
    side: Literal["prosecution", "defence"] = "prosecution"
    round_number: int = 1
    claims: list[str] = Field(default_factory=list)
    statutes_cited: list[str] = Field(
        default_factory=list,
        description="e.g. ['BNS Section 103', 'Constitution Article 21']",
    )
    precedents_cited: list[str] = Field(
        default_factory=list,
        description="e.g. ['Kedar Nath Singh v. State of Bihar (1962)']",
    )
    rebuttals: list[str] = Field(default_factory=list)
    summary: str = ""

    @model_validator(mode="before")
    @classmethod
    def _unwrap_nested(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data
        # Unwrap outer container key
        for key in ("argument", "Argument", "prosecution_argument", "defence_argument"):
            if key in data and isinstance(data[key], dict):
                data = data[key]
                break
        data = dict(data)
        # Normalise claims
        if "claims" not in data:
            for alt in ("claim", "arguments", "argument_points", "legal_arguments"):
                if alt in data:
                    v = data.pop(alt)
                    data["claims"] = [v] if isinstance(v, str) else (v if isinstance(v, list) else [str(v)])
                    break
        # Normalise statutes_cited — may be list of strings OR list of dicts
        if "statutes_cited" not in data:
            for alt in ("statutes", "statutory_basis", "cited_statutes", "statute_citations"):
                if alt in data:
                    raw = data.pop(alt)
                    if isinstance(raw, list):
                        flat = []
                        for item in raw:
                            if isinstance(item, str):
                                flat.append(item)
                            elif isinstance(item, dict):
                                flat.append(item.get("statute") or item.get("section") or str(item))
                        data["statutes_cited"] = flat
                    break
        # Normalise precedents_cited
        if "precedents_cited" not in data:
            for alt in ("precedents", "precedent_support", "cited_precedents", "case_references"):
                if alt in data:
                    raw = data.pop(alt)
                    if isinstance(raw, list):
                        flat = []
                        for item in raw:
                            if isinstance(item, str):
                                flat.append(item)
                            elif isinstance(item, dict):
                                flat.append(item.get("precedent") or item.get("case") or str(item))
                        data["precedents_cited"] = flat
                    break
        # Strip placeholder values the LLM copies from the schema example
        _placeholder_prec = {"Case Name v State (Year)", "case name v state (year)"}
        _placeholder_claim = {"claim 1", "claim 2"}
        _placeholder_stat = {"BNS Section 303", "Article 21"}
        if "precedents_cited" in data and isinstance(data["precedents_cited"], list):
            data["precedents_cited"] = [
                p for p in data["precedents_cited"]
                if p.strip().lower() not in {x.lower() for x in _placeholder_prec}
            ]
        if "claims" in data and isinstance(data["claims"], list):
            data["claims"] = [
                c for c in data["claims"]
                if c.strip().lower() not in {x.lower() for x in _placeholder_claim}
            ]
        if "statutes_cited" in data and isinstance(data["statutes_cited"], list):
            data["statutes_cited"] = [
                s for s in data["statutes_cited"]
                if s.strip() not in _placeholder_stat
            ]
        # Normalise rebuttals
        if "rebuttals" not in data:
            for alt in ("rebuttal", "counter_arguments", "rebuttals_list"):
                if alt in data:
                    v = data.pop(alt)
                    data["rebuttals"] = ([v] if isinstance(v, str) else (v if isinstance(v, list) else [])) if v else []
                    break
        return data


class JudgeScore(BaseModel):
    round_number: int = 1
    prosecution_strength: int = Field(
        default=5, ge=1, le=10,
        description=(
            "Strength of the prosecution's CASE on the merits this round (likelihood of a liable "
            "verdict) — not rhetorical polish. A dispositive point against it forces a low score."
        ),
    )
    defence_strength: int = Field(
        default=5, ge=1, le=10,
        description=(
            "Strength of the defence's CASE on the merits this round (likelihood of acquittal) — "
            "not rhetorical polish. A dispositive point in its favour forces a high score."
        ),
    )
    weak_side: Literal["prosecution", "defence", "balanced"] = "balanced"
    uncited_statutes: list[str] = Field(
        default_factory=list,
        description="Statutes the judge believes should have been cited but weren't",
    )
    reasoning: str = ""
    decision: Literal["another_round", "proceed_to_verdict"] = "proceed_to_verdict"
    win_probability: int = Field(
        default=50, ge=0, le=100,
        description=(
            "Running case-strength estimate: % chance prosecution prevails at verdict. "
            "50 = balanced. 90+ = prosecution overwhelming. 10- = acquittal near-certain."
        ),
    )

    @model_validator(mode="before")
    @classmethod
    def _unwrap_nested(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data
        for key in ("judge_score", "JudgeScore", "score", "round_score"):
            if key in data and isinstance(data[key], dict):
                data = data[key]
                break
        # LLM sometimes outputs floats — round to nearest int
        data = dict(data)
        for field in ("prosecution_strength", "defence_strength"):
            v = data.get(field)
            if isinstance(v, float):
                data[field] = round(v)
            elif isinstance(v, str):
                try:
                    data[field] = int(float(v))
                except (ValueError, TypeError):
                    pass
        # Coerce invalid weak_side values to "balanced"
        ws = data.get("weak_side")
        if ws not in ("prosecution", "defence", "balanced"):
            data["weak_side"] = "balanced"
        if "win_probability" in data:
            v = data["win_probability"]
            if isinstance(v, float):
                data["win_probability"] = round(v)
            elif isinstance(v, str):
                try:
                    data["win_probability"] = int(float(v))
                except (ValueError, TypeError):
                    pass
        return data


class CitationAuditResult(BaseModel):
    hallucinated_citations: list[str] = Field(
        default_factory=list,
        description="Citations that do not exist in the corpus",
    )
    verified_citations: list[str] = Field(default_factory=list)
    audit_passed: bool = True
    audit_notes: str = ""


class Verdict(BaseModel):
    ruling: Literal["liable", "not_liable", "inconclusive"] = "inconclusive"
    confidence: int = Field(default=5, ge=1, le=10)
    reasoning: str = ""
    statutes_relied_on: list[str] = Field(default_factory=list)
    precedents_relied_on: list[str] = Field(default_factory=list)
    dissent_notes: str = ""
    disclaimer: str = (
        "This is an AI-generated educational simulation. "
        "It does NOT constitute legal advice. Consult a qualified advocate."
    )

    @model_validator(mode="before")
    @classmethod
    def _unwrap_nested(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data
        for key in ("verdict", "Verdict", "final_verdict"):
            if key in data and isinstance(data[key], dict):
                data = data[key]
                break
        data = dict(data)
        if "confidence" in data and isinstance(data["confidence"], float):
            data["confidence"] = round(data["confidence"])
        return data


def _upsert_scores_by_round(existing: list[dict], new: list[dict]) -> list[dict]:
    """Merge judge scores, replacing any prior score for the same round.

    The default operator.add reducer appends a duplicate row every time the
    Judge re-deliberates a round it has already scored — which is exactly what
    happens when a human rejects the draft verdict at the HITL gate and routing
    sends the graph back to judge_node. Those duplicates then inflate
    win_probability and the verdict's strength averages on every rejection.

    Upsert keeps one score per round (last-write-wins), so a re-deliberation
    REPLACES the round's score instead of stacking on top of it. For the normal
    forward path every round has a distinct round_number, so this behaves
    identically to operator.add.
    """
    merged = list(existing or [])
    for score in (new or []):
        rn = score.get("round_number")
        for i, prev in enumerate(merged):
            if prev.get("round_number") == rn:
                merged[i] = score
                break
        else:
            merged.append(score)
    return merged


class GraphState(TypedDict):
    # Raw facts from user — consumed by Clerk
    facts_raw: str
    # Offence date collected explicitly from UI/CLI (YYYY-MM-DD string); determines BNS vs IPC
    offence_date: str | None
    # Set by Clerk
    case_file: CaseFile
    # Grows each round — list of Argument objects (serialised as dicts for TypedDict)
    round_transcript: Annotated[list[dict], operator.add]
    # Judge scores — one per round (upsert: re-deliberating a round replaces it)
    judge_scores: Annotated[list[dict], _upsert_scores_by_round]
    # Counters and phase tracking
    current_round: int
    current_phase: str  # "intake" | "argue" | "judge" | "audit" | "hitl" | "done"
    # Audit state
    audit_result: dict | None
    audit_passed: bool
    # HITL
    hitl_approved: bool
    # Final verdict
    verdict: dict | None
    # Error passthrough
    error: str | None
