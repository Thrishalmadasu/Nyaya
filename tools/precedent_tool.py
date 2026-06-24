"""LangChain tool: retrieve relevant landmark precedents from the corpus.

Mirrors ``tools/statute_tool.py`` but for case law: it wraps
``rag.precedent_search.get_precedents`` (local embedded corpus first, Tavily
web search as fallback) so an LLM-driven agent could fetch on-point precedents
the same way it fetches statutes.

NOTE: the advocates currently call ``get_precedents`` directly inside
``agents/advocate.py`` rather than through this ``@tool`` wrapper, so this is
not bound to any LLM today. It is provided so the precedent path mirrors the
statute/validator tools and is ready for an agentic, tool-calling advocate.
"""
from __future__ import annotations

from langchain_core.tools import tool


@tool
def precedent_retrieval_tool(query: str, max_results: int = 2) -> str:
    """Retrieve relevant Indian landmark precedents for a legal issue.

    Use this tool to find case law that is genuinely on point for the issue you
    are arguing. Cite a precedent only when one of the retrieved cases is
    analogous (prosecution) or distinguishable (defence); if none fits, argue
    from statute and facts alone rather than forcing an ill-fitting citation.

    Args:
        query: The legal issue to search for (e.g., "circumstantial evidence
            murder" or "right of private defence proportionate force").
        max_results: How many distinct precedents to return (kept small — each
            result is a concise per-case overview).

    Returns:
        A formatted list of precedents, each with the case name and a concise
        overview (key facts, legal principle, holding), or a message saying none
        were found.
    """
    from rag.precedent_search import get_precedents, format_precedents_for_llm

    results = get_precedents(query, max_results=max_results)
    if not results:
        return (
            "No relevant precedents found in the corpus or via web search. "
            "Do not cite any case that was not retrieved."
        )
    return format_precedents_for_llm(results)
