"""Read-only health report for the RAG corpus.

Run:
    python -m tools.inspect_corpus

Prints, per source act: chunk count, distinct sections, numeric range, and the
number of fallback "Para" chunks (a sign the section-aware chunker failed and
fell back to blind windows — how the old gazette-PDF BNS looked). Use it after a
rebuild to confirm each statute parsed into real sections, not junk.
"""
from __future__ import annotations

import re
from collections import defaultdict

from rag.retriever import _get_collection

# Rough real-world section counts, for a sanity flag only (not authoritative).
EXPECTED = {
    "BNS 2023": 358,
    "BNSS 2023": 531,
    "BSA 2023": 170,
    "IPC 1860": 511,
}


def main() -> None:
    col = _get_collection()
    total = col.count()
    if total == 0:
        print("Corpus is empty — run `python -m ingestion.build_corpus`.")
        return

    rows = col.get(include=["metadatas"], limit=total)["metadatas"]

    chunks = defaultdict(int)
    sections = defaultdict(set)
    para_junk = defaultdict(int)
    numbers = defaultdict(set)
    for m in rows:
        act = m.get("source_act", "?")
        sid = str(m.get("section_id", ""))
        chunks[act] += 1
        sections[act].add(sid)
        if sid.startswith("Para"):
            para_junk[act] += 1
        num = re.search(r"(\d+)", sid)
        if num:
            numbers[act].add(int(num.group(1)))

    print(f"Total chunks: {total}\n")
    print(f"{'ACT':24}{'chunks':>8}{'sections':>10}{'range':>13}{'Para-junk':>11}  flag")
    print("-" * 74)
    for act in sorted(chunks):
        nums = numbers[act]
        rng = f"{min(nums)}..{max(nums)}" if nums else "-"
        junk = para_junk[act]
        flag = ""
        if act == "Precedent":
            # Precedents are intentionally windowed into "Para" chunks (court
            # judgments have no sections), so Para chunks here are expected.
            flag = ""
        elif junk:
            flag = "JUNK (statute fell back to blind windows)"
        elif act in EXPECTED and nums:
            # distinct numeric sections shouldn't wildly exceed the real count
            if max(nums) > EXPECTED[act] * 1.2:
                flag = f"numbers exceed expected ~{EXPECTED[act]}"
        print(f"{act:24}{chunks[act]:>8}{len(sections[act]):>10}{rng:>13}{junk:>11}  {flag}")


if __name__ == "__main__":
    main()
