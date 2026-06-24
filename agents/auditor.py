"""Bias & Citation Integrity Auditor — validates every citation deterministically.

Statutes are checked by exact metadata lookup against the corpus. Case citations
(precedents) are checked by name-token match against the local precedent corpus
first; anything not matched there is put to a Tavily web check so a real case the
small local corpus doesn't hold isn't wrongly branded a fabrication.
"""
from __future__ import annotations

from graph.state import CitationAuditResult, GraphState
from rag.precedent_search import verify_precedent_online
from rag.retriever import precedent_exists, section_exists


def _collect_statutes(transcript: list[dict]) -> list[str]:
    """Extract every unique statute citation from the trial transcript."""
    cited: set[str] = set()
    for argument in transcript:
        for s in argument.get("statutes_cited", []):
            if s and s.strip():
                cited.add(s.strip())
    return list(cited)


def _collect_precedents(transcript: list[dict]) -> list[str]:
    """Extract every unique case (precedent) citation from the transcript."""
    cited: set[str] = set()
    for argument in transcript:
        for p in argument.get("precedents_cited", []):
            if p and p.strip():
                cited.add(p.strip())
    return list(cited)


def auditor_node(state: GraphState) -> dict:
    """LangGraph node: deterministically validate all citations against the corpus."""
    transcript = state.get("round_transcript", [])
    case_file = state.get("case_file")
    # The case's code regime is the act a bare "Section 303" defaults to; an
    # explicit code word in the citation (e.g. "IPC Section 378") still wins.
    if isinstance(case_file, dict):
        expected_regime = case_file.get("code_regime")
    else:
        expected_regime = getattr(case_file, "code_regime", None)

    # ── Statutes: exact corpus lookup, against the act the citation names ───
    all_statutes = _collect_statutes(transcript)
    verified_statutes: list[str] = []
    hallucinated_statutes: list[str] = []
    for citation in all_statutes:
        ok = section_exists(citation, expected_regime=expected_regime)
        (verified_statutes if ok else hallucinated_statutes).append(citation)

    # ── Precedents: local corpus, then Tavily fallback ─────────────────────
    all_precedents = _collect_precedents(transcript)
    verified_precedents: list[str] = []
    unverified_precedents: list[str] = []
    refuted_precedents: list[str] = []   # web check ran and found nothing → suspected fabrication
    for citation in all_precedents:
        if precedent_exists(citation):
            verified_precedents.append(citation)
            continue
        web = verify_precedent_online(citation)
        if web is True:
            verified_precedents.append(citation)
        else:
            unverified_precedents.append(citation)
            if web is False:  # actively searched and not found (None = couldn't check)
                refuted_precedents.append(citation)

    # A fabricated case is as damaging as a fabricated statute, so a refuted
    # precedent fails the audit. Cases merely unchecked (no Tavily key / API
    # error) do NOT fail it — we surface them for the human rather than guess.
    passed = not hallucinated_statutes and not refuted_precedents

    notes = (
        f"Checked {len(all_statutes)} statute citation(s): "
        f"{len(verified_statutes)} verified, {len(hallucinated_statutes)} not found in corpus. "
        f"Checked {len(all_precedents)} case citation(s): "
        f"{len(verified_precedents)} verified, {len(unverified_precedents)} unverified."
    )
    if hallucinated_statutes:
        notes += f" Suspected hallucinated statutes: {hallucinated_statutes}."
    if refuted_precedents:
        notes += f" Cases not found in corpus or online (likely fabricated): {refuted_precedents}."
    unchecked = [p for p in unverified_precedents if p not in refuted_precedents]
    if unchecked:
        notes += (
            f" Cases not in local corpus and not web-verified — reviewer should confirm: {unchecked}."
        )

    audit = CitationAuditResult(
        hallucinated_citations=hallucinated_statutes,
        verified_citations=verified_statutes,
        verified_precedents=verified_precedents,
        unverified_precedents=unverified_precedents,
        audit_passed=passed,
        audit_notes=notes,
    )

    # Always set current_phase to "hitl" regardless of audit outcome.
    # The original "argue" value triggered an infinite re-argue loop:
    # LLM re-generated citations → new hallucinations → auditor failed again.
    return {
        "audit_result": audit.model_dump(),
        "audit_passed": passed,
        "current_phase": "hitl",
    }
