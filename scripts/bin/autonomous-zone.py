#!/usr/bin/env python3
"""What an agent may do unattended, and what still needs Darpan.

Every action here is gated individually, which is right for money mutations and wrong for
everything else: the agent idles whenever nobody is at the keyboard, and a large body of
mechanical work — audits, gate authoring, knowledge upkeep, coverage sweeps — simply never
happens.

This declares the boundary once, so unattended work is a policy rather than a judgement
call made repeatedly under time pressure.

    autonomous-zone.py check "bash scripts/bin/workspace-hygiene.sh --clean"
    autonomous-zone.py list
    autonomous-zone.py run          # execute the safe backlog, stop at the first refusal

**GATED always, no exception, regardless of how safe it looks:**
  - any write to a service repo's source (`trustt-*`, `novopay-*`)
  - git commit / push anywhere
  - Jira transitions or comments
  - any DB write outside localhost:5433
  - anything under `.cursor/rules/` (changes how every future session behaves)

The rule that decides it is `darpan.md`: never write outside the workspace, never push
upstream, never write a remote DB. This encodes the same boundary as a predicate so it
can be checked rather than remembered.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]

# Read-only or workspace-local-only work. Each entry is a command an agent may run with
# nobody watching, plus why it is safe.
SAFE_BACKLOG: list[tuple[str, str]] = [
    ("python3 scripts/lib/harness_audit.py", "read-only audit of the harness"),
    ("python3 scripts/lib/doc_command_gate.py", "read-only; reports dead script paths"),
    # Standing red, and correctly so: the local fixture lags the migrations, so ~150 mapped
    # columns are absent from it. That is an environment state to fix by applying the Flyway
    # SQL, not a code defect and not something to suppress — a column absent locally is the
    # cause of `Unable to find column position by name` at runtime.
    ("python3 scripts/lib/schema_live_drift.py --quiet", "read-only schema comparison"),
    ("python3 scripts/lib/loan_status_sweep_gate.py", "static scan of accounting sources"),
    ("python3 scripts/lib/rules_to_gates.py", "read-only; reports preamble + enforcement"),
    ("python3 scripts/lib/domain_coverage_gate.py", "per-domain coverage ratchet, read-only"),
    ("python3 scripts/testing/transaction_map.py",
     "regenerates the loan transaction map from orchestration + templates + KG"),
    ("python3 scripts/testing/read_inquiry_worklist.py",
     "regenerates the read-API contract worklist from the shipped JTF templates"),
    ("python3 scripts/testing/platform_api_map.py",
     "regenerates the platform-wide API map from every repo's orchestration, templates, "
     "the KG and the api_master registry (read-only)"),
    ("python3 scripts/testing/platform_surface.py",
     "regenerates the event, schedule, data, error, GL and processor maps from the KG"),
    ("python3 scripts/lib/test_platform_surface.py",
     "pins the surface maps to facts established independently of them"),
    ("python3 scripts/lib/test_platform_api_map.py",
     "pins the API map, including agreement with the accounting transaction map"),
    ("python3 scripts/lib/test_batch_read_plan.py",
     "pins the check that catches a batch job planning for rows and reading none (GAP-095), "
     "including a test asserting its partial-loss blind spot"),
    ("python3 scripts/lib/test_file_assert.py",
     "pins file_exists / file_row_count, including that a stale file from an earlier run fails"),
    ("python3 scripts/testing/test_map_builder.py build --apply",
     "regenerates the coverage matrix under cursor-bundle/flow-test"),
    ("bash scripts/bin/workspace-hygiene.sh --clean",
     "removes __pycache__ and orphan temp schemas on localhost only"),
    ("python3 scripts/lib/test_workspace_contract.py", "the workspace's own test suite"),
    ("python3 scripts/testing/autosys_jobs.py",
     "re-reads the production EOD/BOD schedule from the bank's Autosys sheet"),
    ("python3 scripts/testing/loan_flow_worklist.py",
     "regenerates the loan-flow coverage worklist from the maps + registry"),
    # Corroboration compares the intelligence layers against their inputs, so it has to run
    # after everything that regenerates one. Placed earlier it reported test_map and hub as
    # stale on every bulk run — against artefacts the same run was about to rebuild.
    ("bash scripts/bin/super-agent.sh sync", "refreshes the hub from the regenerated maps"),
    ("bash scripts/bin/super-agent.sh corroborate", "read-only state corroboration"),
]

# Deliberately NOT in the backlog: scripts/testing/job_footprint.py --run. It executes real
# EOD/BOD jobs against the shared local DB, and an unattended run would move fixture state
# underneath whoever is mid-investigation. Local DB writes are permitted by darpan.md; running
# the night's batch chain without anyone watching is still the wrong default.

_DENY = [
    (re.compile(r"\bgit\s+(push|commit|merge|rebase|reset|checkout\s+-)", re.I),
     "git history / remote state is never autonomous"),
    (re.compile(r"\b(trustt|novopay)-[a-z-]+/src/", re.I),
     "service source is a money path; edits are gated"),
    (re.compile(r"\.cursor/rules/", re.I),
     "rules change every future session's behaviour"),
    (re.compile(r"\bdb-qa\d?\.sh\b.*--allow-write", re.I),
     "remote DB writes are never permitted"),
    (re.compile(r"\bpsql\b(?!.*(localhost|127\.0\.0\.1))", re.I),
     "psql outside localhost is a remote DB"),
    (re.compile(r"\bjira|atlassian\b", re.I),
     "Jira is outward-facing"),
    (re.compile(r"\b(rm\s+-rf\s+/|--force\b.*push|force-with-lease)", re.I),
     "destructive or history-rewriting"),
    (re.compile(r"\bcurl\b.*\b(POST|PUT|DELETE)\b.*https?://(?!localhost|127\.0\.0\.1)", re.I),
     "outbound mutation to a non-local host"),
]


def classify(command: str) -> tuple[bool, str]:
    for pattern, why in _DENY:
        if pattern.search(command):
            return False, why
    return True, "read-only or workspace-local"


def cmd_check(a) -> int:
    ok, why = classify(a.command)
    print(f"{'AUTONOMOUS' if ok else 'GATED'} — {why}")
    print(f"  {a.command}")
    return 0 if ok else 1


def cmd_list(a) -> int:
    print("safe backlog — runnable unattended:")
    for command, why in SAFE_BACKLOG:
        ok, deny = classify(command)
        mark = " " if ok else "!"
        print(f" {mark} {command}")
        print(f"      {why if ok else 'REFUSED: ' + deny}")
    print("\nalways gated: service source, git, Jira, remote DB, .cursor/rules/")
    return 0


def cmd_run(a) -> int:
    results = []
    for command, why in SAFE_BACKLOG:
        ok, deny = classify(command)
        if not ok:
            print(f"REFUSED {command}\n  {deny}", file=sys.stderr)
            return 2
        print(f"→ {command}", flush=True)
        proc = subprocess.run(command, shell=True, cwd=str(ROOT),
                              capture_output=True, text=True, timeout=a.timeout)
        tail = (proc.stdout or proc.stderr or "").strip().splitlines()[-2:]
        status = "ok" if proc.returncode == 0 else f"rc={proc.returncode}"
        print(f"  {status}: {' | '.join(t.strip()[:90] for t in tail)}")
        results.append({"command": command, "rc": proc.returncode})
        if proc.returncode != 0 and not a.keep_going:
            print("\nstopping at first failure (use --keep-going to continue)", file=sys.stderr)
            break
    failed = [r for r in results if r["rc"] != 0]
    print(f"\n{len(results) - len(failed)}/{len(results)} clean")
    if a.json:
        print(json.dumps(results, indent=1))
    return 1 if failed else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("check")
    c.add_argument("command")
    c.set_defaults(fn=cmd_check)

    l = sub.add_parser("list")
    l.set_defaults(fn=cmd_list)

    r = sub.add_parser("run")
    r.add_argument("--timeout", type=int, default=1800)
    r.add_argument("--keep-going", action="store_true")
    r.add_argument("--json", action="store_true")
    r.set_defaults(fn=cmd_run)

    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
