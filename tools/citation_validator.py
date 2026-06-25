"""Deterministic citation validator — does NOT use the LLM."""
from __future__ import annotations

from langchain_core.tools import tool


@tool
def citation_validator_tool(citation: str, expected_regime: str | None = None) -> str:
    """Validate whether a cited statute section actually exists in the legal corpus.

    This is a deterministic check — it queries the Chroma metadata directly.
    Use this for EVERY statute citation in the transcript during the audit phase.

    The check is act-aware: a citation carrying a code word (e.g. "BNS Section 378")
    is verified against that specific act, so a section that exists in another act
    but not the named one is correctly reported NOT FOUND. When the citation has no
    code word (e.g. a bare "Section 378"), ``expected_regime`` names the act to
    check against.

    Args:
        citation: The statute citation to validate (e.g., "BNS Section 103").
        expected_regime: The case's default code regime (e.g. "BNS" or "IPC"), used
            to resolve the act for citations that carry no explicit code word. If
            omitted, the lookup falls back to act-agnostic matching.

    Returns:
        A string: "FOUND" if the section exists in corpus, "NOT FOUND" if it doesn't.
    """
    from rag.retriever import section_exists

    exists = section_exists(citation, expected_regime=expected_regime)
    if exists:
        return f"FOUND: '{citation}' exists in the corpus."
    return f"NOT FOUND: '{citation}' does not exist in the corpus — possible hallucination."
