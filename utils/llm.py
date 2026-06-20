"""LLM factory — selects backend based on MOOT_COURT_LLM env var.

Rate-limit strategy (Groq free tier):
  Primary model:  GROQ_MODEL (default llama-3.3-70b-versatile, 100K TPD)
  Fallback model: GROQ_FALLBACK_MODEL (default llama-3.1-8b-instant, 500K TPD)

On RateLimitError the structured_llm wrapper retries once after a short wait,
then automatically switches to the fallback model for the rest of the session.
"""
from __future__ import annotations

import os
import time
import logging
from typing import Any, Type

from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv()

_LLM_BACKEND = os.getenv("MOOT_COURT_LLM", "groq").lower()
_PRIMARY_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
_FALLBACK_MODEL = os.getenv("GROQ_FALLBACK_MODEL", "llama-3.1-8b-instant")

# Session-level flag: switch permanently to fallback after first rate-limit hit
_using_fallback: bool = False

log = logging.getLogger(__name__)


def _make_groq(model: str):
    from langchain_groq import ChatGroq
    return ChatGroq(
        model=model,
        api_key=os.getenv("GROQ_API_KEY"),
        temperature=0.3,
    )


def get_llm():
    global _using_fallback
    if _LLM_BACKEND == "groq":
        model = _FALLBACK_MODEL if _using_fallback else _PRIMARY_MODEL
        return _make_groq(model)
    elif _LLM_BACKEND == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model=os.getenv("MOOT_COURT_MODEL", "claude-sonnet-4-6"),
            api_key=os.getenv("ANTHROPIC_API_KEY"),
            temperature=0.3,
        )
    elif _LLM_BACKEND == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model=os.getenv("GEMINI_MODEL", "gemini-2.0-flash"),
            google_api_key=os.getenv("GOOGLE_API_KEY"),
            temperature=0.3,
        )
    else:
        raise ValueError(f"Unknown LLM backend: {_LLM_BACKEND!r}")


class _RateLimitAwareChain:
    """Wraps a structured-output chain and retries with fallback on 429."""

    def __init__(self, schema: Type[BaseModel]):
        self._schema = schema
        self._chain = self._build()

    def _build(self) -> Any:
        global _using_fallback
        model = _FALLBACK_MODEL if _using_fallback else _PRIMARY_MODEL
        llm = _make_groq(model)
        return llm.with_structured_output(self._schema, method="json_mode")

    def invoke(self, messages: list, **kwargs) -> Any:
        global _using_fallback
        from groq import RateLimitError

        try:
            return self._chain.invoke(messages, **kwargs)
        except RateLimitError as exc:
            if _using_fallback:
                # Already on fallback — nothing left to try
                raise

            log.warning(
                "Rate limit on primary model (%s); switching to fallback (%s) for this session.",
                _PRIMARY_MODEL, _FALLBACK_MODEL,
            )
            _using_fallback = True
            self._chain = self._build()

            # Brief pause to let any per-minute window breathe
            time.sleep(2)
            return self._chain.invoke(messages, **kwargs)


def reset_fallback() -> None:
    """Force the next LLM call to use the primary model regardless of prior rate limits."""
    global _using_fallback
    _using_fallback = False


def get_structured_llm(schema: Type[BaseModel]):
    """Return a structured-output chain with automatic rate-limit fallback.

    Uses JSON mode to avoid Groq's strict tool-calling validation.
    Non-Groq backends use the default function_calling method.
    """
    if _LLM_BACKEND == "groq":
        return _RateLimitAwareChain(schema)
    llm = get_llm()
    return llm.with_structured_output(schema)


def get_llm_with_tools(tools: list):
    return get_llm().bind_tools(tools)
