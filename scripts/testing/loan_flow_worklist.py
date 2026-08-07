#!/usr/bin/env python3
"""What it would take to cover every loan flow the webapp starts and every account batch job.

Two entry points own the loan account's life. The webapp starts a flow because someone clicked
something, and a batch job starts one because the clock said so — and the second is the one
nobody watches, because EOD and BOD run at night and are only noticed when the morning numbers
are wrong.

This turns that into a worklist instead of an intention. Every row is a flow that reaches a
loan account, with what is already known about it, what is missing before a test could drive
it, and the one action that would move it. Ordered so the money-writing, production-scheduled
work sits at the top.

A hand-written task list goes stale the week after it is written. This is generated from the
maps, so it re-derives itself and the count going down is real progress rather than a claim.

    loan_flow_worklist.py                 write the worklist + the plan
    loan_flow_worklist.py --ui            only webapp-initiated flows
    loan_flow_worklist.py --batch         only batch / EOD / BOD jobs
    loan_flow_worklist.py --ready         only what the current fixture could drive today
    loan_flow_worklist.py --top 20        the highest-priority rows
"""
from __future__ import annotations

import argparse
import collections
import json
import pathlib
import re
import sqlite3
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
FLOW = ROOT / "cursor-bundle" / "flow-test"
KGDB = ROOT / "cursor-bundle" / "kg" / "data" / "kg.db"
OUT = FLOW / "loan_flow_worklist.jsonl"
DOC = ROOT / ".cursor" / "loan-flow-coverage-plan.md"
REGISTRY = ROOT / "scripts" / "testing" / "registry.json"

LOAN = re.compile(r"loan|disburs|repay|foreclos|prepay|emi|installment|accrual|billing|dpi|"
                  r"writeoff|reschedul|restructur|closure|refund|charge|collection|clmt|"
                  r"eod|bod|asset|dpd|penal|moratorium|lien", re.I)
JOBLIKE = re.compile(r"(Job|Batch|BatchApi)$|^run", re.I)

EOD_ROOTS = ("runEODJobs", "runBODJobs", "runDayEndJobs")

# The tables that mean a loan's money moved. A flow writing one of these is money-tier
# whatever its name suggests.
MONEY_TABLES = {
    "loan_account", "loan_due_details", "loan_installment_details", "loan_transaction_details",
    "loan_account_payments_details", "loan_account_closure_details", "loan_account_charge_details",
    "interest_accrual_details", "dpi_accrual_details", "loan_account_events_queue",
    "account_balance", "gl_transaction", "loan_account_tax_details",
}


def load(name: str) -> list[dict]:
    path = FLOW / name
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.startswith("#")]


def registry_index() -> tuple[dict[str, list[str]], dict[str, str]]:
    """Which registry cases name each API, and the strongest verify mode any of them declares."""
    if not REGISTRY.is_file():
        return {}, {}
    reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
    cases: dict[str, list[str]] = collections.defaultdict(list)
    best: dict[str, str] = {}
    # The registry writes these in both cases and both spellings: `runtime` (80 cases) and
    # `RUNTIME_VERIFIED` (6) mean the same thing. Ranking only the uppercase form reported
    # 1 flow covered out of 231, which was a bug in this script, not a fact about the suite.
    rank = {"runtime_verified": 4, "runtime": 4, "stage_partial": 3, "orch_sibling_sim": 2,
            "processor_mirror_sim": 1, "workspace_only": 1, "static_gate": 1}
    for cid, case in reg.items():
        if not isinstance(case, dict):
            continue
        api = case.get("api")
        if not api:
            continue
        cases[api].append(cid)
        mode = (case.get("verify_mode") or "").strip().lower()
        if rank.get(mode, 0) > rank.get(best.get(api, ""), 0):
            best[api] = mode
    return dict(cases), best


def eod_chain() -> dict[str, int]:
    """Flows reachable from the EOD/BOD entry points, with how deep in the chain they sit."""
    if not KGDB.is_file():
        return {}
    con = sqlite3.connect(f"file:{KGDB}?mode=ro", uri=True)
    by_name: dict[str, set] = collections.defaultdict(set)
    for (rid,) in con.execute("SELECT id FROM nodes WHERE kind='request'"):
        by_name[rid.split("/")[-1]].add(rid)
    graph: dict[str, set] = collections.defaultdict(set)
    for src, dst in con.execute(
            "SELECT src_id, dst_id FROM edges WHERE rel IN ('calls','calls_api') "
            "AND src_id LIKE 'request:%'"):
        graph[src] |= ({dst} if dst.startswith("request:")
                       else by_name.get(dst.split(":", 1)[1], set()))
    con.close()

    depth: dict[str, int] = {}
    frontier = [rid for root in EOD_ROOTS for rid in by_name.get(root, ())]
    for rid in frontier:
        depth[rid.split("/")[-1]] = 0
    level = 0
    while frontier and level < 6:
        nxt = []
        for node in frontier:
            for child in graph.get(node, ()):
                name = child.split("/")[-1]
                if name not in depth:
                    depth[name] = level + 1
                    nxt.append(child)
        frontier, level = nxt, level + 1
    return depth


