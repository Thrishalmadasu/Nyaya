"""LLM factory — selects backend based on MOOT_COURT_LLM env var.

Rate-limit strategy (Groq free tier):
  Primary model:  GROQ_MODEL (default llama-3.3-70b-versatile, 100K TPD)
  Judge model:    GROQ_JUDGE_MODEL (default openai/gpt-oss-120b, 200K TPD)
  Fallback model: GROQ_FALLBACK_MODEL (default llama-3.1-8b-instant, 500K TPD)

The Judge (round scoring + final verdict) runs a stronger reasoning model than
the advocates: it adjudicates the whole trial, and the judge-as-generator gap is
where verdict quality is won or lost. It also draws on a *separate* Groq free-tier
quota bucket, so Judge calls don't compete with advocate calls for the primary
model's daily token budget.

On RateLimitError the structured_llm wrapper retries after a short wait, then
switches that model to the fallback for the rest of the session. Fallback state
is tracked per-primary-model so the Judge and advocate models trip independently.
"""
from __future__ import annotations

import os
import re
import time
import logging
from typing import Any, Type

from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv()

_LLM_BACKEND = os.getenv("MOOT_COURT_LLM", "groq").lower()
_PRIMARY_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
_FALLBACK_MODEL = os.getenv("GROQ_FALLBACK_MODEL", "llama-3.1-8b-instant")
# Stronger model for the Judge (scoring + verdict). See module docstring.
JUDGE_MODEL = os.getenv("GROQ_JUDGE_MODEL", "openai/gpt-oss-120b")

# Primary model names that have hit a long rate-limit and switched to the
# higher-limit fallback for the rest of the session. Keyed by model so the Judge
# and advocate models fall back independently rather than one tripping the other.
_fallback_active: set[str] = set()

log = logging.getLogger(__name__)


# Longest we will wait on the primary model before switching to the
# higher-limit fallback. Per-minute token limits reset within seconds, so short
# waits are honoured on the 70B primary to keep argument/verdict quality high;
# only a long wait (daily-quota exhaustion) is worth the downgrade.
_MAX_PRIMARY_WAIT = 25.0


def _make_groq(model: str):
    from langchain_groq import ChatGroq
    return ChatGroq(
        model=model,
        api_key=os.getenv("GROQ_API_KEY"),
        temperature=0.3,
        max_retries=0,  # retries/back-off are handled in _RateLimitAwareChain
    )


def _retry_after_seconds(exc: Exception) -> float | None:
    """Groq's actual back-off hint: the Retry-After header, else the
    'try again in 7.5s' phrase in the error body. None if neither is present."""
    response = getattr(exc, "response", None)
    if response is not None:
        header = response.headers.get("retry-after")
        if header:
            try:
                return float(header)
            except ValueError:
                pass
    match = re.search(r"try again in ([\d.]+)\s*s", str(exc))
    return float(match.group(1)) if match else None


def get_llm():
    if _LLM_BACKEND == "groq":
        model = _FALLBACK_MODEL if _PRIMARY_MODEL in _fallback_active else _PRIMARY_MODEL
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
    """Wraps a structured-output chain and retries with fallback on 429.

    ``model`` selects the primary Groq model for this chain (defaults to
    GROQ_MODEL). Fallback state is tracked per-model in ``_fallback_active``, so
    a chain on the Judge model and a chain on the advocate model switch to the
    fallback independently — each has its own Groq quota bucket.
    """

    def __init__(self, schema: Type[BaseModel], model: str | None = None):
        self._schema = schema
        self._primary = model or _PRIMARY_MODEL
        self._chain = self._build()

    def _build(self) -> Any:
        model = _FALLBACK_MODEL if self._primary in _fallback_active else self._primary
        llm = _make_groq(model)
        return llm.with_structured_output(self._schema, method="json_mode")

    def invoke(self, messages: list, **kwargs) -> Any:
        from groq import RateLimitError

        last_exc: Exception | None = None
        for attempt in range(4):
            try:
                return self._chain.invoke(messages, **kwargs)
            except RateLimitError as exc:
                last_exc = exc
                wait = _retry_after_seconds(exc)
                if wait is None:
                    wait = 4.0 * (attempt + 1)  # no hint — gentle linear back-off

                if wait > _MAX_PRIMARY_WAIT and self._primary not in _fallback_active:
                    # A long wait means this model's daily quota is spent.
                    # Switch to the higher-limit fallback and retry at once
                    # rather than stall the demo for a minute or more.
                    log.warning(
                        "%s rate-limited for ~%.0fs — switching to fallback model (%s).",
                        self._primary, wait, _FALLBACK_MODEL,
                    )
                    _fallback_active.add(self._primary)
                    self._chain = self._build()
                    continue

                wait = min(wait, _MAX_PRIMARY_WAIT)
                log.warning("Rate limit — waiting %.1fs (Groq retry-after) before retry.", wait)
                time.sleep(wait + 0.3)

        raise last_exc  # type: ignore[misc]


def reset_fallback() -> None:
    """Force the next LLM calls to use primary models regardless of prior rate limits."""
    _fallback_active.clear()


def get_structured_llm(schema: Type[BaseModel], model: str | None = None):
    """Return a structured-output chain with automatic rate-limit fallback.

    ``model`` overrides the primary Groq model for this chain (e.g. the Judge
    model); it is ignored for non-Groq backends, which the free-tier juggling is
    not aimed at. Uses JSON mode to avoid Groq's strict tool-calling validation.
    """
    if _LLM_BACKEND == "groq":
        return _RateLimitAwareChain(schema, model=model)
    llm = get_llm()
    return llm.with_structured_output(schema)


def get_judge_structured_llm(schema: Type[BaseModel]):
    """Structured-output chain for the Judge (round scoring + final verdict),
    running the stronger JUDGE_MODEL. See module docstring for the rationale."""
    return get_structured_llm(schema, model=JUDGE_MODEL)


def get_llm_with_tools(tools: list):
    return get_llm().bind_tools(tools)
