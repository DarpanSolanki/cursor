#!/usr/bin/env python3
"""Which always-on mandates are enforced by a gate, and which still rely on memory.

The always-on preamble is ~10.7k tokens loaded before any work starts. Compliance with a
corpus that size is probabilistic, and it degrades exactly when the task is hard. In one
session I skipped `kg_error` on six error codes, skipped the post-ship `kg flow`, and read
a SKIP as a PASS — not from ignorance, but from budget.

Adding rules cannot fix that. What worked was the opposite: the column check, the sweep
gate and the doc-command gate all removed the need to remember anything.

**A rule that asks an agent to be careful is a gate that has not been written yet.**

This tool keeps that honest. It reports:

  enforced    — a gate exists; the prose can shrink to a pointer
  unenforced  — memory is the only enforcement; candidate for a new gate
  preamble    — current always-on token cost, ratcheted so it cannot creep back

  rules_to_gates.py                 report
  rules_to_gates.py --unenforced    only what still depends on memory
  rules_to_gates.py --accept        record the current preamble size as the ceiling
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[2]
BASELINE = ROOT / "cursor-bundle" / "flow-test" / "preamble_baseline.json"

# mandate -> the gate that makes remembering it unnecessary.
# Only claims a mandate is enforced when the gate genuinely fails on violation; a gate
# that merely reports is listed as advisory, because a warning is not enforcement.
ENFORCED: list[tuple[str, str, str]] = [
    ("resolve every column before naming it",
     "scripts/lib/sql_column_check.py", "40-knowledge-upkeep"),
    ("never let a query name a column the DB lacks",
     "scripts/db-local.sh + scripts/db/db-qa.sh pre-flight", "40-knowledge-upkeep"),
    ("code maps a column the local DB lacks must be visible",
     "scripts/lib/schema_live_drift.py", "40-knowledge-upkeep"),
    ("no assert or SQL may name a missing column",
     "scripts/lib/schema_ref_gate.py", "10-quality-gates"),
    ("every referenced script path must exist",
     "scripts/lib/doc_command_gate.py", "00-workspace-core"),
    ("hooks.json and settings.json stay in sync",
     "scripts/lib/harness_audit.py::check_hooks", "00-workspace-core"),
    ("every gate must be wired to a host",
     "scripts/lib/harness_audit.py::check_wiring", "20-ship-gates"),
    ("no new presence-only assert",
     "scripts/bin/assert-strength-gate.py", "40-knowledge-upkeep"),
    ("money sweeps must not stamp over terminal state",
     "scripts/lib/loan_status_sweep_gate.py", "10-quality-gates"),
    ("money cases must assert universal invariants",
     "scripts/testing/lib/money_invariants.py (ntest guard)", "20-ship-gates"),
    ("mainline push must include the upstream tip",
     "scripts/bin/train-upstream-sync.sh (push-origin)", "upstream-mainline-push-sync"),
    ("no comments in repository layer / comment volume",
     "scripts/lib/java_comment_lint.py", "repository-layer-no-comments"),
    ("registry cases must resolve to real files",
     "scripts/lib/harness_audit.py::check_registry", "20-ship-gates"),
    ("KG must be fresh/valid before money claims",
     "kg_doctor / kg-ensure-fresh.sh", "30-kg-discipline"),
    ("KG lookups must be reachable over MCP",
     "scripts/lib/test_kg_mcp_cli_parity.py", "30-kg-discipline"),
    ("money gap surface must not grow",
     "scripts/testing/corroborate.py::money_proof_gaps ratchet", "20-ship-gates"),
    ("impact tests must run before a money ship",
     "scripts/bin/impact-tests.sh --mark-ran", "20-ship-gates"),
]

# Still memory-only. Each is a candidate for a gate; the note says what would enforce it.
UNENFORCED: list[tuple[str, str, str]] = [
    ("call kg_error before grepping for an error code", "30-kg-discipline",
     "hook on Grep/Bash args matching an error code -> print the kg_error command"),
    ("call kg_schema before grepping for a column's writers", "40-knowledge-upkeep",
     "hook on Grep for set<Field>/snake_case column -> print kg_schema"),
    ("run kg flow with the fix sha after a money ship", "20-ship-gates",
     "post-push hook emitting fix_shipped when a changelog entry names a sha"),
    ("print the OPTIONS BOARD after any analysis", "00-workspace-core",
     "not mechanically checkable — output-shape, stays prose"),
    ("STOP-AND-WAIT before mutating on a money path", "00-workspace-core",
     "harness-level: EnterPlanMode already provides this; rule can point at it"),
    ("state the branch you read alongside a cross-train claim", "40-knowledge-upkeep",
     "not mechanically checkable from outside the answer; stays prose"),
    ("a skip must never be read as a pass", "20-ship-gates",
     "ntest returns a distinct code for SKIP so && cannot swallow it"),
]

_IMPORT = re.compile(r"^@(\.cursor/rules/[a-z0-9-]+\.md)", re.M)


def preamble_files() -> list[pathlib.Path]:
    claude_md = ROOT / ".cursorrules"
    files = [claude_md]
    if claude_md.is_file():
        for rel in _IMPORT.findall(claude_md.read_text(encoding="utf-8")):
            path = ROOT / rel
            if path.is_file():
                files.append(path)
    return files


def preamble_tokens() -> tuple[int, list[tuple[str, int]]]:
    rows: list[tuple[str, int]] = []
    total = 0
    for path in preamble_files():
        words = len(path.read_text(encoding="utf-8").split())
        tokens = words * 4 // 3
        rows.append((str(path.relative_to(ROOT)), tokens))
        total += tokens
    return total, rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--unenforced", action="store_true")
    ap.add_argument("--accept", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    total, rows = preamble_tokens()

    if args.accept:
        BASELINE.parent.mkdir(parents=True, exist_ok=True)
        BASELINE.write_text(json.dumps({"tokens": total}) + "\n", encoding="utf-8")
        print(f"preamble ceiling recorded: {total} tokens")
        return 0

    if args.json:
        print(json.dumps({
            "preamble_tokens": total,
            "files": dict(rows),
            "enforced": len(ENFORCED),
            "unenforced": len(UNENFORCED),
        }, indent=1))
        return 0

    if args.unenforced:
        print(f"still memory-only ({len(UNENFORCED)}):")
        for mandate, rule, how in UNENFORCED:
            print(f"  [{rule}] {mandate}")
            print(f"      -> {how}")
        return 0

    print(f"always-on preamble: {total} tokens across {len(rows)} file(s)")
    for name, tokens in rows:
        print(f"    {tokens:6}  {name}")

    ratio = len(ENFORCED) / max(1, len(ENFORCED) + len(UNENFORCED))
    print(f"\nmandates: {len(ENFORCED)} enforced by a gate, "
          f"{len(UNENFORCED)} memory-only  ({100*ratio:.0f}% enforced)")
    print("  a rule that asks an agent to be careful is a gate that is not written yet")

    ceiling = None
    if BASELINE.is_file():
        try:
            ceiling = int(json.loads(BASELINE.read_text(encoding="utf-8"))["tokens"])
        except (json.JSONDecodeError, KeyError, ValueError, OSError):
            ceiling = None

    if ceiling is None:
        print("\n  no ceiling recorded — run --accept to set one")
        return 0
    if total > ceiling:
        print(f"\n  FAIL — preamble grew {ceiling} -> {total} tokens.")
        print("  Every token here is loaded before any work and competes with the task.")
        print("  Convert a mandate to a gate, or accept deliberately with --accept.")
        return 1
    if total < ceiling:
        print(f"\n  improved: {ceiling} -> {total} tokens; run --accept to lower the ceiling")
    else:
        print(f"\n  holding at the {ceiling}-token ceiling")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
