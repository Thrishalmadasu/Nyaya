"""CLI entry point for the AI Moot Court.

Usage:
    python -m cli.run_case "On 15 August 2024, accused Raj Sharma was caught..."
    python -m cli.run_case --file path/to/case.txt
    python -m cli.run_case --auto   # skip HITL, auto-approve (for eval/demo)
"""
from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path

from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table

load_dotenv()

console = Console()


def _print_argument(arg: dict, round_num: int) -> None:
    side = arg.get("side", "").upper()
    color = "red" if side == "PROSECUTION" else "blue"
    title = f"[{color}]Round {round_num} — {side}[/{color}]"
    claims = "\n".join(f"  • {c}" for c in arg.get("claims", []))
    statutes = ", ".join(arg.get("statutes_cited", [])) or "None"
    precedents = ", ".join(arg.get("precedents_cited", [])) or "None"
    rebuttals = "\n".join(f"  ↩ {r}" for r in arg.get("rebuttals", [])) or "  —"
    body = (
        f"[bold]Claims:[/bold]\n{claims}\n\n"
        f"[bold]Statutes:[/bold] {statutes}\n"
        f"[bold]Precedents:[/bold] {precedents}\n"
        f"[bold]Rebuttals:[/bold]\n{rebuttals}"
    )
    console.print(Panel(body, title=title, border_style=color))


def _print_judge_score(score: dict) -> None:
    table = Table(title=f"⚖️  Judge Score — Round {score.get('round_number')}", show_header=False)
    table.add_column("Field", style="bold")
    table.add_column("Value")
    table.add_row("Prosecution strength", f"{score.get('prosecution_strength')}/10")
    table.add_row("Defence strength", f"{score.get('defence_strength')}/10")
    table.add_row("Weak side", score.get("weak_side", ""))
    table.add_row("Decision", score.get("decision", ""))
    table.add_row("Uncited statutes", ", ".join(score.get("uncited_statutes", [])) or "None")
    table.add_row("Reasoning", score.get("reasoning", "")[:200])
    console.print(table)


def _print_verdict(verdict: dict) -> None:
    ruling = verdict.get("ruling", "").upper()
    color = {"LIABLE": "red", "NOT_LIABLE": "green", "INCONCLUSIVE": "yellow"}.get(ruling, "white")
    confidence = verdict.get("confidence", 0)

    console.print(Rule("FINAL VERDICT", style="bold yellow"))
    console.print(Panel(
        f"[bold {color}]RULING: {ruling}[/bold {color}]\n"
        f"Confidence: {confidence}/10\n\n"
        f"[bold]Reasoning:[/bold]\n{verdict.get('reasoning', '')}\n\n"
        f"[bold]Statutes relied on:[/bold] {', '.join(verdict.get('statutes_relied_on', []))}\n"
        f"[bold]Precedents relied on:[/bold] {', '.join(verdict.get('precedents_relied_on', []))}\n\n"
        f"[italic]{verdict.get('disclaimer', '')}[/italic]",
        title="⚖️  AI Moot Court Verdict",
        border_style="yellow",
    ))


def run(facts: str, auto_approve: bool = False) -> dict:
    from graph.court import get_graph

    graph = get_graph()
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    initial_state = {
        "facts_raw": facts,
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

    console.print(Rule("[bold]AI MOOT COURT[/bold]", style="yellow"))
    console.print(Panel(facts, title="📋 Fact Scenario", border_style="white"))

    # Phase 1: Run until HITL interrupt
    events = list(graph.stream(initial_state, config=config, stream_mode="values"))

    # Print transcript events as they arrive
    seen_rounds: set[tuple] = set()
    seen_scores: set[int] = set()

    for state in events:
        transcript = state.get("round_transcript", [])
        scores = state.get("judge_scores", [])

        for arg in transcript:
            key = (arg.get("side"), arg.get("round_number"))
            if key not in seen_rounds:
                seen_rounds.add(key)
                _print_argument(arg, arg.get("round_number", 1))

        for score in scores:
            rn = score.get("round_number", 0)
            if rn not in seen_scores:
                seen_scores.add(rn)
                _print_judge_score(score)

    # Get latest state
    latest = graph.get_state(config)
    current_state = latest.values

    # Print audit result
    audit = current_state.get("audit_result")
    if audit:
        status = "✓ PASSED" if current_state.get("audit_passed") else "✗ FAILED"
        color = "green" if current_state.get("audit_passed") else "red"
        console.print(Panel(
            f"[{color}]{status}[/{color}]\n"
            f"Verified: {audit.get('verified_citations', [])}\n"
            f"Hallucinated: {audit.get('hallucinated_citations', [])}\n"
            f"Notes: {audit.get('audit_notes', '')}",
            title="🔍 Citation Audit",
            border_style=color,
        ))

    # Phase 2: HITL gate
    if not auto_approve:
        console.print(Rule("HUMAN REVIEW", style="bold magenta"))
        decision = console.input(
            "[bold magenta]Review complete? Type [green]approve[/green] or [red]reject[/red]: [/bold magenta]"
        ).strip().lower()
        approved = decision == "approve"
    else:
        console.print("[dim]Auto-approve mode — skipping HITL.[/dim]")
        approved = True

    # Resume graph with HITL decision via LangGraph Command
    from langgraph.types import Command

    resume_value = "approve" if approved else "reject"
    resume_events = list(
        graph.stream(Command(resume=resume_value), config=config, stream_mode="values")
    )

    # Print final verdict
    final_state = graph.get_state(config).values
    verdict = final_state.get("verdict")
    if verdict:
        _print_verdict(verdict)

    return final_state


def main() -> None:
    parser = argparse.ArgumentParser(description="AI Moot Court — run a legal case")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("facts", nargs="?", help="Fact scenario as a string")
    group.add_argument("--file", type=Path, help="Path to a .txt file with the fact scenario")
    parser.add_argument("--auto", action="store_true", help="Auto-approve HITL (for eval/demo)")
    parser.add_argument("--json", action="store_true", help="Output final state as JSON")
    args = parser.parse_args()

    if args.file:
        facts = args.file.read_text(encoding="utf-8").strip()
    else:
        facts = args.facts

    if not facts:
        console.print("[red]Error: no fact scenario provided[/red]")
        sys.exit(1)

    final_state = run(facts, auto_approve=args.auto)

    if args.json:
        print(json.dumps(final_state.get("verdict", {}), indent=2, default=str))


if __name__ == "__main__":
    main()