def scheduled() -> dict[str, list[str]]:
    out: dict[str, list[str]] = collections.defaultdict(list)
    for row in load("platform_schedulers.jsonl"):
        for target in row["triggers"]:
            out[target.split("/")[-1]].append(row["scheduler"])
    return dict(out)


def classify(row: dict, eod: dict, sched: dict, cases: dict, best: dict) -> dict | None:
    api = row["api"]
    money_tables = sorted(set(row["tables_written"]) & MONEY_TABLES)
    ui = bool(row.get("ui_reachable"))
    in_eod = api in eod
    jobs = sched.get(api, [])
    is_job = bool(JOBLIKE.search(api)) or bool(jobs) or in_eod

    if not LOAN.search(api) and not money_tables:
        return None
    if not (ui or is_job):
        return None

    has_case = bool(cases.get(api))
    verify = best.get(api, "")
    proven = verify in ("runtime", "runtime_verified")

    blockers = []
    if not row["orchestration"]:
        blockers.append("no orchestration — driven internally, needs a parent to enter through")
    if not row["request_template"]:
        blockers.append("no JTF request template — no HTTP contract to build a request from")
    if not row["processors"]:
        blockers.append("no processors indexed")

    if proven:
        action = "covered — keep the assert honest when the flow changes"
    elif has_case:
        action = (f"case exists ({', '.join(cases[api][:2])}) but verify_mode is "
                  f"{verify or 'undeclared'} — drive it for real and assert exact columns")
    elif blockers:
        action = "resolve the blocker, then write a value-level case"
    elif row["mutating"] and money_tables:
        action = ("write a money case: seed the fixture, run the real flow, assert exact "
                  f"values on {', '.join(money_tables[:3])}")
    elif row["mutating"]:
        action = "write a service case: run the real flow, assert the rows it writes"
    else:
        action = "write a read case from the JTF response template"

    priority = (
        (0 if money_tables and (in_eod or jobs) else
         1 if money_tables and ui else
         2 if in_eod or jobs else
         3 if row["mutating"] else 4),
        -len(row["tables_written"]),
        api,
    )
    return {
        "api": api, "repo": row["repo"],
        "entry": ("batch+ui" if (ui and is_job) else "batch" if is_job else "ui"),
        "eod_depth": eod.get(api),
        "schedulers": jobs,
        "mutating": row["mutating"],
        "money_tables": money_tables,
        "tables_written": row["tables_written"],
        "processors": len(row["processors"]),
        "orchestration": row["orchestration"],
        "request_template": row["request_template"],
        "registry_cases": cases.get(api, []),
        "verify_mode": verify,
        "covered": proven,
        "blockers": blockers,
        "ready": not blockers,
        "action": action,
        "_priority": priority,
    }


def build() -> list[dict]:
    api_rows = load("platform_api_map.jsonl")
    cases, best = registry_index()
    eod, sched = eod_chain(), scheduled()
    rows = [r for r in (classify(a, eod, sched, cases, best) for a in api_rows) if r]
    rows.sort(key=lambda r: r["_priority"])
    for r in rows:
        r.pop("_priority")
    return rows


