"""Nyāya — Adversarial Legal Reasoning · Streamlit application."""
from __future__ import annotations

import os
import sys
import uuid
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import streamlit as st
from dotenv import load_dotenv

load_dotenv(override=True)

st.set_page_config(
    page_title="Nyāya — AI Legal Reasoning",
    page_icon="⚖",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Design system ──────────────────────────────────────────────────────────────
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,700;0,900;1,700&display=swap');

:root {
    --ground:      #0C1018;
    --surface:     #141B27;
    --surface-2:   #1C2438;
    --border:      #1E2840;
    --text:        #E4DDD1;
    --text-muted:  #7A8599;
    --accent:      #C49A3C;
    --pros:        #9E4040;
    --pros-light:  #D46060;
    --pros-bg:     rgba(158,64,64,0.10);
    --pros-border: rgba(158,64,64,0.40);
    --def:         #2E5F8A;
    --def-light:   #5A9BC0;
    --def-bg:      rgba(46,95,138,0.10);
    --def-border:  rgba(46,95,138,0.40);
}

#MainMenu, footer, header { visibility: hidden; }
.stDeployButton { display: none !important; }
[data-testid="stToolbar"] { display: none !important; }

.main .block-container { max-width: 1080px; padding: 2rem 2rem 5rem; }

@keyframes bar-enter   { from { width: 0 !important; opacity: 0; } }
@keyframes bar-enter-d { from { width: 0 !important; opacity: 0; } }
@keyframes slide-in    { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }

.ny-header { display: flex; align-items: flex-end; justify-content: space-between; border-bottom: 1px solid var(--border); padding-bottom: 1.2rem; margin-bottom: 2rem; }
.ny-wordmark { font-family: 'Playfair Display', serif; font-size: 1.9rem; font-weight: 900; color: var(--text); letter-spacing: -0.01em; margin: 0; line-height: 1; }
.ny-tagline { font-size: 0.72rem; color: var(--text-muted); letter-spacing: 0.08em; text-transform: uppercase; margin-left: 1rem; }
.ny-badge { font-size: 0.65rem; font-weight: 600; letter-spacing: 0.1em; text-transform: uppercase; padding: 0.25rem 0.65rem; border-radius: 3px; background: rgba(196,154,60,0.12); border: 1px solid rgba(196,154,60,0.3); color: var(--accent); }
.ny-badge.missing { background: rgba(200,60,60,0.1); border-color: rgba(200,60,60,0.3); color: #C05050; }

.ny-section { font-size: 0.62rem; font-weight: 700; letter-spacing: 0.15em; text-transform: uppercase; color: var(--text-muted); margin: 2rem 0 0.75rem; padding-bottom: 0.4rem; border-bottom: 1px solid var(--border); }
.ny-round-label { display: flex; align-items: center; gap: 0.75rem; margin: 2rem 0 0.75rem; padding-bottom: 0.4rem; border-bottom: 1px solid var(--border); animation: slide-in 0.3s ease both; }
.ny-round-badge { font-size: 0.6rem; font-weight: 700; letter-spacing: 0.12em; text-transform: uppercase; padding: 0.2rem 0.55rem; border-radius: 2px; background: rgba(196,154,60,0.12); color: var(--accent); border: 1px solid rgba(196,154,60,0.25); }
.ny-round-text { font-size: 0.62rem; font-weight: 700; letter-spacing: 0.15em; text-transform: uppercase; color: var(--text-muted); }

.ny-progress { display: flex; align-items: center; flex-wrap: wrap; gap: 0.45rem; margin: 1.25rem 0 1.75rem; }
.ny-prog-step { display: inline-flex; align-items: center; font-size: 0.58rem; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; padding: 0.32rem 0.7rem; border-radius: 3px; border: 1px solid var(--border); background: var(--surface); color: var(--text-muted); white-space: nowrap; transition: background 0.3s ease, color 0.3s ease, border-color 0.3s ease; }
.ny-prog-step:not(:last-child) { margin-right: 0.45rem; position: relative; }
.ny-prog-step:not(:last-child)::after { content: ""; position: absolute; right: -0.45rem; width: 0.45rem; height: 1px; background: var(--border); }
.ny-prog-done { color: var(--accent); border-color: rgba(196,154,60,0.30); background: rgba(196,154,60,0.08); }
.ny-prog-done::before { content: "✓"; margin-right: 0.4rem; font-size: 0.6rem; }
.ny-prog-active { color: var(--ground); border-color: var(--accent); background: var(--accent); box-shadow: 0 0 0 3px rgba(196,154,60,0.15); }
.ny-prog-active::before { content: ""; display: inline-block; width: 5px; height: 5px; border-radius: 50%; background: var(--ground); margin-right: 0.45rem; animation: prog-pulse 1.2s ease-in-out infinite; }
.ny-prog-pending { color: var(--text-muted); border-color: var(--border); background: var(--surface); opacity: 0.5; }
@keyframes prog-pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.25; } }

