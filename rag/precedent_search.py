"""Tavily-based internet search for Indian legal precedents."""
from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()


def search_precedents(query: str, max_results: int = 5) -> list[dict]:
    """Search for Indian legal precedents using Tavily.

    Returns a list of {title, url, content} dicts.
    Falls back to empty list if Tavily key is not set.
    """
    api_key = os.getenv("TAVILY_API_KEY", "")
    if not api_key:
        return []

    try:
        from tavily import TavilyClient

        client = TavilyClient(api_key=api_key)
        results = client.search(
            query=f"Indian court case precedent {query} site:indiankanoon.org OR site:main.sci.gov.in",
            max_results=max_results,
            search_depth="advanced",
        )
        return [
            {
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "content": r.get("content", "")[:800],
            }
            for r in results.get("results", [])
        ]
    except Exception as exc:
        print(f"[precedent_search] Tavily error: {exc}")
        return []


def format_precedents_for_llm(results: list[dict]) -> str:
    if not results:
        return "No precedents found via internet search."
    lines = []
    for r in results:
        lines.append(f"• {r['title']}\n  {r['content'][:400]}\n  Source: {r['url']}")
    return "\n\n".join(lines)