def markdown(rows: list[dict]) -> str:
    todo = [r for r in rows if not r["covered"]]
    ui = [r for r in rows if r["entry"] in ("ui", "batch+ui")]
    batch = [r for r in rows if r["entry"] in ("batch", "batch+ui")]
    money = [r for r in rows if r["money_tables"]]
    eod = sorted((r for r in rows if r["eod_depth"] is not None),
                 key=lambda r: (r["eod_depth"], r["api"]))
    ready = [r for r in todo if r["ready"]]
    blocked = [r for r in todo if not r["ready"]]

    out = ["# Loan flow coverage plan (generated — do not hand-edit)", "",
           "`python3 scripts/testing/loan_flow_worklist.py` regenerates this from the platform",
           "maps and the registry. Every loan-account flow the webapp starts or a batch job runs,",
           "with what is missing and the one action that would move it.",
           "",
           "A hand-written task list is stale the week after it is written. This one re-derives",
           "itself, so the number going down is progress rather than a claim.",
           "",
           "## Scope", "",
           "| | Count |",
           "|---|---:|",
           f"| Loan flows reachable from the webapp | {len(ui)} |",
           f"| Loan flows run by a batch job or scheduler | {len(batch)} |",
           f"| Of those, writing a money table | {len(money)} |",
           f"| In the EOD/BOD chain | {len(eod)} |",
           f"| **Proven covered** (`RUNTIME_VERIFIED`) | **{len(rows) - len(todo)}** |",
           f"| **Still to do** | **{len(todo)}** |",
           f"| — of which the current fixture could drive today | {len(ready)} |",
           f"| — of which blocked on a contract or an entry point | {len(blocked)} |",
           "",
           "Coverage means the flow was **run for real and its columns asserted**. A registry",
           "case that has never run is not coverage; `40-knowledge-upkeep.md` calls a",
           "presence-only assert what it is.",
           "",
           "## EOD / BOD chain", "",
           "The jobs production runs unattended, in call order from the entry point. Depth 0 is",
           "the entry; anything deeper runs because something above it called it.", ""]
    if eod:
        out += ["| Depth | Flow | Writes | Case | Action |", "|---:|---|---:|---|---|"]
        out += [f"| {r['eod_depth']} | `{r['api']}` | {len(r['tables_written'])} | "
                f"{'yes' if r['registry_cases'] else '—'} | {r['action'][:64]} |" for r in eod]
    else:
        out.append("_No EOD entry point resolved — check `runEODJobs` is in the API map._")

    out += ["", "## Highest priority — money, scheduled, uncovered", "",
            "These write a money table and run on a schedule, so a defect lands overnight with",
            "nobody watching.", "",
            "| Flow | Repo | Entry | Money tables | Action |", "|---|---|---|---|---|"]
    top = [r for r in todo if r["money_tables"] and r["entry"] != "ui"][:20]
    out += [f"| `{r['api']}` | {r['repo'].replace('trustt-platform-','')} | {r['entry']} | "
            f"{', '.join('`'+t+'`' for t in r['money_tables'][:3])} | {r['action'][:70]} |"
            for r in top] or ["| _none_ | | | | |"]

    out += ["", "## Webapp-initiated, money-writing, uncovered", "",
            "| Flow | Repo | Money tables | Action |", "|---|---|---|---|"]
    top_ui = [r for r in todo if r["money_tables"] and r["entry"] in ("ui", "batch+ui")][:20]
    out += [f"| `{r['api']}` | {r['repo'].replace('trustt-platform-','')} | "
            f"{', '.join('`'+t+'`' for t in r['money_tables'][:3])} | {r['action'][:70]} |"
            for r in top_ui] or ["| _none_ | | | |"]

    reasons = collections.Counter(b for r in blocked for b in r["blockers"])
    out += ["", "## Blocked, and why", "",
            "Not laziness — these need something resolved before a test could exist.", ""]
    out += [f"- **{n}** — {reason}" for reason, n in reasons.most_common()]
    out += ["",
            "`child*` flows dominate the no-template group: the parent drives them internally,",
            "so there is no gateway contract to build a request from. They are covered by",
            "driving the parent, not by inventing an entry point.", "",
            "## How to work it", "",
            "1. Take the top table first — money plus a schedule is the worst place for a gap.",
            "2. Drive the **real** flow locally; `run-the-real-thing-locally.md` is not optional",
            "   here, and seeding the rows the job was meant to write proves nothing.",
            "3. Assert exact column values, and watch the assert fail before the fix.",
            "4. Add the case to `scripts/testing/registry.json` with a real `verify_mode`.",
            "5. Re-run this script — the count moves on its own.", ""]
    return "\n".join(out) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--ui", action="store_true")
    ap.add_argument("--batch", action="store_true")
    ap.add_argument("--ready", action="store_true")
    ap.add_argument("--top", type=int)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    rows = build()
    if not rows:
        print("no rows — build the platform maps first "
              "(platform_api_map.py, platform_surface.py)", file=sys.stderr)
        return 2

    view = rows
    if args.ui:
        view = [r for r in view if r["entry"] in ("ui", "batch+ui")]
    if args.batch:
        view = [r for r in view if r["entry"] in ("batch", "batch+ui")]
    if args.ready:
        view = [r for r in view if r["ready"] and not r["covered"]]
    if args.top:
        view = view[:args.top]

    if args.json or args.ui or args.batch or args.ready or args.top:
        if args.json:
            print(json.dumps(view, indent=1))
        else:
            for r in view:
                flag = "OK " if r["covered"] else "TODO"
                print(f"{flag} {r['api'][:44]:46} {r['entry']:8} "
                      f"money={len(r['money_tables'])} :: {r['action'][:60]}")
        return 0

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8") as fh:
        fh.write("# Loan flow coverage worklist — generated from the platform maps + registry.\n")
        for r in rows:
            fh.write(json.dumps(r) + "\n")
    DOC.write_text(markdown(rows), encoding="utf-8")

    todo = [r for r in rows if not r["covered"]]
    print(f"loan flow worklist: {len(rows)} flow(s) reaching a loan account")
    print(f"  {len(rows)-len(todo):4} proven covered")
    print(f"  {len(todo):4} to do — {sum(1 for r in todo if r['ready'])} drivable today, "
          f"{sum(1 for r in todo if not r['ready'])} blocked")
    print(f"  {sum(1 for r in rows if r['eod_depth'] is not None):4} in the EOD/BOD chain")
    print(f"  {sum(1 for r in rows if r['money_tables']):4} write a money table")
    print(f"  → {OUT.relative_to(ROOT)}\n  → {DOC.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
