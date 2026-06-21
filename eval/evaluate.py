"""Run all 5 evaluation cases and report pass/fail for each check.

Usage:
    python -m eval.evaluate
    python -m eval.evaluate --case 01_clear_liability
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

load_dotenv()

CASES_DIR = Path(__file__).parent / "cases"
console = Console()


def _run_case(case_data: dict) -> dict:
    """Run a single case through the graph (auto-approve HITL) and return final state."""
    from cli.run_case import run

    facts = case_data["facts"]
    final_state = run(facts, auto_approve=True)
    return final_state


def _check_case(case_data: dict, final_state: dict) -> list[dict]:
    """Return a list of {check, passed, detail} dicts."""
    expected = case_data.get("expected", {})
    results = []

    # Check 1: Code regime routing
    if "code_regime" in expected:
        case_file = final_state.get("case_file", {})
        if isinstance(case_file, dict):
            actual_regime = case_file.get("code_regime", "")
        else:
            actual_regime = getattr(case_file, "code_regime", "")
        passed = actual_regime == expected["code_regime"]
        results.append({
            "check": "Code regime routing",
            "passed": passed,
            "detail": f"expected={expected['code_regime']}, got={actual_regime}",
        })

    # Check 2: Expected ruling
    exp_ruling = expected.get("expected_ruling", "any")
    if exp_ruling != "any":
        verdict = final_state.get("verdict") or {}
        actual_ruling = verdict.get("ruling", "")
        passed = actual_ruling == exp_ruling
        results.append({
            "check": "Ruling",
            "passed": passed,
            "detail": f"expected={exp_ruling}, got={actual_ruling}",
        })

    # Check 3: Minimum rounds
    min_rounds = expected.get("expected_round_min", 1)
    actual_rounds = final_state.get("current_round", 1)
    passed = actual_rounds >= min_rounds
    results.append({
        "check": f"Rounds ≥ {min_rounds}",
        "passed": passed,
        "detail": f"actual rounds completed={actual_rounds}",
    })

    # Check 4: Audit passed (always required)
    audit_passed = final_state.get("audit_passed", False)
    results.append({
        "check": "Audit passed (no hallucinations)",
        "passed": audit_passed,
        "detail": f"audit_passed={audit_passed}",
    })

    # Check 5: Verdict has disclaimer
    verdict = final_state.get("verdict") or {}
    has_disclaimer = bool(verdict.get("disclaimer", ""))
    results.append({
        "check": "Verdict disclaimer present",
        "passed": has_disclaimer,
        "detail": "disclaimer field non-empty",
    })

    # Check 6: Key statutes referenced (best-effort)
    key_statutes = expected.get("key_statutes_should_appear", [])
    if key_statutes:
        transcript = final_state.get("round_transcript", [])
        all_cited = []
        for arg in transcript:
            all_cited.extend(arg.get("statutes_cited", []))
        cited_str = " ".join(all_cited).lower()
        found = [s for s in key_statutes if s.lower().split(" section ")[0] in cited_str or s.lower() in cited_str]
        passed = len(found) > 0
        results.append({
            "check": "Key statutes cited",
            "passed": passed,
            "detail": f"expected any of {key_statutes}, found {found}",
        })

    return results


def run_evaluation(case_ids: list[str] | None = None) -> bool:
    """Run evaluation. Returns True if all cases pass all checks."""
    case_files = sorted(CASES_DIR.glob("*.json"))
    if case_ids:
        case_files = [f for f in case_files if any(cid in f.stem for cid in case_ids)]

    if not case_files:
        console.print("[red]No case files found.[/red]")
        return False

    summary_table = Table(title="📊 Evaluation Summary", show_lines=True)
    summary_table.add_column("Case", style="bold")
    summary_table.add_column("Checks", justify="right")
    summary_table.add_column("Passed", justify="right")
    summary_table.add_column("Status", justify="center")

    all_passed = True

    for case_file in case_files:
        case_data = json.loads(case_file.read_text())
        case_name = case_data.get("name", case_file.stem)
        console.rule(f"[bold cyan]Running: {case_name}[/bold cyan]")

        try:
            final_state = _run_case(case_data)
            checks = _check_case(case_data, final_state)
        except Exception as exc:
            console.print(f"[red]ERROR: {exc}[/red]")
            summary_table.add_row(case_name[:50], "—", "—", "[red]ERROR[/red]")
            all_passed = False
            continue

        n_checks = len(checks)
        n_passed = sum(1 for c in checks if c["passed"])
        case_passed = n_passed == n_checks
        all_passed = all_passed and case_passed

        # Per-check detail
        detail_table = Table(show_header=True)
        detail_table.add_column("Check")
        detail_table.add_column("Result", justify="center")
        detail_table.add_column("Detail")
        for c in checks:
            icon = "✓" if c["passed"] else "✗"
            color = "green" if c["passed"] else "red"
            detail_table.add_row(c["check"], f"[{color}]{icon}[/{color}]", c["detail"])
        console.print(detail_table)

        status = "[green]PASS[/green]" if case_passed else "[red]FAIL[/red]"
        summary_table.add_row(case_name[:50], str(n_checks), str(n_passed), status)

    console.print(summary_table)
    overall = "[green]ALL PASSED[/green]" if all_passed else "[red]SOME FAILED[/red]"
    console.print(f"\nOverall result: {overall}")
    return all_passed


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run AI Moot Court evaluation suite")
    parser.add_argument("--case", nargs="+", help="Filter by case ID prefix (e.g. 01 03)")
    args = parser.parse_args()

    passed = run_evaluation(case_ids=args.case)
    sys.exit(0 if passed else 1)
