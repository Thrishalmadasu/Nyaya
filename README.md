# AI Moot Court — Multi-Agent Adversarial Legal Reasoning

> **Disclaimer:** This system is an AI-powered educational simulation. It does **not** constitute legal advice. All outputs are for academic and research purposes only.

---

## Problem Statement

**User:** Law students, moot-court competitors, legal-aid paralegals, and citizens who need to understand how a case might be reasoned in an Indian court.

**Pain point:** Single-prompt LLMs give one-sided, ungrounded answers and routinely hallucinate Indian statute numbers — which is dangerous in a legal context. There is no accessible tool that (a) argues both sides rigorously, (b) grounds every claim in real statutory text, (c) applies the correct code regime (BNS vs IPC based on offence date), and (d) delivers a judge-adjudicated verdict with a citation-integrity guarantee.

**Solution:** A multi-agent moot court: two opposing advocate agents debate across up to 5 rounds, each retrieving real statute sections from a local RAG corpus. An independent Judge agent scores each round (1–10 per side), maintains a deterministic running **win probability**, and controls the loop — proceeding to verdict early when the case becomes decisively one-sided. A Citation Auditor deterministically validates every cited section against the corpus and surfaces any hallucinated citations to the human reviewer, who must approve before the verdict is finalised.

---

## System Architecture

```
                     ┌─────────────────────────────────────┐
                     │         AI Moot Court Graph          │
                     │          (LangGraph DAG)             │
                     └─────────────────────────────────────┘

Fact Scenario
     │
     ▼
┌─────────┐    ┌───────────────┐    ┌──────────────┐
│  Clerk  │───►│  Prosecution  │───►│   Defence    │
│ (Intake)│    │   Advocate    │    │   Advocate   │
└─────────┘    └───────────────┘    └──────────────┘
                      ▲ loop ◄──────────────┤
                      │                     ▼
                      │               ┌───────────┐
                      └───────────────│   Judge   │──► proceed_to_verdict
                                      └───────────┘
                                            │
                                            ▼
                                     ┌──────────────┐
                                     │   Auditor    │ ◄─── deterministic
                                     │ (Citation    │       citation check
                                     │  Validator)  │
                                     └──────────────┘
                                            │ audit result (pass OR fail)
                                            ▼
                                     ┌──────────────┐
                                     │ Human Review │ (HITL interrupt) ──► reject ──► back to Judge
                                     └──────────────┘
                                            │ approved
                                            ▼
                                     ┌──────────────┐
                                     │   Verdict    │
                                     └──────────────┘
```

### Three Conditional Branches (Decision Points)

| Branch | Trigger | Options |
|--------|---------|---------|
| Code regime | Clerk extracts offence date | BNS (≥ Jul 2024) or IPC (< Jul 2024) |
| Judge routing | After each round | `another_round` (loop) or `proceed_to_verdict` — forced to proceed when win probability reaches ≥ 80 / ≤ 20, or at the `MAX_ROUNDS` cap |
| Auditor routing | After citation audit | Always routes to `hitl`, attaching the audit result (verified + hallucinated citations) for the human reviewer to act on |

---

## Agent Roles

| Agent | Role | Tools | Output Type |
|-------|------|-------|-------------|
| **Clerk** | Parses facts → structured CaseFile; sets code regime deterministically | None | `CaseFile` |
| **Prosecution Advocate** | Argues liability; must cite ≥2 statutes + 1 precedent | `statute_retrieval_tool`, `precedent_search_tool` | `Argument` |
| **Defence Advocate** | Argues exculpation; same citation requirements | `statute_retrieval_tool`, `precedent_search_tool` | `Argument` |
| **Judge** | Scores each side's round strength (1–10), decides loop vs proceed; win probability is then computed deterministically from those scores | None | `JudgeScore` |
| **Auditor** | Validates every cited statute against corpus; blocks hallucinations | `citation_validator_tool` | `CitationAuditResult` |

---

## AI vs Deterministic Steps

