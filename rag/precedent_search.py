"""Precedent retrieval: local corpus first, Tavily internet search as fallback.

Advocate agents call :func:`get_precedents`. It returns landmark-case context
from the locally embedded precedent corpus when available, and only reaches out
to the Tavily web API when the corpus yields nothing (or no API key is set).
"""
from __future__ import annotations

import logging
import os
import re

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Single content cap (no double truncation). Trimmed sentence-aware in _shorten.
_CONTENT_CHARS = 600


def _shorten(text: str, limit: int = _CONTENT_CHARS) -> str:
    """Truncate at a sentence/word boundary near ``limit`` rather than mid-word."""
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    cut = text[:limit]
    # Prefer the last sentence end, else the last space, within the window.
    boundary = max(cut.rfind(". "), cut.rfind("\n"))
    if boundary < limit * 0.5:
        boundary = cut.rfind(" ")
    if boundary > 0:
        cut = cut[:boundary]
    return cut.rstrip() + "…"


def _sanitize_query(query: str) -> str:
    """Strip characters that could break out of the Tavily ``site:`` filter."""
    # Drop quotes, site:/filetype: operators and stray boolean punctuation.
    cleaned = re.sub(r'["\']', " ", query or "")
    cleaned = re.sub(r"\b(site|filetype|inurl|intitle)\s*:", " ", cleaned, flags=re.I)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:200]


def _local_precedents(query: str, max_results: int) -> list[dict]:
    """Pull precedent chunks from the embedded corpus, shaped like search hits."""
    try:
        from rag.retriever import retrieve_precedents
    except Exception as exc:  # pragma: no cover - import guard
        logger.warning("precedent retriever unavailable: %s", exc)
        return []

    try:
        chunks = retrieve_precedents(query, top_k=max_results)
    except Exception as exc:
        logger.warning("local precedent retrieval failed: %s", exc)
        return []

    return [
        {
            "title": c.section_title or "Indian precedent",
            "url": "",  # local corpus has no canonical URL on the chunk
            "content": _shorten(c.text),
            "source": "corpus",
        }
        for c in chunks
    ]


def _tavily_precedents(query: str, max_results: int) -> list[dict]:
    """Search the open web for precedents via Tavily. Returns [] on any failure."""
    api_key = os.getenv("TAVILY_API_KEY", "")
    if not api_key:
        logger.info("TAVILY_API_KEY not set — skipping internet precedent fallback")
        return []

    safe_query = _sanitize_query(query)
    try:
        from tavily import TavilyClient

        client = TavilyClient(api_key=api_key)
        results = client.search(
            query=(
                f"Indian court case precedent {safe_query} "
                "site:indiankanoon.org OR site:main.sci.gov.in"
            ),
            max_results=max_results,
            search_depth="advanced",
        )
        hits = [
            {
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "content": _shorten(r.get("content", "")),
                "source": "tavily",
            }
            for r in results.get("results", [])
        ]
        if not hits:
            logger.info("Tavily returned no precedents for %r", safe_query)
        return hits
    except Exception as exc:
        logger.warning("Tavily precedent search failed: %s", exc)
        return []


def get_precedents(query: str, max_results: int = 5) -> list[dict]:
    """Return precedent context: local corpus first, Tavily fallback.

    Each result is a ``{title, url, content, source}`` dict. The ``source`` key
    records whether it came from the local ``corpus`` or ``tavily`` so callers
    and logs can tell them apart. Returns ``[]`` only when both sources are
    empty/unavailable.
    """
    local = _local_precedents(query, max_results)
    if local:
        return local

    logger.info("no local precedents for %r — falling back to internet search", query)
    return _tavily_precedents(query, max_results)


# Backwards-compatible alias (older callers / tests may import search_precedents).
search_precedents = get_precedents


def format_precedents_for_llm(results: list[dict]) -> str:
    if not results:
        return "No precedents found."
    lines = []
    for r in results:
        src = r.get("url") or r.get("source", "")
        suffix = f"\n  Source: {src}" if src else ""
        lines.append(f"• {r.get('title', 'Unknown')}\n  {r.get('content', '')}{suffix}")
    return "\n\n".join(lines)
