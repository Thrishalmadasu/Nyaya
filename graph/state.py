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
    prosecution_strength: int = Field(default=5, ge=1, le=10)
    defence_strength: int = Field(default=5, ge=1, le=10)
    weak_side: Literal["prosecution", "defence", "balanced"] = "balanced"
    uncited_statutes: list[str] = Field(
        default_factory=list,
        description="Statutes the judge believes should have been cited but weren't",
    )
    reasoning: str = ""
    decision: Literal["another_round", "proceed_to_verdict"] = "proceed_to_verdict"

    @model_validator(mode="before")
    @classmethod
    def _unwrap_nested(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data
        for key in ("judge_score", "JudgeScore", "score", "round_score"):
            if key in data and isinstance(data[key], dict):
                data = data[key]
                break
        # LLM sometimes outputs floats (e.g. 7.5) — round to nearest int
        data = dict(data)
        for field in ("prosecution_strength", "defence_strength"):
            if field in data and isinstance(data[field], float):
                data[field] = round(data[field])
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


class GraphState(TypedDict):
    # Raw facts from user — consumed by Clerk
    facts_raw: str
    # Set by Clerk
    case_file: CaseFile
    # Grows each round — list of Argument objects (serialised as dicts for TypedDict)
    round_transcript: Annotated[list[dict], operator.add]
    # Judge scores — one per round
    judge_scores: Annotated[list[dict], operator.add]
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