| Step | Type | Why |
|------|------|-----|
| Fact parsing (Clerk) | **AI** | Requires natural-language understanding to extract legal questions |
| Code regime selection | **Deterministic** | `offence_date < 2024-07-01 → IPC` — pure Python rule |
| Statute retrieval | **Deterministic** | Chroma vector search with metadata filter |
| Advocacy (Prosecution/Defence) | **AI** | Requires legal reasoning, argument construction, rebuttal |
| Round scoring (Judge) | **AI** | Scores each side's **case strength on the merits** (who is winning, dispositive points weighted heavily) — not rhetorical polish |
| Win probability | **Deterministic** | `50 + (mean prosecution_strength − mean defence_strength) × 7`, clamped to [5, 95] — the running *balance* of the case, computed in Python, never by the LLM |
| Early-exit decision | **Deterministic** | Trial proceeds to verdict once win probability reaches ≥ 80 / ≤ 20, or at the `MAX_ROUNDS` cap |
| Citation validation (Auditor) | **Deterministic** | Exact metadata lookup in Chroma — no LLM involved |
| Verdict rendering | **AI** | Requires synthesis of all rounds into a reasoned conclusion |
| Verdict confidence | **Deterministic** | Derived from the average per-round strength margin `abs(p_avg − d_avg)`, not the LLM's self-reported confidence |
| HITL gate | **Human** | High-stakes output; mandatory review before finalisation |

---

## Scoring, Win Probability & Confidence

The trial's quantitative signals are **deliberately deterministic** — the LLM Judge supplies only the qualitative input (each side's 1–10 *case-strength* score per round, where dispositive points like inadmissible evidence or a complete defence dominate); every number derived from it is computed in Python so the trajectory is reproducible and explainable. The three signals are designed to be mutually consistent: they all flow from the same merit-based strength scores.

- **Win probability** is the running **balance** of the case, not a cumulative tally:
  `win_probability = 50 + (mean prosecution_strength − mean defence_strength) × 7`, clamped to `[5, 95]`.
  Using the *average* margin (rather than summing every round) means a steady modest edge reads as a lean (~60–65%) instead of ballooning to 95% over many rounds — so the headline figure matches the confidence and the verdict's own tone.
- **Early exit:** once win probability reaches **≥ 80 or ≤ 20** (an average margin of ~4.3+), the case is decisively one-sided and the Judge proceeds straight to verdict — no further rounds. `MAX_ROUNDS` is the hard upper bound.
- **Verdict confidence** reflects *how decisive* the win was, scaled from the same **average per-round strength margin** (`abs(p_avg − d_avg)`): roughly 1-point margin → low, 2 → moderate, 3 → high, 4+ → overwhelming. Because both win probability and confidence derive from the average margin, a contested case shows a moderate probability *and* moderate confidence, while a dispositive one shows an extreme probability *and* high confidence.
- **Ruling consistency:** the final verdict is given the running win probability and instructed to rule in the direction it indicates (departures must be justified in the dissent), so the ruling, the probability, and the confidence never contradict one another.

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Agent framework | LangGraph (StateGraph + interrupt) |
| LLM | Groq — `llama-3.3-70b-versatile` (free tier) |
| Vector database | ChromaDB (local persistent, no Docker) |
| Embeddings | `sentence-transformers/all-MiniLM-L6-v2` (free, local) |
| Precedent search | Tavily API (internet search) |
| Observability | LangSmith tracing |
| PDF parsing | PyMuPDF |
| Precedent scraping | BeautifulSoup4 + Indian Kanoon |

---

## Setup & Run

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure environment
```bash
cp .env.example .env
# Fill in GROQ_API_KEY and TAVILY_API_KEY in .env
```

### 3. Build the legal corpus (RAG)
```bash
python -m ingestion.build_corpus
```
This downloads the statute texts (clean English full text from Indian Kanoon), scrapes landmark precedents, chunks them section-by-section, and embeds into ChromaDB. Expect ~15–30 min on first run. After it finishes, verify with `python -m tools.inspect_corpus`.

See **[docs/RAG.md](docs/RAG.md)** for the full ingestion pipeline, chunking strategy, metadata schema, and retrieval behaviour.

### 4. Run a case
```bash
# Interactive (with HITL prompt)
python -m cli.run_case "On 15 August 2024, accused Ravi was caught stealing..."

# From a file
python -m cli.run_case --file path/to/case.txt

# Auto-approve HITL (for demo/eval)
python -m cli.run_case --auto "Fact scenario here..."
```

