"""Generate concise, per-case precedent overviews via the LLM.

Why this exists
---------------
The raw judgments in ``corpus/precedents/*.txt`` are long and front-loaded with
citation metadata (Cites/Cited-by counts, equivalent citations, bench names).
Chunking them at a fixed window made the top retrieval hits that boilerplate —
not the legal principle — and returned several chunks of the *same* case, so an
advocate only ever saw a name + a random mid-judgment fragment and could only
name-drop.

This script distils each judgment into a faithful ~120–200 word overview — case
name, court, year, area of law, the ratio decidendi, and the holding — and
writes it to ``corpus/precedents_overviews/<slug>.txt``. Those overviews are
committed, so the corpus build is deterministic and needs no LLM at runtime or
in CI. ``ingestion.build_corpus`` then embeds **one** overview document per case.

Run (one-time dev step; rides out Groq rate limits via the shared retry/fallback)::

    python -m ingestion.precedent_overview
    python -m ingestion.precedent_overview --force   # regenerate even if present
"""
from __future__ import annotations

import argparse
from pathlib import Path

from pydantic import BaseModel, Field

from ingestion.chunker import _parse_precedent_header
from utils.llm import get_structured_llm

PRECEDENTS_DIR = Path(__file__).parent.parent / "corpus" / "precedents"
OVERVIEWS_DIR = Path(__file__).parent.parent / "corpus" / "precedents_overviews"

# Judgments are long; the principle and holding live near the top and in the
# concluding paragraphs, but the front matter is metadata. Feed a generous slice
# of the judgment — enough to capture the ratio without blowing the token budget.
_MAX_INPUT_CHARS = 14000


class _Overview(BaseModel):
    """Structured precedent overview the LLM is asked to return.

    Field set and ordering mirror the hand-authored seed corpus: the substantive
    parts (key facts, ratio, holding) lead so that if anything is ever trimmed
    downstream, only the trailing metadata is lost. Kept deliberately short —
    the overview is the token guardrail, not a place to dump the judgment.
    """

    key_facts: str = Field(
        description="The material facts that drove the decision, in 1-2 sentences"
    )
    legal_principle: str = Field(
        description="The ratio decidendi / legal principle the case established, in 2-3 sentences"
    )
    holding: str = Field(description="The holding / outcome of the case, in 1 sentence")
    court: str = Field(description="The deciding court, e.g. 'Supreme Court of India'")
    area_of_law: str = Field(description="Area of law, e.g. 'criminal law — sentencing'")


_SYSTEM = (
    "You are a legal research assistant summarising Indian case law. Produce a "
    "faithful, concise overview of the judgment in roughly 120–180 words total. "
    "Do NOT invent facts, holdings, or principles that are not supported by the "
    "text. If the judgment text is incomplete, summarise only what is present. "
    "Keep it dense and to the point — this overview is the only context an "
    "advocate receives about the case, so every sentence must carry legal signal."
)


def _build_overview_text(case_name: str, year: int, ov: _Overview) -> str:
    """Render the structured overview into the committed file format.

    Leads with a ``CASE:`` header so ``_parse_precedent_header`` recovers the
    authoritative title and year at embed time, exactly like the raw judgments.
    Substance (key facts, principle, holding) comes before the court/area
    metadata so a downstream length cap trims only the least important tail.
    """
    return (
        f"CASE: {case_name}\n\n"
        f"KEY FACTS: {ov.key_facts.strip()}\n\n"
        f"PRINCIPLE: {ov.legal_principle.strip()}\n\n"
        f"HOLDING: {ov.holding.strip()}\n\n"
        f"COURT: {ov.court}\n"
        f"AREA: {ov.area_of_law}\n"
    )


def generate_overview(raw_text: str, fallback_name: str) -> str:
    """Distil one raw judgment into the committed overview text."""
    case_name, year = _parse_precedent_header(raw_text, fallback_name)
    llm = get_structured_llm(_Overview)

    from langchain_core.messages import HumanMessage, SystemMessage

    messages = [
        SystemMessage(content=_SYSTEM),
        HumanMessage(
            content=(
                f"Case: {case_name}\n\n"
                f"Judgment text (may be truncated):\n{raw_text[:_MAX_INPUT_CHARS]}\n\n"
                "Summarise the material facts, the legal principle / ratio "
                "decidendi, the holding, the court, and the area of law. Keep the "
                "whole overview to roughly 120–180 words."
            )
        ),
    ]
    ov: _Overview = llm.invoke(messages)
    return _build_overview_text(case_name, year, ov)


def main(force: bool = False) -> None:
    if not PRECEDENTS_DIR.exists():
        raise SystemExit(f"No precedents directory at {PRECEDENTS_DIR} — run the scraper first.")

    OVERVIEWS_DIR.mkdir(parents=True, exist_ok=True)
    raw_files = sorted(PRECEDENTS_DIR.glob("*.txt"))
    if not raw_files:
        raise SystemExit(f"No precedent files in {PRECEDENTS_DIR} — run the scraper first.")

    print(f"Generating overviews for {len(raw_files)} precedent(s) → {OVERVIEWS_DIR}")
    written = skipped = failed = 0

    for raw_path in raw_files:
        dest = OVERVIEWS_DIR / raw_path.name
        if dest.exists() and not force:
            print(f"  [skip] {raw_path.name} (overview exists)")
            skipped += 1
            continue

        raw_text = raw_path.read_text(encoding="utf-8", errors="ignore")
        fallback_name = raw_path.stem.replace("_", " ").title()
        try:
            overview_text = generate_overview(raw_text, fallback_name)
        except Exception as exc:  # noqa: BLE001 — log and keep going on the rest
            print(f"  [FAIL] {raw_path.name}: {exc}")
            failed += 1
            continue

        dest.write_text(overview_text, encoding="utf-8")
        print(f"  [ok]   {raw_path.name}")
        written += 1

    print(f"\nDone: {written} written, {skipped} skipped, {failed} failed.")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate per-case precedent overviews via the LLM")
    parser.add_argument("--force", action="store_true", help="Regenerate even if an overview file exists")
    args = parser.parse_args()
    main(force=args.force)
