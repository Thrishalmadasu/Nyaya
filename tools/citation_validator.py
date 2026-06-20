"""Deterministic citation validator — does NOT use the LLM."""
from __future__ import annotations

from langchain_core.tools import tool


@tool
def citation_validator_tool(citation: str) -> str:
    """Validate whether a cited statute section actually exists in the legal corpus.

    This is a deterministic check — it queries the Chroma metadata directly.
    Use this for EVERY statute citation in the transcript during the audit phase.

    Args:
        citation: The statute citation to validate (e.g., "BNS Section 103")

    Returns:
        A string: "FOUND" if the section exists in corpus, "NOT FOUND" if it doesn't.
    """
    from rag.retriever import section_exists

    exists = section_exists(citation)
    if exists:
        return f"FOUND: '{citation}' exists in the corpus."
    return f"NOT FOUND: '{citation}' does not exist in the corpus — possible hallucination."