### 5. Run the evaluation suite
```bash
python -m eval.evaluate
```

---

## Corpus Contents

### Statutes (RAG)
| Act | Regime | Year |
|-----|--------|------|
| Bharatiya Nyaya Sanhita (BNS) | BNS | 2023 |
| Bharatiya Nagarik Suraksha Sanhita (BNSS) | BNS | 2023 |
| Bharatiya Sakshya Adhiniyam (BSA) | BNS | 2023 |
| Indian Penal Code (IPC) | IPC | 1860 |
| Code of Criminal Procedure (CrPC) | IPC | 1973 |
| Constitution of India (Part III + IV) | CONST | 1950 |

### Precedents (Scraped from Indian Kanoon)
25+ landmark Supreme Court judgments across: fundamental rights, murder/culpable homicide, theft/robbery, bail, private defence, evidence law, and sentencing.

---

## Evaluation Results

| # | Case | Code Regime | Expected Ruling | Audit | Status |
|---|------|-------------|-----------------|-------|--------|
| 1 | Clear liability (CCTV theft) | BNS ✓ | liable | Pass | ✓ |
| 2 | Clear acquittal (verified alibi) | BNS ✓ | not_liable | Pass | ✓ |
| 3 | Borderline (circumstantial) | BNS ✓ | inconclusive | Pass | ✓ |
| 4 | Citation trap (hallucination test) | BNS ✓ | blocked by Auditor | Pass | ✓ |
| 5 | Pre-July 2024 offence | **IPC** ✓ | any | Pass | ✓ |

---

## Guardrails

- **Mandatory disclaimer** on every `Verdict` object — cannot be suppressed
- **HITL gate** — LangGraph `interrupt()` suspends graph; human must type `approve` before verdict is finalised
- **Citation validator** — deterministic Chroma metadata lookup, not LLM — cannot hallucinate; every cited section is checked against the corpus and any hallucinations are flagged to the human reviewer at the HITL gate before approval
- **Max rounds cap** — controlled by `MOOT_COURT_MAX_ROUNDS` env var (default 5)
- **Refusal** — Clerk system prompt rejects personal legal advice requests framed as "my case"

---

## Limitations & Future Work

- RAG corpus covers the main statutes but not all subordinate legislation (rules, regulations)
- Precedent retrieval via Tavily is internet-dependent; could be replaced with a local precedent index
- LLM may still reason incorrectly even when citing real sections — the Auditor checks existence, not interpretation accuracy
- Future: add a sub-agent for sentencing guidelines and quantum of punishment

---

## Individual Contributions

> See [`CONTRIBUTIONS.md`](CONTRIBUTIONS.md) for the full per-file ownership matrix.

See **[CONTRIBUTIONS.md](CONTRIBUTIONS.md)** for the authoritative, file-level breakdown of each member's work. Summary:

| Contributor | Primary areas |
|-------------|---------------|
| **Suraj Guduru** | Data models & graph assembly (`graph/state.py`, `graph/court.py`), Judge agent & verdict (`agents/judge.py`), LLM factory (`utils/llm.py`), `rag/retriever.py`, HITL/verdict UI, eval runner |
| **Sai Venkatesh Alampally** | RAG ingestion pipeline (`ingestion/*`), statute corpus, Prosecution & Auditor agents, citation/statute tools, scoreboard UI |
| **Thrishal Madasu** | Edge routing (`graph/edges.py`), all system prompts (`agents/prompts.py`), Clerk & Defence agents, precedent search & corpus, CLI, case-display UI, README |

---

## Project Structure

```
moot_court/
├── agents/          # 5 agent nodes + system prompts
├── cli/             # CLI entry point
├── corpus/          # Downloaded statutes + scraped precedents
├── eval/            # 5 evaluation cases + evaluator
├── graph/           # LangGraph state, edges, graph assembly
├── ingestion/       # Download, scrape, chunk, embed pipeline
├── rag/             # Retriever + precedent search
├── tools/           # LangChain tools (statute, precedent, citation validator)
└── utils/           # LLM factory
```
