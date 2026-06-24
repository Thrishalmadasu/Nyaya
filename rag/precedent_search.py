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


def _citation_party_tokens(citation: str) -> list[str]:
    """Distinctive party surnames from a full-form citation, for match-checking.

    Drops the '(Year)', the 'v/vs' separator and generic state/role words so the
    tokens that remain actually identify the case — the same idea as the
    scraper's content validator, kept local to avoid a dependency on ingestion.
    """
    core = re.sub(r"\(\d{4}\)", "", citation)
    stop = {
        "state", "of", "union", "india", "the", "and", "ors", "anr", "others",
        "public", "prosecutor", "cbi", "secretary", "home", "govt", "government",
        "versus", "vs", "v",
    }
    return [
        w for w in re.split(r"[^A-Za-z0-9]+", core)
        if len(w) >= 4 and w.lower() not in stop
    ]


def verify_precedent_online(citation: str) -> bool | None:
    """Best-effort web check that a cited case actually exists.

    Returns ``True`` when Tavily results plausibly describe the cited case,
    ``False`` when a search ran but nothing matched (suspected fabrication), and
    ``None`` when no check could be made (no ``TAVILY_API_KEY`` or an API error)
    — so callers can tell 'refuted' apart from 'unchecked'.

    A match requires a single result whose **title** carries a distinctive
    party surname and whose text carries the citation's year (when it has one).
    Matching on the result title — not body text — is what keeps a generic word
    in a fabricated name ("Totally Fake v Nobody") from latching onto unrelated
    judgments: court-result titles reliably read "X vs Y on <date>", so a real
    party name surfaces there while a noise word does not.
    """
    api_key = os.getenv("TAVILY_API_KEY", "")
    if not api_key:
        return None

    party_tokens = _citation_party_tokens(citation)
    if not party_tokens:
        # Nothing distinctive to confirm against — don't claim a verdict.
        return None

    year_m = re.search(r"\((\d{4})\)|\b(\d{4})\b", citation)
    year = next((g for g in (year_m.groups() if year_m else []) if g), None)

    safe_query = _sanitize_query(citation)
    try:
        from tavily import TavilyClient

        client = TavilyClient(api_key=api_key)
        results = client.search(
            query=(
                f"Indian court case {safe_query} "
                "site:indiankanoon.org OR site:main.sci.gov.in"
            ),
            max_results=5,
            search_depth="advanced",
        )
    except Exception as exc:
        logger.warning("Tavily precedent verification failed for %r: %s", citation, exc)
        return None

    hits = results.get("results", [])
    if not hits:
        return False

    tokens_low = [t.lower() for t in party_tokens]
    for r in hits:
        title = r.get("title", "").lower()
        full = f"{title} {r.get('content', '')}".lower()
        surname_ok = any(tok in title for tok in tokens_low)
        year_ok = year is None or year in full
        if surname_ok and year_ok:
            return True
    return False


def format_precedents_for_llm(results: list[dict]) -> str:
    if not results:
        return "No precedents found."
    lines = []
    for r in results:
        src = r.get("url") or r.get("source", "")
        suffix = f"\n  Source: {src}" if src else ""
        lines.append(f"• {r.get('title', 'Unknown')}\n  {r.get('content', '')}{suffix}")
    return "\n\n".join(lines)
