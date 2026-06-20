"""LangChain tool: search for Indian legal precedents via Tavily."""
from __future__ import annotations

from langchain_core.tools import tool


@tool
def precedent_search_tool(query: str) -> str:
    """Search for relevant Indian court case precedents.

    Use this tool to find real past judgments that support your legal argument.
    Always verify the case name and year before citing.

    Args:
        query: Legal issue or case type to search (e.g., "theft conviction Supreme Court India")

    Returns:
        List of relevant cases with titles, excerpts, and source URLs.
    """
    from rag.precedent_search import search_precedents, format_precedents_for_llm

    results = search_precedents(query=query, max_results=5)
    return format_precedents_for_llm(results)