.ny-casefile { background: var(--surface); border: 1px solid var(--border); border-radius: 6px; padding: 1.2rem 1.5rem; margin-bottom: 1rem; animation: slide-in 0.35s ease both; }
.ny-cf-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 1rem; margin-bottom: 1rem; padding-bottom: 1rem; border-bottom: 1px solid var(--border); }
.ny-cf-label { font-size: 0.6rem; font-weight: 700; letter-spacing: 0.12em; text-transform: uppercase; color: var(--text-muted); margin-bottom: 0.25rem; }
.ny-cf-value { font-size: 0.88rem; color: var(--text); font-weight: 500; }
.ny-cf-value.bns { color: var(--accent); }
.ny-cf-value.ipc { color: #7A9BB5; }
.ny-q-list { list-style: none; padding: 0; margin: 0; }
.ny-q-list li { font-size: 0.83rem; color: var(--text); padding: 0.45rem 0; border-bottom: 1px solid var(--border); line-height: 1.55; display: flex; gap: 0.75rem; }
.ny-q-list li:last-child { border-bottom: none; }
.ny-q-num { font-size: 0.6rem; color: var(--accent); font-weight: 700; padding-top: 0.2rem; flex-shrink: 0; min-width: 1.5rem; }

.ny-scoreboard { background: var(--surface); border: 1px solid var(--border); border-radius: 6px; padding: 1rem 1.4rem 1.1rem; margin: 0.5rem 0 0.5rem; animation: slide-in 0.35s ease both; }
.ny-sb-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.85rem; }
.ny-sb-title { font-size: 0.6rem; font-weight: 700; letter-spacing: 0.15em; text-transform: uppercase; color: var(--text-muted); }
.ny-sb-lead { font-size: 0.6rem; font-weight: 700; letter-spacing: 0.12em; text-transform: uppercase; padding: 0.15rem 0.5rem; border-radius: 3px; }
.ny-sb-lead.pros { background: var(--pros-bg); color: var(--pros-light); border: 1px solid var(--pros-border); }
.ny-sb-lead.def  { background: var(--def-bg);  color: var(--def-light);  border: 1px solid var(--def-border); }
.ny-sb-lead.bal  { background: rgba(196,154,60,0.08); color: var(--accent); border: 1px solid rgba(196,154,60,0.25); }
.ny-sb-bars { display: flex; flex-direction: column; gap: 0.55rem; margin-bottom: 0.85rem; }
.ny-sb-row { display: flex; align-items: center; gap: 0.75rem; }
.ny-sb-name { font-size: 0.68rem; color: var(--text-muted); font-weight: 600; width: 100px; flex-shrink: 0; letter-spacing: 0.03em; }
.ny-sb-track { flex: 1; height: 8px; background: rgba(255,255,255,0.06); border-radius: 4px; overflow: hidden; }
.ny-sb-fill-p { height: 100%; background: linear-gradient(90deg, #6B2020, #9E4040); border-radius: 4px; animation: bar-enter 0.7s cubic-bezier(0.16,1,0.3,1) both; }
.ny-sb-fill-d { height: 100%; background: linear-gradient(90deg, #1A3A5C, #2E5F8A); border-radius: 4px; animation: bar-enter-d 0.7s cubic-bezier(0.16,1,0.3,1) both; }
.ny-sb-score-val { font-size: 0.8rem; font-weight: 700; color: var(--text); width: 40px; text-align: right; flex-shrink: 0; }
.ny-sb-trend { font-size: 0.65rem; color: var(--text-muted); margin-left: 0.4rem; }
.ny-sb-divider { height: 1px; background: var(--border); margin: 0.7rem 0; }
.ny-sb-history { font-size: 0.68rem; color: var(--text-muted); line-height: 1.7; font-family: 'SF Mono', 'Consolas', monospace; letter-spacing: 0.02em; }
.ny-sb-history-round { display: inline-block; margin-right: 1.1rem; }
.ny-sb-history-round .rn { color: var(--accent); font-weight: 700; }
.ny-sb-history-round .ps { color: var(--pros-light); }
.ny-sb-history-round .ds { color: var(--def-light); }

.ny-args-row { display: flex; gap: 1rem; align-items: flex-start; animation: slide-in 0.3s ease both; }
.ny-args-col { flex: 1; min-width: 0; }
.ny-card { border-radius: 6px; padding: 1.25rem 1.4rem; margin-bottom: 0.75rem; border: 1px solid transparent; }
.ny-card.pros { background: var(--pros-bg); border-color: var(--pros-border); border-left: 3px solid var(--pros); }
.ny-card.def  { background: var(--def-bg);  border-color: var(--def-border);  border-left: 3px solid var(--def); }
.ny-card.pending { background: rgba(255,255,255,0.02); border-color: var(--border); border-style: dashed; opacity: 0.7; }
.ny-card-side { font-size: 0.58rem; font-weight: 700; letter-spacing: 0.15em; text-transform: uppercase; margin-bottom: 0.9rem; }
.ny-card-side.pros { color: var(--pros-light); }
.ny-card-side.def  { color: var(--def-light); }
.ny-card-side.pending { color: var(--text-muted); }
.ny-claim { font-size: 0.84rem; color: var(--text); line-height: 1.7; margin-bottom: 0.75rem; padding-left: 1.4rem; position: relative; }
.ny-claim::before { content: attr(data-n); position: absolute; left: 0; top: 0.05rem; font-size: 0.58rem; font-weight: 700; color: var(--text-muted); }
.ny-cite-row { display: flex; flex-wrap: wrap; gap: 0.35rem; margin-top: 0.85rem; padding-top: 0.75rem; border-top: 1px solid var(--border); }
.ny-cite-label { font-size: 0.58rem; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; color: var(--text-muted); padding-top: 0.25rem; margin-right: 0.25rem; flex-shrink: 0; }
.ny-pill { font-size: 0.66rem; font-weight: 500; padding: 0.2rem 0.55rem; border-radius: 3px; background: rgba(196,154,60,0.1); border: 1px solid rgba(196,154,60,0.2); color: #D4B46C; font-family: 'SF Mono', 'Consolas', monospace; }
.ny-prec-pill { font-size: 0.66rem; font-style: italic; padding: 0.2rem 0.55rem; border-radius: 3px; background: rgba(255,255,255,0.04); border: 1px solid var(--border); color: var(--text-muted); }
.ny-rebuttal-block { margin-top: 0.9rem; padding: 0.75rem 1rem; background: rgba(0,0,0,0.2); border-radius: 4px; border-left: 2px solid var(--border); }
.ny-rebuttal-label { font-size: 0.56rem; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; color: var(--text-muted); margin-bottom: 0.4rem; }
.ny-rebuttal-text { font-size: 0.8rem; color: var(--text-muted); line-height: 1.65; }
.ny-pending-pulse { display: inline-block; width: 6px; height: 6px; border-radius: 50%; background: var(--text-muted); opacity: 0.5; margin-right: 0.5rem; vertical-align: middle; }

.ny-judge { background: var(--surface-2); border: 1px solid var(--border); border-radius: 6px; padding: 1.1rem 1.4rem; margin-top: 0; margin-bottom: 0.5rem; animation: slide-in 0.35s ease both; }
.ny-judge-title { font-size: 0.58rem; font-weight: 700; letter-spacing: 0.15em; text-transform: uppercase; color: var(--text-muted); margin-bottom: 0.8rem; }
.ny-tow-labels { display: flex; justify-content: space-between; margin-bottom: 0.35rem; }
.ny-tow-label-p { font-size: 0.72rem; font-weight: 700; color: var(--pros-light); }
.ny-tow-label-d { font-size: 0.72rem; font-weight: 700; color: var(--def-light); }
.ny-tow-bar { display: flex; height: 10px; border-radius: 5px; overflow: hidden; margin-bottom: 0.35rem; background: rgba(255,255,255,0.05); }
.ny-tow-pros { background: linear-gradient(90deg, #6B2020, #9E4040); animation: bar-enter 0.7s cubic-bezier(0.16,1,0.3,1) both; }
.ny-tow-def  { background: linear-gradient(270deg, #1A3A5C, #2E5F8A); flex: 1; animation: bar-enter-d 0.7s cubic-bezier(0.16,1,0.3,1) both; }
.ny-tow-caption { font-size: 0.62rem; color: var(--text-muted); text-align: center; letter-spacing: 0.06em; margin-bottom: 0.55rem; }
.ny-decision { display: inline-block; font-size: 0.58rem; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; padding: 0.2rem 0.6rem; border-radius: 3px; margin-top: 0.5rem; }
.ny-decision.loop  { background: rgba(196,154,60,0.12); color: var(--accent); border: 1px solid rgba(196,154,60,0.3); }
.ny-decision.stop  { background: rgba(46,95,138,0.15); color: #7AABCC; border: 1px solid rgba(46,95,138,0.3); }
.ny-decision.early { background: rgba(46,138,80,0.12); color: #4CAF80; border: 1px solid rgba(46,138,80,0.3); }
.ny-judge-reason { font-size: 0.8rem; color: var(--text-muted); line-height: 1.65; margin-top: 0.7rem; padding-top: 0.7rem; border-top: 1px solid var(--border); }

.ny-audit { border-radius: 6px; padding: 1rem 1.4rem; border: 1px solid transparent; animation: slide-in 0.35s ease both; }
.ny-audit.pass { background: rgba(46,138,80,0.08); border-color: rgba(46,138,80,0.25); }
.ny-audit.fail { background: rgba(200,60,60,0.08); border-color: rgba(200,60,60,0.25); }
.ny-audit-title { font-size: 0.68rem; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; margin-bottom: 0.5rem; }
.ny-audit.pass .ny-audit-title { color: #4CAF80; }
.ny-audit.fail .ny-audit-title { color: #C05050; }
.ny-audit-body { font-size: 0.82rem; color: var(--text-muted); line-height: 1.55; }

.ny-hitl { background: var(--surface); border: 1px solid rgba(196,154,60,0.35); border-radius: 6px; padding: 1.4rem 1.6rem; margin: 1.5rem 0; }
.ny-hitl-title { font-size: 0.65rem; font-weight: 700; letter-spacing: 0.14em; text-transform: uppercase; color: var(--accent); margin-bottom: 0.5rem; }
.ny-hitl-body { font-size: 0.84rem; color: var(--text-muted); line-height: 1.6; }

.ny-verdict-wrap { border-radius: 6px; overflow: hidden; margin-top: 0.5rem; animation: slide-in 0.4s ease both; }
.ny-verdict-panel { padding: 2.8rem 2rem; text-align: center; }
.ny-verdict-panel.liable      { background: rgba(158,64,64,0.15);  border: 1px solid rgba(158,64,64,0.4); }
.ny-verdict-panel.not_liable  { background: rgba(46,138,80,0.12);  border: 1px solid rgba(46,138,80,0.35); }
.ny-verdict-panel.inconclusive{ background: rgba(196,154,60,0.10); border: 1px solid rgba(196,154,60,0.35); }
.ny-verdict-ruling { font-family: 'Playfair Display', serif; font-size: 3.8rem; font-weight: 900; letter-spacing: -0.02em; line-height: 1; margin-bottom: 0.5rem; animation: slide-in 0.5s ease both; }
.liable       .ny-verdict-ruling { color: #D46060; }
.not_liable   .ny-verdict-ruling { color: #4CAF80; }
.inconclusive .ny-verdict-ruling { color: var(--accent); }
.ny-conf-wrap { display: flex; flex-direction: column; align-items: center; gap: 0.4rem; margin-top: 1.2rem; }
.ny-conf-label { font-size: 0.62rem; font-weight: 700; letter-spacing: 0.12em; text-transform: uppercase; color: var(--text-muted); }
.ny-conf-track { width: 220px; height: 8px; background: rgba(255,255,255,0.08); border-radius: 4px; overflow: hidden; }
.ny-conf-fill { height: 100%; border-radius: 4px; animation: bar-enter 0.8s cubic-bezier(0.16,1,0.3,1) both; }
.liable       .ny-conf-fill { background: linear-gradient(90deg, #6B2020, #D46060); }
.not_liable   .ny-conf-fill { background: linear-gradient(90deg, #1A5C35, #4CAF80); }
.inconclusive .ny-conf-fill { background: linear-gradient(90deg, #7A5020, var(--accent)); }
.ny-conf-value { font-size: 1.1rem; font-weight: 700; color: var(--text); }
.ny-conf-desc { font-size: 0.72rem; color: var(--text-muted); font-style: italic; }
.ny-verdict-body { padding: 1.6rem 1.8rem; background: var(--surface); border: 1px solid var(--border); border-top: none; border-radius: 0 0 6px 6px; }
.ny-verdict-score-row { display: flex; gap: 2rem; margin-bottom: 1.2rem; padding-bottom: 1.2rem; border-bottom: 1px solid var(--border); }
.ny-verdict-score-item { flex: 1; }
.ny-verdict-score-side { font-size: 0.58rem; font-weight: 700; letter-spacing: 0.12em; text-transform: uppercase; margin-bottom: 0.4rem; }
.ny-verdict-score-side.pros { color: var(--pros-light); }
.ny-verdict-score-side.def  { color: var(--def-light); }
.ny-verdict-score-bar { height: 5px; background: rgba(255,255,255,0.06); border-radius: 3px; overflow: hidden; margin-bottom: 0.3rem; }
.ny-verdict-score-bar-fill-p { height: 100%; background: linear-gradient(90deg, #6B2020, #9E4040); border-radius: 3px; animation: bar-enter 0.8s cubic-bezier(0.16,1,0.3,1) 0.2s both; }
.ny-verdict-score-bar-fill-d { height: 100%; background: linear-gradient(90deg, #1A3A5C, #2E5F8A); border-radius: 3px; animation: bar-enter-d 0.8s cubic-bezier(0.16,1,0.3,1) 0.2s both; }
.ny-verdict-score-num { font-size: 0.72rem; color: var(--text-muted); }
.ny-verdict-reasoning { font-size: 0.88rem; color: var(--text); line-height: 1.8; margin-bottom: 1rem; }
.ny-verdict-cites { font-size: 0.78rem; color: var(--text-muted); margin-bottom: 0.4rem; line-height: 1.6; }
.ny-verdict-disclaimer { font-size: 0.72rem; color: var(--text-muted); font-style: italic; margin-top: 1rem; padding-top: 1rem; border-top: 1px solid var(--border); }

/* Trial summary — closing stat panel */
.ny-conclusion { background: var(--surface); border: 1px solid var(--border); border-radius: 6px; padding: 1.4rem 1.5rem 1.3rem; margin-bottom: 1rem; animation: slide-in 0.35s ease both; }
.ny-conclusion-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 0.85rem; }
.ny-conclusion-stat { background: var(--surface-2); border: 1px solid var(--border); border-radius: 5px; padding: 1rem 0.85rem; text-align: center; }
.ny-conclusion-label { font-size: 0.56rem; font-weight: 700; letter-spacing: 0.12em; text-transform: uppercase; color: var(--text-muted); margin-bottom: 0.55rem; }
.ny-conclusion-value { font-family: 'Playfair Display', serif; font-size: 1.75rem; font-weight: 900; color: var(--text); line-height: 1.05; letter-spacing: -0.01em; }
.ny-conclusion-value.liable       { font-size: 1.15rem; letter-spacing: 0.01em; color: #D46060; }
.ny-conclusion-value.not_liable   { font-size: 1.15rem; letter-spacing: 0.01em; color: #4CAF80; }
.ny-conclusion-value.inconclusive { font-size: 1.15rem; letter-spacing: 0.01em; color: var(--accent); }
.ny-conclusion-note { font-size: 0.8rem; color: var(--text-muted); line-height: 1.65; margin-top: 1.1rem; padding-top: 1rem; border-top: 1px solid var(--border); text-align: center; }
@media (max-width: 640px) { .ny-conclusion-row { grid-template-columns: repeat(2, 1fr); } }

div[data-testid="stButton"] button { border-radius: 4px; font-size: 0.8rem; letter-spacing: 0.05em; font-weight: 600; transition: all 0.15s ease; }
div[data-testid="stTextArea"] textarea { background: var(--surface) !important; border-color: var(--border) !important; color: var(--text) !important; font-size: 0.87rem; line-height: 1.7; border-radius: 5px; }
div[data-testid="stSelectbox"] > div { background: var(--surface) !important; border-color: var(--border) !important; border-radius: 5px; }
div[data-testid="stAlert"] { background: rgba(196,154,60,0.08) !important; border-color: rgba(196,154,60,0.3) !important; border-radius: 5px; }
</style>
"""


# ── Session state ──────────────────────────────────────────────────────────────

def _init_state() -> None:
    defaults: dict = {
        "phase": "idle",
        "thread_id": None,
        "facts_raw": "",
        "offence_date": None,
        "clerk_output": None,
        "rounds": [],
        "audit_result": None,
        "verdict": None,
        "error_msg": "",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def _build_fresh_graph():
    import importlib
    import utils.llm
    import agents.prompts, agents.clerk, agents.prosecution, agents.defence
    import agents.judge, agents.auditor
    import graph.edges, graph.court
    importlib.reload(utils.llm)
    importlib.reload(agents.prompts)
    importlib.reload(agents.clerk)
    importlib.reload(agents.prosecution)
    importlib.reload(agents.defence)
    importlib.reload(agents.judge)
    importlib.reload(agents.auditor)
    importlib.reload(graph.edges)
    importlib.reload(graph.court)
    from langgraph.checkpoint.memory import MemorySaver
    from graph.court import build_graph
    return build_graph(checkpointer=MemorySaver())


def _get_graph():
    if "graph" not in st.session_state:
        st.session_state["graph"] = _build_fresh_graph()
    return st.session_state["graph"]


def _reset() -> None:
    for k in ["phase", "thread_id", "facts_raw", "offence_date", "clerk_output",
              "rounds", "audit_result", "verdict", "error_msg"]:
        st.session_state.pop(k, None)
    _init_state()


def _corpus_ready() -> bool:
    chroma_dir = Path(__file__).parent / "chroma_db"
    return chroma_dir.exists() and any(chroma_dir.iterdir())


# ── HTML string builders ───────────────────────────────────────────────────────

def _pills_html(items: list[str], cls: str = "ny-pill") -> str:
    if not items:
        return "<span style='color:var(--text-muted);font-size:0.72rem'>—</span>"
    return " ".join(f"<span class='{cls}'>{s}</span>" for s in items[:6])


def _case_file_html(cf: dict) -> str:
    regime = cf.get("code_regime", "BNS")
    regime_cls = "bns" if regime == "BNS" else "ipc"
    date_val = cf.get("offence_date") or "Not specified"
    offence = cf.get("offence_type") or "—"
    accused = cf.get("accused_name") or "Accused"
    questions = cf.get("legal_questions", [])
    q_items = "".join(
        f"<li><span class='ny-q-num'>Q{i+1}</span>{q}</li>"
        for i, q in enumerate(questions)
    )
    return f"""
<div class='ny-section'>Case File</div>
<div class='ny-casefile'>
  <div class='ny-cf-grid'>
    <div><div class='ny-cf-label'>Code Regime</div><div class='ny-cf-value {regime_cls}'>{regime}</div></div>
    <div><div class='ny-cf-label'>Offence Date</div><div class='ny-cf-value'>{date_val}</div></div>
    <div><div class='ny-cf-label'>Offence Type</div><div class='ny-cf-value'>{offence}</div></div>
    <div><div class='ny-cf-label'>Accused</div><div class='ny-cf-value'>{accused}</div></div>
  </div>
  <div class='ny-cf-label' style='margin-bottom:0.5rem'>Legal Questions Before Court</div>
  <ul class='ny-q-list'>{q_items}</ul>
</div>"""


def _argument_card_html(arg: dict, side: str) -> str:
    side_cls = "pros" if side == "prosecution" else "def"
    side_label = "PROSECUTION" if side == "prosecution" else "DEFENCE"
    claims = arg.get("claims", [])
    claims_html = "".join(
        f"<div class='ny-claim' data-n='{i+1}.'>{c}</div>"
        for i, c in enumerate(claims[:5])
    )
    statutes = arg.get("statutes_cited", [])
    precedents = arg.get("precedents_cited", [])
    rebuttals = [r for r in arg.get("rebuttals", []) if r]
    cite_html = ""
    if statutes or precedents:
        cite_html = f"""
<div class='ny-cite-row'>
  <span class='ny-cite-label'>Statutes</span>{_pills_html(statutes, 'ny-pill')}
</div>
<div class='ny-cite-row' style='margin-top:0.3rem'>
  <span class='ny-cite-label'>Precedents</span>{_pills_html(precedents, 'ny-prec-pill')}
</div>"""
    rebuttal_html = ""
    if rebuttals:
        rebuttal_html = f"""
<div class='ny-rebuttal-block'>
  <div class='ny-rebuttal-label'>Rebuttal of opposing argument</div>
  <div class='ny-rebuttal-text'>{" ".join(rebuttals[:3])}</div>
</div>"""
    return f"""
<div class='ny-card {side_cls}'>
  <div class='ny-card-side {side_cls}'>{side_label}</div>
  {claims_html}{cite_html}{rebuttal_html}
</div>"""


def _pending_card_html(side: str) -> str:
    label = "PROSECUTION" if side == "prosecution" else "DEFENCE"
    return f"""
<div class='ny-card pending'>
  <div class='ny-card-side pending'>{label}</div>
  <div style='font-size:0.8rem;color:var(--text-muted)'>
    <span class='ny-pending-pulse'></span>Preparing argument…
  </div>
</div>"""


def _round_header_html(rn: int) -> str:
    return f"""
<div class='ny-round-label'>
  <span class='ny-round-badge'>Round {rn}</span>
  <span class='ny-round-text'>Oral Arguments</span>
</div>"""


def _round_args_html(rd: dict) -> str:
    pros = rd.get("prosecution")
    defn = rd.get("defence")
    pros_html = _argument_card_html(pros, "prosecution") if pros else _pending_card_html("prosecution")
    def_html = _argument_card_html(defn, "defence") if defn else _pending_card_html("defence")
    return f"""
<div class='ny-args-row'>
  <div class='ny-args-col'>{pros_html}</div>
  <div class='ny-args-col'>{def_html}</div>
</div>"""


def _audit_html(audit: dict) -> str:
    if not audit:
        return ""
    passed = audit.get("audit_passed", True)
    cls = "pass" if passed else "fail"
    title = "All citations verified" if passed else "Citation issues detected"
    verified = audit.get("verified_citations", [])
    hallucinated = audit.get("hallucinated_citations", [])
    verified_precedents = audit.get("verified_precedents", [])
    unverified_precedents = audit.get("unverified_precedents", [])
    notes = audit.get("audit_notes", "")
    detail = ""
    if verified:
        detail += f"Verified statutes: {', '.join(verified[:8])}. "
    if hallucinated:
        detail += f"<strong style='color:#C05050'>Statutes not found: {', '.join(hallucinated)}.</strong> "
    if verified_precedents:
        detail += f"Verified cases: {', '.join(verified_precedents[:8])}. "
    if unverified_precedents:
        detail += f"<strong style='color:#C05050'>Unverified cases: {', '.join(unverified_precedents)}.</strong> "
    if notes:
        detail += notes
    return f"""
<div class='ny-section'>Citation Audit</div>
<div class='ny-audit {cls}'>
  <div class='ny-audit-title'>{title}</div>
  <div class='ny-audit-body'>{detail}</div>
</div>"""



def _scoreboard_html() -> str:
    rounds = st.session_state.rounds
    scored = [(i + 1, rd) for i, rd in enumerate(rounds) if rd.get("score")]
    if not scored:
        return ""
    rounds_done = len(scored)
    wps = [rd["score"].get("win_probability", 50) for _, rd in scored]
    latest_wp = wps[-1]
    d_wp = 100 - latest_wp
    if latest_wp >= 60:
        lead_text, lead_cls = "PROSECUTION FAVOURED", "pros"
    elif latest_wp <= 40:
        lead_text, lead_cls = "DEFENCE FAVOURED", "def"
    else:
        lead_text, lead_cls = "BALANCED", "bal"
    def _wp_trend(wp_list: list) -> str:
        if len(wp_list) < 2:
            return ""
        diff = wp_list[-1] - wp_list[-2]
        if diff > 2:
            return f"<span style=\'color:var(--pros-light);font-size:0.65rem\'> ▲{diff}%</span>"
        if diff < -2:
            return f"<span style=\'color:var(--def-light);font-size:0.65rem\'> ▼{abs(diff)}%</span>"
        return "<span style=\'color:var(--text-muted);font-size:0.65rem\'> —</span>"
    history_parts = []
    for rn, rd in scored:
        wp_val = rd["score"].get("win_probability", 50)
        history_parts.append(
            f"<span class='ny-sb-history-round'>"
            f"<span class='rn'>R{rn}</span> "
            f"<span class='ps'>P {wp_val}%</span>"
            f"</span>"
        )
    history_items = "".join(history_parts)
    return f"""
<div class=\'ny-section\'>Trial Momentum · {rounds_done} Round{"s" if rounds_done != 1 else ""} Scored</div>
<div class=\'ny-scoreboard\'>
  <div class=\'ny-sb-header\'>
    <span class=\'ny-sb-title\'>Win Probability</span>
    <span class=\'ny-sb-lead {lead_cls}\'>{lead_text}</span>
  </div>
  <div class=\'ny-tow-labels\'>
    <span class=\'ny-tow-label-p\'>Prosecution · {latest_wp}%{_wp_trend(wps)}</span>
    <span class=\'ny-tow-label-d\'>{d_wp}% · Defence</span>
  </div>
  <div class=\'ny-tow-bar\'>
    <div class=\'ny-tow-pros\' style=\'width:{latest_wp}%\'></div>
    <div class=\'ny-tow-def\'></div>
  </div>
  <div class=\'ny-sb-divider\'></div>
  <div class=\'ny-sb-history\'>{history_items}</div>
</div>"""


def _judge_score_html(score: dict) -> str:
    wp = score.get("win_probability", 50)
    d_wp = 100 - wp
    decision = score.get("decision", "proceed_to_verdict")
    is_early = decision == "proceed_to_verdict" and (wp >= 80 or wp <= 20)
    if decision == "another_round":
        badge_cls, badge_text = "loop", "Another round ordered"
    elif is_early:
        winner = "Prosecution" if wp >= 90 else "Defence"
        badge_cls, badge_text = "early", f"Early verdict — {winner} case overwhelming"
    else:
        badge_cls, badge_text = "stop", "Proceeding to verdict"
    reasoning = score.get("reasoning", "")
    uncited = score.get("uncited_statutes", [])
    uncited_list = ", ".join(uncited[:4])
    uncited_note = f" <em>The court expected to hear arguments on: {uncited_list}.</em>" if uncited else ""
    weak = score.get("weak_side", "balanced")
    weak_side_name = "Prosecution" if weak == "prosecution" else "Defence"
    weak_note = f" {weak_side_name} counsel's arguments were weaker this round." if weak != "balanced" else ""
    rn = score.get("round_number", "?")
    return f"""
<div class='ny-judge'>
  <div class='ny-judge-title'>Judge's Assessment — Round {rn}</div>
  <div class='ny-tow-labels'>
    <span class='ny-tow-label-p'>Prosecution · {wp}%</span>
    <span class='ny-tow-label-d'>{d_wp}% · Defence</span>
  </div>
  <div class='ny-tow-bar'>
    <div class='ny-tow-pros' style='width:{wp}%'></div>
    <div class='ny-tow-def'></div>
  </div>
  <div class='ny-tow-caption'>Win probability — based on case strength &amp; law</div>
  <span class='ny-decision {badge_cls}'>{badge_text}</span>
  <div class='ny-judge-reason'>{reasoning}{weak_note}{uncited_note}</div>
</div>"""


def _conf_description(conf: int) -> str:
    if conf >= 9:
        return "Overwhelming — evidence on one side was conclusive"
    if conf >= 7:
        return "High — winning side held a clear advantage on the facts"
    if conf >= 5:
        return "Moderate — case was contested; some doubt remains"
    if conf >= 3:
        return "Low — outcome was uncertain; evidence was equivocal"
    return "Very low — genuinely contested; verdict could have gone either way"

# ── State absorber ─────────────────────────────────────────────────────────────

def _absorb(node_name: str, update: dict) -> None:
    def _rn_from(obj) -> int:
        return obj.get("round_number", 1) if isinstance(obj, dict) else getattr(obj, "round_number", 1)

    if node_name == "clerk_node" and "case_file" in update:
        cf = update["case_file"]
        st.session_state.clerk_output = cf if isinstance(cf, dict) else cf.model_dump()

    if node_name == "prosecution_node" and "round_transcript" in update:
        for arg in update["round_transcript"]:
            rn = _rn_from(arg)
            arg_d = arg if isinstance(arg, dict) else arg.model_dump()
            while len(st.session_state.rounds) < rn:
                st.session_state.rounds.append({})
            st.session_state.rounds[rn - 1]["prosecution"] = arg_d

    if node_name == "defence_node" and "round_transcript" in update:
        for arg in update["round_transcript"]:
            rn = _rn_from(arg)
            arg_d = arg if isinstance(arg, dict) else arg.model_dump()
            while len(st.session_state.rounds) < rn:
                st.session_state.rounds.append({})
            st.session_state.rounds[rn - 1]["defence"] = arg_d

    if node_name == "judge_node" and "judge_scores" in update:
        for score in update["judge_scores"]:
            rn = _rn_from(score)
            score_d = score if isinstance(score, dict) else score.model_dump()
            while len(st.session_state.rounds) < rn:
                st.session_state.rounds.append({})
            st.session_state.rounds[rn - 1]["score"] = score_d

    if node_name == "auditor_node" and "audit_result" in update:
        st.session_state.audit_result = update["audit_result"]

    if node_name == "verdict_node" and "verdict" in update:
        v = update["verdict"]
        st.session_state.verdict = v if isinstance(v, dict) else v.model_dump()


# ── Streaming ──────────────────────────────────────────────────────────────────

_ACTIVITY_LABELS = {
    "clerk_node":       "⚖ Court Clerk is registering the case and identifying applicable statutes…",
    "prosecution_node": "⚔ Prosecution counsel is building arguments…",
    "defence_node":     "🛡 Defence counsel is preparing a response…",
    "judge_node":       "🔎 The Judge is evaluating arguments and scoring the round…",
    "auditor_node":     "📋 Citation Auditor is verifying all statutory references…",
    "verdict_node":     "⚖ The Judge is deliberating the final verdict…",
}

_MAX_ROUNDS = 8


def _run_pre_hitl(facts: str, offence_date: str) -> None:
    thread_id = str(uuid.uuid4())
    st.session_state.thread_id = thread_id
    config = {"configurable": {"thread_id": thread_id}}
    graph = _get_graph()
    initial_state = {
        "facts_raw": facts,
        "offence_date": offence_date,
        "round_transcript": [],
        "judge_scores": [],
        "current_round": 1,
        "current_phase": "intake",
        "audit_result": None,
        "audit_passed": False,
        "hitl_approved": False,
        "verdict": None,
        "error": None,
    }

    progress_slot = st.empty()
    case_slot = st.empty()
    scoreboard_slot = st.empty()
    activity_slot = st.empty()
    round_slots: list[dict] = [
        {"header": st.empty(), "args": st.empty(), "score": st.empty()}
        for _ in range(_MAX_ROUNDS)
    ]
    audit_slot = st.empty()
    progress_slot.markdown(_progress_html(), unsafe_allow_html=True)

    def _rn_from(obj) -> int:
        return obj.get("round_number", 1) if isinstance(obj, dict) else getattr(obj, "round_number", 1)

    try:
        for chunk in graph.stream(initial_state, config=config, stream_mode="updates"):
            for node_name, update in chunk.items():
                _absorb(node_name, update)
                progress_slot.markdown(_progress_html(), unsafe_allow_html=True)

                if node_name == "clerk_node" and st.session_state.clerk_output:
                    case_slot.markdown(_case_file_html(st.session_state.clerk_output), unsafe_allow_html=True)

                elif node_name == "prosecution_node" and "round_transcript" in update:
                    for arg in update["round_transcript"]:
                        rn = _rn_from(arg)
                        rn_idx = rn - 1
                        if 0 <= rn_idx < _MAX_ROUNDS:
                            rd = st.session_state.rounds[rn_idx]
                            round_slots[rn_idx]["header"].markdown(_round_header_html(rn), unsafe_allow_html=True)
                            round_slots[rn_idx]["args"].markdown(_round_args_html(rd), unsafe_allow_html=True)

                elif node_name == "defence_node" and "round_transcript" in update:
                    for arg in update["round_transcript"]:
                        rn = _rn_from(arg)
                        rn_idx = rn - 1
                        if 0 <= rn_idx < _MAX_ROUNDS:
                            rd = st.session_state.rounds[rn_idx]
                            round_slots[rn_idx]["args"].markdown(_round_args_html(rd), unsafe_allow_html=True)

                elif node_name == "judge_node" and "judge_scores" in update:
                    for score in update["judge_scores"]:
                        rn = _rn_from(score)
                        rn_idx = rn - 1
                        if 0 <= rn_idx < _MAX_ROUNDS:
                            rd = st.session_state.rounds[rn_idx]
                            s = rd.get("score")
                            if s:
                                round_slots[rn_idx]["score"].markdown(_judge_score_html(s), unsafe_allow_html=True)
                    sb_html = _scoreboard_html()
                    if sb_html:
                        scoreboard_slot.markdown(sb_html, unsafe_allow_html=True)

                elif node_name == "auditor_node" and st.session_state.audit_result:
                    audit_slot.markdown(_audit_html(st.session_state.audit_result), unsafe_allow_html=True)

                label = _ACTIVITY_LABELS.get(node_name, "")
                if label:
                    activity_slot.info(label)
                else:
                    activity_slot.empty()

    except Exception as exc:
        activity_slot.empty()
        st.session_state.phase = "error"
        st.session_state.error_msg = str(exc)
        return

    activity_slot.empty()
    graph_state = graph.get_state(config)
    if graph_state.next and "hitl_node" in graph_state.next:
        st.session_state.phase = "awaiting_hitl"
    else:
        st.session_state.phase = "done"



def _progress_html() -> str:
    """Horizontal stepper reflecting live trial state (works during the run, at
    the gate, and when done) — each step is derived from session_state, not just
    the phase, so it updates as nodes stream in."""
    rounds = st.session_state.rounds
    phase = st.session_state.phase
    clerk_done = bool(st.session_state.clerk_output)
    audit_done = bool(st.session_state.audit_result)
    past_gate = phase in {"post_hitl_approved", "post_hitl_rejected", "done"}

    steps = [("Intake", "clerk")]
    for i in range(1, len(rounds) + 1):
        steps.append((f"Round {i}", f"r{i}"))
    steps += [("Audit", "audit"), ("HITL Gate", "hitl"), ("Verdict", "verdict")]

    items = []
    for label, key in steps:
        if key == "clerk":
            cls = "ny-prog-done" if clerk_done else "ny-prog-active"
        elif key.startswith("r"):
            rd = rounds[int(key[1:]) - 1]
            if rd.get("score"):
                cls = "ny-prog-done"
            elif rd.get("prosecution") or rd.get("defence"):
                cls = "ny-prog-active"
            else:
                cls = "ny-prog-pending"
        elif key == "audit":
            cls = "ny-prog-done" if audit_done else "ny-prog-pending"
        elif key == "hitl":
            cls = "ny-prog-active" if phase == "awaiting_hitl" else ("ny-prog-done" if past_gate else "ny-prog-pending")
        else:  # verdict
            cls = "ny-prog-done" if phase == "done" else ("ny-prog-active" if phase == "post_hitl_approved" else "ny-prog-pending")
        items.append(f"<div class='ny-prog-step {cls}'>{label}</div>")
    return "<div class='ny-progress'>" + "".join(items) + "</div>"


def _conclusion_html() -> str:
    rounds = st.session_state.rounds
    verdict = st.session_state.verdict or {}
    scored = [rd for rd in rounds if rd.get("score")]
    if not scored:
        return ""
    wps = [rd["score"].get("win_probability", 50) for rd in scored]
    final_wp = wps[-1]
    ruling = verdict.get("ruling", "inconclusive")
    ruling_display = ruling.upper().replace("_", " ")
    if final_wp >= 60:
        balance = f"Prosecution ended with a {final_wp}% win probability — favoured throughout."
    elif final_wp <= 40:
        balance = f"Defence ended with a {100 - final_wp}% win probability — case leaned toward acquittal."
    else:
        balance = f"Win probability ended at {final_wp}% — a genuinely contested case."
    turning = None
    for i, rd in enumerate(scored):
        if abs(rd["score"].get("win_probability", 50) - 50) > 10:
            turning = i + 1
            break
    turn_str = f" The balance first shifted decisively in Round {turning}." if turning else ""
    return f"""
<div class='ny-section'>Trial Summary</div>
<div class='ny-conclusion'>
  <div class='ny-conclusion-row'>
    <div class='ny-conclusion-stat'>
      <div class='ny-conclusion-label'>Final Ruling</div>
      <div class='ny-conclusion-value {ruling}'>{ruling_display}</div>
    </div>
    <div class='ny-conclusion-stat'>
      <div class='ny-conclusion-label'>Final Win Prob</div>
      <div class='ny-conclusion-value'>{final_wp}% P</div>
    </div>
    <div class='ny-conclusion-stat'>
      <div class='ny-conclusion-label'>Peak Prob</div>
      <div class='ny-conclusion-value'>{max(wps)}% P</div>
    </div>
    <div class='ny-conclusion-stat'>
      <div class='ny-conclusion-label'>Rounds</div>
      <div class='ny-conclusion-value'>{len(scored)}</div>
    </div>
  </div>
  <div class='ny-conclusion-note'>{balance}{turn_str}</div>
</div>"""


def _verdict_html(verdict: dict, rounds: list) -> str:
    ruling = verdict.get("ruling", "inconclusive").lower().replace(" ", "_")
    display = ruling.upper().replace("_", " ")
    confidence = verdict.get("confidence", 5)
    reasoning = verdict.get("reasoning", "")
    statutes = verdict.get("statutes_relied_on", [])
    precedents = verdict.get("precedents_relied_on", [])
    dissent = verdict.get("dissent_notes", "")
    disclaimer = verdict.get("disclaimer", "AI-generated educational simulation. Not legal advice.")
    scored = [rd for rd in rounds if rd.get("score")]
    n_rounds = len(scored)
    final_wp = scored[-1]["score"].get("win_probability", 50) if scored else 50
    final_d_wp = 100 - final_wp
    sep = " · "
    cite_html = ""
    if statutes:
        statutes_str = sep.join(statutes[:6])
        cite_html += f"<div class='ny-verdict-cites'><strong>Statutes relied on:</strong> {statutes_str}</div>"
    if precedents:
        precedents_str = sep.join(precedents[:5])
        cite_html += f"<div class='ny-verdict-cites'><strong>Precedents:</strong> {precedents_str}</div>"
    dissent_html = ""
    if dissent:
        dissent_html = f"<div class='ny-verdict-cites' style='margin-top:0.6rem;color:var(--text-muted);font-style:italic'>{dissent}</div>"
    return f"""
<div class=\'ny-section\'>Final Verdict · {n_rounds} Round{"s" if n_rounds != 1 else ""}</div>
<div class=\'ny-verdict-wrap\'>
  <div class=\'ny-verdict-panel {ruling}\'>
    <div class=\'ny-verdict-ruling\'>{display}</div>
    <div class=\'ny-conf-wrap\'>
      <span class=\'ny-conf-label\'>Judge\'s Confidence</span>
      <div class=\'ny-conf-track\'><div class=\'ny-conf-fill\' style=\'width:{confidence*10}%\'></div></div>
      <span class=\'ny-conf-value\'>{confidence}/10</span>
      <span class=\'ny-conf-desc\'>{_conf_description(confidence)}</span>
    </div>
  </div>
  <div class=\'ny-verdict-body\'>
    <div class=\'ny-verdict-score-row\'>
      <div class=\'ny-verdict-score-item\' style=\'flex:none;width:100%\'>
        <div class=\'ny-verdict-score-side pros\' style=\'margin-bottom:0.5rem\'>Final Win Probability</div>
        <div class=\'ny-tow-labels\' style=\'margin-bottom:0.3rem\'><span class=\'ny-tow-label-p\'>Prosecution · {final_wp}%</span><span class=\'ny-tow-label-d\'>{final_d_wp}% · Defence</span></div>
        <div class=\'ny-tow-bar\' style=\'height:12px\'><div class=\'ny-tow-pros\' style=\'width:{final_wp}%\'></div><div class=\'ny-tow-def\'></div></div>
      </div>
    </div>
    <div class=\'ny-verdict-reasoning\'>{reasoning}</div>
    {cite_html}
    {dissent_html}
    <div class=\'ny-verdict-disclaimer\'>{disclaimer}</div>
  </div>
</div>"""


def _render_all() -> None:
    if st.session_state.clerk_output:
        st.markdown(_case_file_html(st.session_state.clerk_output), unsafe_allow_html=True)
    sb_html = _scoreboard_html()
    if sb_html:
        st.markdown(sb_html, unsafe_allow_html=True)
    for i, rd in enumerate(st.session_state.rounds):
        st.markdown(_round_header_html(i + 1), unsafe_allow_html=True)
        st.markdown(_round_args_html(rd), unsafe_allow_html=True)
        if rd.get("score"):
            st.markdown(_judge_score_html(rd["score"]), unsafe_allow_html=True)
    if st.session_state.audit_result:
        st.markdown(_audit_html(st.session_state.audit_result), unsafe_allow_html=True)


def _run_post_hitl(approved: bool) -> None:
    from langgraph.types import Command
    from utils.llm import reset_fallback
    reset_fallback()  # verdict must use the full models (judge/primary), not the 8B fallback whose 6K TPM causes 413
    config = {"configurable": {"thread_id": st.session_state.thread_id}}
    graph = st.session_state.get("_graph") or _get_graph()
    decision = "approve" if approved else "reject"
    activity = st.empty()
    activity.info("Deliberating the final verdict…" if approved else "Hearing another round of argument…")
    try:
        for chunk in graph.stream(Command(resume=decision), config=config, stream_mode="updates"):
            for node_name, update in chunk.items():
                _absorb(node_name, update)
                label = _ACTIVITY_LABELS.get(node_name, "")
                if label:
                    activity.info(label)
    except Exception as exc:
        activity.empty()
        st.session_state.phase = "error"
        st.session_state.error_msg = str(exc)
        return
    activity.empty()
    # On "hear another round" the graph runs a fresh round and re-suspends before
    # the gate — return to the review screen, not the (verdict-less) done screen.
    graph_state = graph.get_state(config)
    if graph_state.next and "hitl_node" in graph_state.next:
        st.session_state.phase = "awaiting_hitl"
    else:
        st.session_state.phase = "done"

# ── Sample cases ───────────────────────────────────────────────────────────────

SAMPLE_CASES = {
    "Select a sample case…": "",
    "Theft with CCTV — BNS (Aug 2024)": (
        "On 15 August 2024, the accused Ravi Kumar, aged 27, entered a mobile phone retail "
        "shop — 'Smart Zone Electronics' — in Koramangala, Bengaluru at approximately 3:42 PM. "
        "The shop was busy with three other customers present. The shop owner, Mr. Arjun Shetty, "
        "was attending to a customer at the billing counter. Ravi picked up two Samsung Galaxy S24 "
        "smartphones (total retail value Rs 1,10,000) from an unlocked display shelf, concealed them "
        "inside a cloth shopping bag he had brought with him, and attempted to walk out through the "
        "main entrance without making any payment. He was stopped by a security guard, Mahesh, at "
        "the exit after the anti-theft alarm was triggered. The entire sequence was recorded on four "
        "CCTV cameras inside the store. The phones were recovered intact from his bag. Ravi claimed "
        "he 'forgot to pay' and had intended to return. No prior criminal record was found. No "
        "violence was used. The phones were in working condition when recovered."
    ),
    "Dowry death — IPC (Mar 2024)": (
        "On 14 March 2024, Sunita Devi, aged 24, was found dead at her matrimonial home in "
        "Patna, Bihar. The official cause of death was strangulation, confirmed by post-mortem "
        "conducted at Patna Medical College on 15 March 2024. Sunita had been married to the "
        "accused Rajesh Kumar for 18 months. Her parents filed a complaint stating that Rajesh "
        "and his parents had been demanding Rs 5 lakh additional dowry since the marriage and had "
        "subjected Sunita to physical and mental harassment. Sunita spoke to her mother by phone "
        "three days before her death, expressing fear for her life and stating she was being beaten "
        "for not bringing money from her parents. Two neighbours corroborated hearing arguments and "
        "sounds of physical altercation from the house on the night of 12 March. Rajesh claims "
        "Sunita died by suicide due to depression. No suicide note was found. Forensic examination "
        "found Sunita's skin cells under Rajesh's fingernails."
    ),
    "Grievous hurt — circumstantial (BNS)": (
        "On 3 November 2024, Mr. Harish Goel, aged 45, was found unconscious near the rear "
        "exit of Centurion Mall's underground parking lot in Hyderabad at 10:15 PM with severe "
        "head injuries. He remains in a coma. The accused, Vikram Singh aged 38, was Harish's "
        "business partner with whom he had a documented financial dispute over Rs 40 lakh. A "
        "restaurant waiter witnessed a heated argument between Vikram and Harish inside the mall "
        "at 8:30 PM. CCTV at the parking lot entrance shows Harish entering at 9:45 PM and "
        "Vikram's registered vehicle entering two minutes later at 9:47 PM. Vikram's jacket had "
        "a bloodstain on the left sleeve matching Harish's blood group B+. Vikram claims he went "
        "to his car to retrieve documents and did not encounter Harish."
    ),
    "Drug possession — NDPS Act (Sep 2024)": (
        "On 7 September 2024, officers from the Narcotics Control Bureau conducted a raid at "
        "Flat 4B, Sunrise Apartments, Vile Parle, Mumbai. The accused, Aakash Mehta, aged 31, "
        "was present in the flat. During the search, officers recovered 52 grams of heroin "
        "concealed inside a hollow book on a bookshelf. The flat is rented in Aakash's name. "
        "A mobile phone found on Aakash contained encrypted WhatsApp messages referencing "
        "'deliveries' and quantities consistent with drug transactions. Cash of Rs 2.3 lakh "
        "was found in a drawer. The search was authorised by a gazetted officer under Section "
        "42 NDPS but without a prior magistrate's warrant. No independent witness was present."
    ),
    # ── Clear prosecution win (early exit likely) ──────────────────────────────
    "Restaurant stabbing — CCTV + DNA + 4 witnesses (BNS, Nov 2024)": (
        "On 22 November 2024, at approximately 9:10 PM, the accused Deepak Rao, aged 34, "
        "entered 'Spice Garden' restaurant in Indiranagar, Bengaluru, where the victim Suresh "
        "Nair, aged 40, was dining with his family. Deepak approached Suresh's table, produced "
        "a 6-inch kitchen knife, and stabbed Suresh four times in the chest and abdomen in full "
        "view of the restaurant. Suresh was declared dead on arrival at Manipal Hospital at "
        "10:02 PM. The entire attack — lasting 38 seconds — was captured on three high-resolution "
        "restaurant CCTV cameras, with clear facial footage of the accused. Four adult diners at "
        "adjacent tables provided independent eyewitness statements identifying Deepak as the "
        "attacker. The knife was recovered at the scene; forensic analysis confirmed Deepak's "
        "fingerprints on the handle and DNA matching Suresh on the blade. Deepak's mobile phone "
        "records show 23 unanswered calls to Suresh in the 48 hours before the incident. Text "
        "messages recovered from the phone contain explicit death threats sent the previous evening. "
        "Deepak claims the stabbing was accidental during a 'scuffle', but no witness observed "
        "any altercation initiated by Suresh. Deepak has a prior conviction for assault in 2021."
    ),
    # ── Clear defence win (early exit likely) ─────────────────────────────────
    "Robbery — mistaken identity, iron-clad alibi (BNS, Oct 2024)": (
        "On 5 October 2024, at 11:30 PM, an armed robbery occurred at a petrol station in "
        "Andheri West, Mumbai. The attendant, Ramesh Patil, described the robber as a male, "
        "approximately 5'8\", wearing a red hoodie, with a partial face cover. Rs 48,000 in cash "
        "was taken at knifepoint. Three days later, police arrested the accused Farhan Shaikh, "
        "aged 26, based solely on Ramesh's identification from a photo lineup of six photographs. "
        "No weapon was recovered from Farhan. No fingerprints or DNA were collected at the scene. "
        "The petrol station CCTV footage was of poor quality (720p, partially obstructed) and "
        "does not capture the robber's face. Critically, Farhan produces the following alibi: "
        "on the night of 5 October, he had boarded IndiGo Flight 6E-884 from Mumbai to Kolkata "
        "at 9:45 PM (boarding pass and airline PNR on record). The flight departed at 10:20 PM "
        "and landed in Kolkata at 12:55 AM. Hotel check-in records at Kolkata's Ibis Hotel at "
        "1:30 AM corroborate his arrival. A co-passenger, Ms. Anita Roy, confirms sitting next "
        "to Farhan for the entire flight. Two weeks after Farhan's arrest, the actual robber — "
        "matching the physical description and wearing an identical red hoodie — was caught "
        "committing a second robbery at a nearby petrol station."
    ),
    # ── Contested — legal question genuinely ambiguous ────────────────────────
    "Self-defence homicide — right of private defence disputed (IPC, Apr 2024)": (
        "On 18 April 2024, at approximately 2:15 AM, the accused Santosh Pillai, aged 52, "
        "owner of 'Pillai Jewellers' in T. Nagar, Chennai, was sleeping in the back room of "
        "his locked shop when he was awakened by the sound of breaking glass. He found Muniyandi, "
        "aged 28, inside the shop having forced entry by breaking a rear window. Santosh confronted "
        "the intruder and, during the altercation, stabbed Muniyandi twice with a pair of scissors "
        "he had grabbed from the counter. Muniyandi died at Government Stanley Hospital two hours "
        "later. Forensic examination found that Muniyandi was unarmed — he carried only a "
        "flathead screwdriver used to force the window. No jewellery was found on his person. "
        "Post-mortem confirms death from internal haemorrhage caused by the stab wounds. Santosh "
        "claims he acted in reasonable fear of death or grievous hurt to himself and to protect his "
        "property. The prosecution argues the force used was grossly disproportionate — Muniyandi "
        "had no weapon capable of causing death, and Santosh could have retreated or raised an alarm. "
        "Neighbours confirm they heard shouting and could have been alerted. Santosh had previously "
        "threatened Muniyandi (who had worked briefly as a cleaner at the shop) in a public dispute "
        "three months earlier over alleged petty theft of Rs 500."
    ),
    "Cheque dishonour — intent to defraud disputed (NI Act / BNS, Jan 2025)": (
        "On 10 January 2025, a cheque for Rs 18 lakh drawn by the accused Priya Nambiar, "
        "aged 44, director of Nambiar Exports Pvt. Ltd., in favour of the complainant "
        "Vijayakumar Textiles was returned unpaid by Canara Bank with the memo 'Funds Insufficient'. "
        "Vijayakumar Textiles supplied 2,000 metres of premium silk fabric on credit in November "
        "2024, and the cheque was issued as payment. Priya claims the cheque was a security "
        "instrument, not a payment cheque, and that payment was to be made in instalments once a "
        "letter of credit from a UAE buyer was realised. The complainant denies any oral instalment "
        "agreement and says the cheque was unconditional. Email correspondence between the parties "
        "shows Priya writing 'please hold the cheque until I confirm LC realisation' — the complainant "
        "never replied to this email before presenting the cheque. Priya's company account shows "
        "that the UAE LC was indeed delayed due to a documentary error at the correspondent bank, "
        "and was realised on 5 February 2025 — 26 days after the cheque bounce. Priya made full "
        "payment of Rs 18 lakh on 8 February 2025, which the complainant accepted under protest. "
        "The complainant argues the statutory notice under Section 138 NI Act was issued and "
        "ignored for 15 days before filing the complaint."
    ),
    "Cybercrime — data theft, shared device defence (BNS/IT Act, Mar 2025)": (
        "On 3 March 2025, the cybercrime branch of the Delhi Police arrested Arjun Mehrotra, "
        "aged 23, a final-year computer science student at Delhi Technological University, on "
        "charges of unauthorised access and data theft under the Information Technology Act 2000 "
        "and BNS Section 316 (cheating by personation). The complaint was filed by FinTechPro "
        "Pvt. Ltd., which alleged that phishing pages mimicking its customer login portal were "
        "hosted from an IP address registered to Arjun's student dormitory room. The phishing kit "
        "— a fully functional replica of the FinTechPro login page — was found in a folder named "
        "'project_backup' on a laptop seized from his room. 47 customer credentials were "
        "harvested; of these, 12 accounts were accessed and a total of Rs 3.4 lakh was transferred "
        "to mule accounts. The laptop's browser history shows access to hacking forums. Arjun "
        "denies all charges. He states the laptop was shared by four roommates who all had the "
        "password, and that the 'project_backup' folder was already present when he bought the "
        "second-hand device. He produces a receipt showing the laptop was purchased from a "
        "refurbisher. No biometric or keystroke-level logs tie the specific phishing-kit access "
        "events to Arjun personally. One roommate has provided an affidavit stating he too used "
        "the laptop regularly for 'personal work' without elaborating."
    ),
}


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    _init_state()
    st.markdown(CSS, unsafe_allow_html=True)

    corpus_ok = _corpus_ready()
    badge_cls = "ny-badge" if corpus_ok else "ny-badge missing"
    badge_text = "Corpus loaded" if corpus_ok else "Corpus not built"
    st.markdown(f"""
<div class='ny-header'>
  <div style='display:flex;align-items:baseline;gap:1rem'>
    <h1 class='ny-wordmark'>Ny&#257;ya</h1>
    <span class='ny-tagline'>Adversarial Legal Reasoning &middot; Indian Law</span>
  </div>
  <span class='{badge_cls}'>{badge_text}</span>
</div>""", unsafe_allow_html=True)

    if not corpus_ok:
        st.warning(
            "Legal corpus not built — citation validation will not work. "
            "Run `python -m ingestion.build_corpus` to build the RAG corpus."
        )

    if st.session_state.phase == "idle":
        st.markdown("<div class='ny-section'>Fact Scenario</div>", unsafe_allow_html=True)
        sample = st.selectbox("Load a sample", options=list(SAMPLE_CASES.keys()), label_visibility="collapsed")
        prefill = SAMPLE_CASES.get(sample, "")
        facts = st.text_area("Facts", value=prefill, height=180,
            placeholder="Describe the facts of the case in detail — who, what, when, where, what evidence exists.",
            label_visibility="collapsed")

        st.markdown("<div class='ny-section' style='margin-top:1rem'>Offence Date <span style='color:#C05050'>*</span></div>", unsafe_allow_html=True)
        st.markdown(
            "<p style='color:var(--text-muted);font-size:0.75rem;margin-bottom:0.5rem'>"
            "The offence date determines whether BNS (on/after 1 Jul 2024) or IPC (before 1 Jul 2024) applies. "
            "Select using the picker or type a date below.</p>",
            unsafe_allow_html=True,
        )
        date_col_pick, date_col_text = st.columns([2, 3])
        with date_col_pick:
            picked_date = st.date_input(
                "Pick a date",
                value=None,
                min_value=date(1950, 1, 1),
                max_value=date(2099, 12, 31),
                label_visibility="collapsed",
            )
        with date_col_text:
            typed_date = st.text_input(
                "Or type a date",
                value="",
                placeholder="e.g. 15-08-2024 or 2024-08-15",
                label_visibility="collapsed",
            )

        col_btn, col_note = st.columns([2, 6])
        with col_btn:
            go = st.button("Convene Court", type="primary", use_container_width=True)
        with col_note:
            st.markdown("<p style='color:var(--text-muted);font-size:0.73rem;margin-top:0.5rem'>Educational simulation only &mdash; not legal advice.</p>", unsafe_allow_html=True)
        if go:
            _DATE_FMTS_UI = ["%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%B %d, %Y", "%d %B %Y"]
            resolved_date: str | None = None

            # Free-text takes priority if provided; fall back to picker
            if typed_date.strip():
                from datetime import datetime as _dt  # noqa: PLC0415
                parsed_ok = False
                for fmt in _DATE_FMTS_UI:
                    try:
                        resolved_date = _dt.strptime(typed_date.strip(), fmt).strftime("%Y-%m-%d")
                        parsed_ok = True
                        break
                    except ValueError:
                        pass
                if not parsed_ok:
                    st.error(
                        f"Could not parse '{typed_date}' as a date. "
                        "Try formats like 15-08-2024, 2024-08-15, or 15 August 2024."
                    )
                    resolved_date = None
            elif picked_date is not None:
                resolved_date = picked_date.strftime("%Y-%m-%d")

            if not facts.strip():
                st.error("Please enter a fact scenario before convening court.")
            elif resolved_date is None:
                st.error("Please provide the offence date — it determines which law applies (BNS or IPC).")
            else:
                cutover = date(2024, 7, 1)
                from datetime import datetime as _dt2  # noqa: PLC0415
                _d = _dt2.strptime(resolved_date, "%Y-%m-%d").date()
                regime_preview = "BNS" if _d >= cutover else "IPC"
                st.info(f"Offence date: **{resolved_date}** → applying **{regime_preview}**")
                st.session_state.facts_raw = facts.strip()
                st.session_state.offence_date = resolved_date
                st.session_state.phase = "running"
                st.rerun()

    elif st.session_state.phase == "running":
        st.markdown(f"<p style='color:var(--text-muted);font-size:0.8rem;margin-bottom:1.5rem'>{st.session_state.facts_raw[:220]}{'…' if len(st.session_state.facts_raw) > 220 else ''}</p>", unsafe_allow_html=True)
        _run_pre_hitl(st.session_state.facts_raw, st.session_state.offence_date)
        st.rerun()

    elif st.session_state.phase == "awaiting_hitl":
        facts_preview = st.session_state.facts_raw[:220] + ("…" if len(st.session_state.facts_raw) > 220 else "")
        st.markdown(f"<p style='color:var(--text-muted);font-size:0.8rem;margin-bottom:0.25rem'>{facts_preview}</p>", unsafe_allow_html=True)
        st.markdown(_progress_html(), unsafe_allow_html=True)
        _render_all()
        audit = st.session_state.audit_result or {}
        hallucinated = audit.get("hallucinated_citations", [])
        unverified_precedents = audit.get("unverified_precedents", [])
        caution = ""
        flagged = hallucinated + unverified_precedents
        if flagged:
            flagged_str = ", ".join(flagged)
            caution = f"<br><strong style='color:#C05050'>Caution:</strong> The following citations were not verified: {flagged_str}"

        max_rounds = int(os.getenv("MOOT_COURT_MAX_ROUNDS", "5"))
        rounds_done = len([r for r in st.session_state.rounds if r.get("score")])
        can_argue_more = rounds_done < max_rounds
        round_word = "round" if rounds_done == 1 else "rounds"
        st.markdown(f"""
<div class=\'ny-section\'>Verdict Gate</div>
<div class=\'ny-hitl\'>
  <div class=\'ny-hitl-title\'>Rule now, or hear more argument?</div>
  <div class=\'ny-hitl-body\'>{rounds_done} {round_word} argued so far. You can deliver the verdict now, or send both advocates back to argue another round before the judge rules.{caution}</div>
</div>""", unsafe_allow_html=True)
        c1, c2, _ = st.columns([2, 2, 4])
        with c1:
            if st.button("⚖ Deliver Verdict", type="primary", use_container_width=True):
                st.session_state.phase = "post_hitl_approved"
                st.rerun()
        with c2:
            another = st.button(
                "↩ Hear Another Round",
                use_container_width=True,
                disabled=not can_argue_more,
                help=(
                    "Both advocates argue one more round, then you return here to decide again."
                    if can_argue_more
                    else f"The {max_rounds}-round limit has been reached — you can only deliver the verdict."
                ),
            )
            if another:
                st.session_state.phase = "post_hitl_rejected"
                st.rerun()
        if not can_argue_more:
            st.markdown(
                f"<p style='color:var(--text-muted);font-size:0.72rem;margin-top:0.4rem'>"
                f"Maximum of {max_rounds} rounds reached — the trial can only proceed to verdict.</p>",
                unsafe_allow_html=True,
            )

    elif st.session_state.phase in ("post_hitl_approved", "post_hitl_rejected"):
        _render_all()
        _run_post_hitl(st.session_state.phase == "post_hitl_approved")
        st.rerun()

    elif st.session_state.phase == "done":
        st.markdown(_progress_html(), unsafe_allow_html=True)
        _render_all()
        if st.session_state.verdict:
            st.markdown(_verdict_html(st.session_state.verdict, st.session_state.rounds), unsafe_allow_html=True)
            st.markdown(_conclusion_html(), unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Start New Case"):
            _reset()
            st.rerun()

    elif st.session_state.phase == "error":
        st.error(f"An error occurred: {st.session_state.error_msg}")
        if st.button("Reset and try again"):
            _reset()
            st.rerun()


if __name__ == "__main__":
    main()
