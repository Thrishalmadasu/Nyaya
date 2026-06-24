"""Master ingestion script: download → scrape → chunk → embed → verify.

Run:
    python -m ingestion.build_corpus
    python -m ingestion.build_corpus --force   # re-download everything
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main(force: bool = False) -> None:
    print("=" * 60)
    print("AI Moot Court — Corpus Builder")
    print("=" * 60)

    # Step 1: Download statute PDFs
    print("\n[1/4] Downloading statute PDFs...")
    from ingestion.download_statutes import download_all, STATUTE_SOURCES

    downloaded = download_all(force=force)
    print(f"      → {len(downloaded)}/{len(STATUTE_SOURCES)} statutes ready")

    # Step 2: Scrape precedents
    print("\n[2/4] Scraping landmark cases from Indian Kanoon...")
    from ingestion.scrape_kanoon import scrape_all, LANDMARK_CASES, check_corpus_health

    summary = scrape_all(force=force)
    on_disk = len(summary["scraped"]) + len(summary["skipped"])
    print(f"      → {on_disk}/{summary['total']} precedents present "
          f"({len(summary['scraped'])} new, {len(summary['rejected'])} rejected, "
          f"{len(summary['missing'])} missing)")

    # Health check: loudly flag any configured case that is absent or whose
    # on-disk header doesn't match — so a corrupt/stale corpus can't pass silently.
    problems = check_corpus_health()
    if problems:
        print(f"  ⚠ CORPUS HEALTH: {len(problems)} precedent issue(s) — these cases will NOT be trustworthy:")
        for slug, reason in problems:
            print(f"      • {slug}: {reason}")

    # Step 3: Chunk everything
    print("\n[3/4] Chunking statutes and precedents...")
    from ingestion.chunker import chunk_statute_pdf, overview_to_chunk
    from ingestion.download_statutes import STATUTE_SOURCES

    all_chunks = []

    # Chunk statute files (PDF or TXT)
    from ingestion.chunker import chunk_statute_txt
    statutes_dir = Path(__file__).parent.parent / "corpus" / "statutes"
    for entry in STATUTE_SOURCES:
        statute_path = statutes_dir / entry["filename"]
        if not statute_path.exists():
            print(f"  [skip] {entry['filename']} not found")
            continue
        if statute_path.suffix == ".pdf":
            chunks = chunk_statute_pdf(
                pdf_path=statute_path,
                source_act=entry["name"],
                code_regime=entry["code_regime"],
                year=entry["year"],
            )
        else:
            chunks = chunk_statute_txt(
                txt_path=statute_path,
                source_act=entry["name"],
                code_regime=entry["code_regime"],
                year=entry["year"],
            )
        all_chunks.extend(chunks)
        print(f"  {entry['name']}: {len(chunks)} chunks")

    # Embed one concise overview document per precedent case (not 24 windows of
    # the raw judgment) — see ingestion/precedent_overview.py for the rationale.
    overviews_dir = Path(__file__).parent.parent / "corpus" / "precedents_overviews"
    overview_files = sorted(overviews_dir.glob("*.txt")) if overviews_dir.exists() else []
    if not overview_files:
        print("  ⚠ No precedent overviews found in corpus/precedents_overviews/ — "
              "run `python -m ingestion.precedent_overview` first. Skipping precedents.")
    for txt_path in overview_files:
        all_chunks.append(overview_to_chunk(txt_path))

    print(f"  Precedents ({len(overview_files)} overviews): {sum(1 for c in all_chunks if c.metadata.get('code_regime') == 'PRECEDENT')} documents")
    print(f"      → Total chunks: {len(all_chunks)}")

    # Step 4: Embed and upsert
    print("\n[4/4] Embedding and upserting to Chroma...")
    from ingestion.embedder import upsert_chunks, delete_acts

    # Clear existing chunks for every act we just re-chunked, so a rebuild is a
    # true replacement. Chunk IDs derive from (source_act, section_id, text), so
    # without this an act re-parsed into different sections would stack new
    # chunks on top of the stale ones (e.g. clean BNS added beside old Para-junk).
    acts_to_refresh = sorted({c.metadata.get("source_act") for c in all_chunks if c.metadata.get("source_act")})
    if acts_to_refresh:
        print(f"      clearing existing chunks for: {', '.join(acts_to_refresh)}")
        delete_acts(acts_to_refresh, verbose=True)

    n_upserted = upsert_chunks(all_chunks, verbose=True)
    print(f"      → {n_upserted} chunks upserted to Chroma")

    # Verification
    print("\n[verify] Running a test query...")
    from rag.retriever import retrieve

    test_chunks = retrieve("theft punishment", code_regime="BNS", top_k=3)
    if test_chunks:
        print(f"  ✓ Retrieved {len(test_chunks)} chunks for 'theft punishment'")
        for c in test_chunks[:2]:
            print(f"    — {c.source_act}: {c.section_id}: {c.section_title[:60]}")
    else:
        print("  ✗ No chunks retrieved — check embedding and Chroma setup")

    print("\n" + "=" * 60)
    print(f"Corpus build complete: {n_upserted} total chunks in Chroma")
    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build the AI Moot Court legal corpus")
    parser.add_argument("--force", action="store_true", help="Re-download all files")
    args = parser.parse_args()
    main(force=args.force)
