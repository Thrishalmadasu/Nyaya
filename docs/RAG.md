# RAG & Ingestion Pipeline

How the AI Moot Court turns Indian statutes and precedents into a searchable
corpus, and how retrieval feeds the advocate agents. This is the authoritative
description of the chunking strategy and metadata schema.

## Overview

```
download (statutes + precedents)  ->  chunk  ->  embed  ->  ChromaDB  ->  retrieve
   ingestion/download_statutes.py     chunker.py  embedder.py   chroma_db/   rag/retriever.py
   ingestion/scrape_kanoon.py
```

- **Vector store:** ChromaDB, local persistent at `chroma_db/` (gitignored — each
  machine builds or copies it).
- **Embeddings:** `sentence-transformers/all-MiniLM-L6-v2` (384-dim), cosine distance.
- **Collection:** `indian_law`, one row per chunk.

Build it with `python -m ingestion.build_corpus`.

## Data sources

All statutes are fetched as **clean English full text from Indian Kanoon**
(`type: "html"` in `STATUTE_SOURCES`), then parsed to plain text.

| Act | Regime | Source |
|-----|--------|--------|
| Bharatiya Nyaya Sanhita (BNS) 2023 | BNS | indiankanoon.org/doc/149679501 |
| Bharatiya Nagarik Suraksha Sanhita (BNSS) 2023 | BNS | indiankanoon.org/doc/91117739 |
| Bharatiya Sakshya Adhiniyam (BSA) 2023 | BNS | indiankanoon.org/doc/70224818 |
| Indian Penal Code (IPC) 1860 | IPC | indiankanoon.org/doc/1569253 |
| Code of Criminal Procedure (CrPC) 1973 | IPC | indiankanoon.org/doc/1684044 |
| Constitution of India | CONST | indiankanoon.org/doc/237570 |

> **Why not the official egazette PDFs?** The egazette BNS/BNSS/BSA PDFs are
> bilingual Hindi/English two-column scans. PyMuPDF cannot recover section
> boundaries from them, so the chunker fell back to blind windows: the BNS
> corpus held 656 junk pseudo-sections (`Para N`) with Hindi gazette headers as
> titles, and the real murder section was not retrievable. The Indian Kanoon
> pages parse into all real sections, so we use those instead.

## Dual-regime model (why both BNS and IPC are kept)

A crime is tried under the law **in force when the offence was committed**
(Constitution Article 20(1) — no retroactive criminal liability). BNS replaced
IPC only for offences on or after **1 July 2024**; pre-cutover offences are
still adjudicated under IPC. So the corpus keeps **both** codes, and the Clerk
routes by offence date (`agents/clerk.py::_determine_regime`): `>= 2024-07-01 ->
BNS`, else `IPC`. IPC is historical-but-active law here, not stale data.

## Chunking strategy (`ingestion/chunker.py`)

**Statutes — one chunk per section, split when long.**
1. Split the act text on section markers (`^<number>. <Title>`), giving one
   unit per section/article.
2. Skip units under 30 chars (artefacts).
3. If a section body exceeds the window (1500 chars), split it into **overlapping
   sub-chunks** (`_SECTION_WINDOW=1500`, `_SECTION_OVERLAP=200`) rather than
   truncating. Every sub-chunk keeps the **same `section_id` and `section_title`**
   and records a 1-based `part`. (Earlier code truncated at 1500 chars, dropping
   the tail of long provisions.)
4. Each chunk's embedded text leads with identity + keywords:
   `"Section N. <title>. Keywords: <synonyms>. <body>"`.

**Precedents — blind windows.** Court judgments have no sections, so they are
chunked into ~1000-char overlapping windows labelled `Para N` (by design — this
is expected and not a parsing failure).

**Fallback (and its risk).** If section-splitting finds fewer than 10 sections,
the statute path falls back to blind `Para N` windows. This is what silently
masked the broken BNS PDF. After any rebuild, run `python -m tools.inspect_corpus`
— a statute showing `Para` chunks or a section range far above its real size has
fallen back and needs a better source.

## Metadata schema

Every chunk carries (all stored as strings in Chroma):

| Field | Meaning | Used by |
|-------|---------|---------|
| `source_act` | e.g. `"BNS 2023"`, `"Precedent"` | rebuild (`delete_acts`), display |
| `section_id` | `"Section 103"` / `"Article 21"` / `"Para 4"` | citation lookup, display |
| `section_title` | section heading | embedded text, display |
| `code_regime` | `BNS` / `IPC` / `CONST` / `PRECEDENT` | **retrieval filter** |
| `year` | enactment year | display |
| `part` | sub-chunk index within a section (`"1"`, `"2"`, …) | dedup id, ordering |
| `keywords` | lay synonyms for the offence (comma-joined) | embedded text, transparency |

The chunk id (`embedder.py::_chunk_id`) is an MD5 of
`source_act | section_id | part | text[:80]` — deterministic (re-runs don't
duplicate) and includes `part` so sub-chunks sharing a title prefix don't collide.

## Keyword enrichment (`ingestion/keywords.py`)

Retrieval is dense-vector similarity, so a fact-pattern query ("stealing") can
miss a section titled only "Theft". `keywords_for(title, body)` matches a curated
offence -> lay-synonym table and the matched synonyms are (a) written into the
embedded text and (b) stored in the `keywords` field. It is deterministic — no
LLM at ingest. **To extend:** add a `(triggers, synonyms)` row to
`OFFENCE_SYNONYMS`; `triggers` are statute terms, `synonyms` are everyday words.

## Retrieval (`rag/retriever.py`)

- `retrieve(query, code_regime, top_k=8, include_constitution=False)` runs a
  cosine query filtered to the active regime.
- **Constitution is excluded by default.** Constitutional articles otherwise
  competed in every query (Article 20 surfacing for a murder case). Pass
  `include_constitution=True` to opt them back in; the advocate agents set this
  only when the offence/legal-questions mention constitutional terms.
- **Query construction:** the advocates query with the **offence type** (falling
  back to the legal questions, then the facts). Role/era words like
  "liability prosecution BNS" are dense-retrieval noise — they pull procedural
  and boilerplate sections ahead of the substantive offence.
- `section_exists(citation)` is a deterministic metadata lookup used by the
  Citation Auditor. **Known limitation:** it currently matches on the section
  number only and ignores the act name, so a regime-mismatched citation
  ("BNS Section 302", where 302 exists only in IPC) still validates. Tightening
  this to be regime-aware is tracked as future work.

## Rebuild & verify

```bash
# Full rebuild (download -> chunk -> embed; clears each re-chunked act first)
python -m ingestion.build_corpus

# Health report: per-act section counts, ranges, junk detection
python -m tools.inspect_corpus

# Tests (retrieval tests skip automatically if the corpus is unbuilt)
python -m unittest discover -s tests
```

A healthy corpus shows real section ranges (BNS 1..358, BNSS 1..531, BSA 1..170,
IPC 1..511) and zero `Para` chunks for statutes. Spot-check retrieval with
`retrieve("punishment for murder", code_regime="BNS")` -> BNS Section 103.
