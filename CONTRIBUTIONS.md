# Team Contributions — Nyāya AI Moot Court

## Team Members

| # | Name | GitHub | Role |
|---|------|--------|------|
| 1 | Suraj Guduru | surajguduru | Project Lead |
| 2 | Sai Venkatesh Alampally | venki1402 | RAG & Agent Engineer |
| 3 | Thrishal Madasu | Thrishalmadasu | Agent & UI Engineer |

---

## Work Division

Each member owns roughly equal portions of: core logic, RAG/tooling, UI, testing, and infrastructure.

---

### Suraj Guduru

**Core — Data Models & Graph Assembly**
- `graph/state.py` — All Pydantic models (CaseFile, Argument, JudgeScore, Verdict, CitationAuditResult) and GraphState TypedDict with LangGraph reducers
- `graph/court.py` — LangGraph StateGraph assembly, HITL interrupt node, `build_graph()` factory
- `agents/judge.py` — Judge scoring node (chain-of-thought schema, prior-round comparison, hard round cap), verdict renderer, compact transcript for token efficiency
- `utils/llm.py` — LLM factory with Groq/Anthropic/Gemini backends, rate-limit fallback chain, `reset_fallback()` for verdict calls

**RAG**
- `rag/retriever.py` — ChromaDB retrieval with code-regime metadata filter, `section_exists()` citation lookup

**App — HITL Gate & Verdict Panel**
- `app.py` (HITL gate, verdict HTML, `_build_fresh_graph()` with full module reload, `_run_pre_hitl`, `_run_post_hitl`)

**Testing & Eval**
- `eval/cases/01_clear_liability.json` — BNS theft case (CCTV + confiscated goods)
- `eval/cases/05_offence_date_routing.json` — pre-July 2024 murder → IPC routing
- `eval/evaluate.py` — eval runner: runs all 5 cases, validates routing + citation checks

**Setup**
- `requirements.txt`, `.env.example`, `.gitignore`, `.streamlit/config.toml`

---

### Sai Venkatesh Alampally

**Core — Prosecution, Auditor & Citation Tools**
- `agents/prosecution.py` — Prosecution advocate node: RAG retrieval, judge-hint context, prior-defence rebuttal injection, structured output
- `agents/auditor.py` — Deterministic citation auditor: collects all cited statutes from full transcript, runs `section_exists()` on each, sets `audit_passed`
- `tools/citation_validator.py` — LangChain Tool wrapping `section_exists()` for use by agents
- `tools/statute_tool.py` — LangChain Tool wrapping RAG retriever, formatted for LLM consumption

**RAG & Ingestion Pipeline**
- `ingestion/download_statutes.py` — Downloads statute PDFs from indiacode.nic.in
- `ingestion/chunker.py` — Section-aware chunker splitting on `Section \d+` regex; preserves section_id + act metadata
- `ingestion/embedder.py` — Embeds chunks with sentence-transformers MiniLM, upserts to Chroma
- `ingestion/build_corpus.py` — Orchestrates: download → chunk → embed → verify
- `corpus/statutes/` — BNS/IPC/Constitution statute text files

**App — Scoreboard & Judge Assessment**
- `app.py` (scoreboard HTML, judge score card, running assessment panel, score trend arrows)

**Testing & Eval**
- `eval/cases/02_clear_acquittal.json` — alibi + exculpatory evidence case
- `eval/cases/04_citation_trap.json` — hallucination trap: advocacy cites "BNS Section 999"

---

### Thrishal Madasu

**Core — Routing, Prompts, Clerk & Defence**
- `graph/edges.py` — Conditional edge functions: `judge_routing` (round cap, env-read inside function), `auditor_routing` (always → HITL), `hitl_routing`
- `agents/prompts.py` — All five system prompts: Clerk (code-regime logic), Prosecution, Defence, Auditor, Judge (strict scoring rubric, differentiation rules, cross-round comparison), Verdict
- `agents/clerk.py` — Intake node: parses facts → CaseFile structured output, determines BNS vs IPC from offence date
- `agents/defence.py` — Defence advocate node: acquittal-focused RAG retrieval, prosecution rebuttal injection, judge-hint context

**RAG & Corpus**
- `rag/precedent_search.py` — Precedent retrieval: local embedded-corpus first, Tavily internet search as fallback; formatted for LLM consumption
- `ingestion/scrape_kanoon.py` — Scrapes landmark cases from Indian Kanoon with content validation (rejects mismatched/stale doc IDs) and a corpus health check
- `corpus/precedents/` — 23 verified landmark Indian case text files (Kesavananda Bharati, Maneka Gandhi, D.K. Basu, Puttaswamy, etc.)

**App — Case Display & Argument Cards**
- `app.py` (case file HTML, argument cards, round headers, pending pulse, audit display, trial progress tracker, conclusion summary panel)
- `cli/run_case.py` — CLI entry point with rich pretty-print output

**Testing & Eval**
- `eval/cases/03_borderline.json` — Circumstantial evidence case; tests multi-round behaviour
- `README.md` — Architecture diagram, setup guide, agent roles, evaluation results, limitations

---

## Ownership Summary

| Area | Suraj | Venkatesh | Thrishal |
|------|-------|-----------|----------|
| Data Models / State | ✅ | | |
| Graph Assembly | ✅ | | |
| Edge Routing | | | ✅ |
| System Prompts | | | ✅ |
| Judge Agent | ✅ | | |
| Prosecution Agent | | ✅ | |
| Defence Agent | | | ✅ |
| Clerk Agent | | | ✅ |
| Auditor Agent | | ✅ | |
| RAG Retriever | ✅ | | |
| Ingestion Pipeline | | ✅ | |
| Statute Corpus | | ✅ | |
| Precedent Corpus | | | ✅ |
| Citation Tools | | ✅ | |
| Precedent Tools | | | ✅ |
| LLM Factory | ✅ | | |
| Streamlit App (structure/HITL/verdict) | ✅ | | |
| Streamlit App (scoreboard/judge cards) | | ✅ | |
| Streamlit App (case display/cards/progress) | | | ✅ |
| CLI | | | ✅ |
| Eval Runner | ✅ | | |
| Eval Cases (01, 05) | ✅ | | |
| Eval Cases (02, 04) | | ✅ | |
| Eval Cases (03) | | | ✅ |
| Setup / Config | ✅ | | |
| README | | | ✅ |
