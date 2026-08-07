#!/usr/bin/env python3
"""Measure what a job actually writes, by running it and diffing the database.

The knowledge graph traces `request -> processor -> table` and stops at the orchestration
boundary, so a Spring Batch job's real writes — which happen in an `ItemWriter` under
`batchnew/**` — are invisible to it. `loanAccountBillingJob` is indexed as writing one table
and writes six. Every coverage claim resting on the static footprint is therefore soft.

This closes it by observation instead of inference: snapshot, run the real job, snapshot again.

Two things this gets right because getting them wrong produced a confident wrong answer:

  A row-count diff sees INSERT only. `account` moved 2154 rows during an accrual run with no
  change in count at all. Detecting that needs `updated_on` — and `interest_accrual_details`
  has no such column, so for those tables an UPDATE is simply not observable and the report
  says so rather than implying the table was untouched.

  A SQL error must never read as an empty result. The first version of this measurement ran
  `order by 2` against a single-column select with stderr redirected to /dev/null, printed
  nothing, and looked like a clean "no updates found". Errors here are fatal and loud.

Running it twice proved something the plan had only predicted. The first run inserted 780
rows across five tables. The second, against the same business date, inserted nothing at all —
the jobs are idempotent — and all four registry cases still reported COMPLETED and passed.
HTTP 200 + SUCCESS + COMPLETED is satisfied by a job that did no work, so those asserts cannot
tell a working EOD from a silently skipped one.

    job_footprint.py --snapshot before
    job_footprint.py --run batch.interest_accrual_calc batch.loan_account_billing
    job_footprint.py --diff                 what moved, against the static map
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
FLOW = ROOT / "cursor-bundle" / "flow-test"
STATE = FLOW / "job_footprint"
DBLOCAL = ROOT / "scripts" / "db-local.sh"
SCHEMA = "mfi_accounting"

_ROW = re.compile(r"^([a-z][a-z0-9_]*)\|(-?\d+)$")


def sql(query: str, timeout: int = 600) -> list[str]:
    """Run read-only SQL. A failure raises — it must never look like an empty result."""
    proc = subprocess.run(["bash", str(DBLOCAL), "--sql", query],
                          cwd=str(ROOT), capture_output=True, text=True, timeout=timeout)
    text = proc.stdout + proc.stderr
    if proc.returncode != 0 or "ERROR:" in text:
        raise SystemExit(f"SQL failed:\n{text.strip()[:800]}")
    return [line.strip() for line in proc.stdout.splitlines()]


def tables() -> list[str]:
    rows = sql(f"select table_name from information_schema.tables "
               f"where table_schema='{SCHEMA}' and table_type='BASE TABLE' order by 1")
    return [r for r in rows if re.fullmatch(r"[a-z][a-z0-9_]*", r) and r != "table_name"]


def with_updated_on() -> set[str]:
    rows = sql(f"select table_name from information_schema.columns "
               f"where table_schema='{SCHEMA}' and column_name='updated_on'")
    return {r for r in rows if re.fullmatch(r"[a-z][a-z0-9_]*", r) and r != "table_name"}


def counts(names: list[str]) -> dict[str, int]:
    union = " union all ".join(
        f"select '{n}' t, count(*) c from {SCHEMA}.{n}" for n in names)
    out: dict[str, int] = {}
    for line in sql(f"select t||'|'||c as r from ({union}) z order by t"):
        m = _ROW.match(line)
        if m:
            out[m.group(1)] = int(m.group(2))
    return out


def touched_since(names: set[str], stamp: str) -> dict[str, int]:
    if not names:
        return {}
    union = " union all ".join(
        f"select '{n}' t, count(*) c from {SCHEMA}.{n} where updated_on > timestamp '{stamp}'"
        for n in sorted(names))
    out: dict[str, int] = {}
    for line in sql(f"select t||'|'||c as r from ({union}) z where c > 0 order by c desc"):
        m = _ROW.match(line)
        if m:
            out[m.group(1)] = int(m.group(2))
    return out


def snapshot(label: str) -> pathlib.Path:
    names = tables()
    started = time.time()
    stamp = next((l for l in sql("select to_char(now(),'YYYY-MM-DD HH24:MI:SS.MS') as r")
                  if re.fullmatch(r"\d{4}-\d{2}-\d{2} [\d:.]+", l)), "")
    data = {
        "label": label,
        "db_now": stamp,
        "counts": counts(names),
        "updatable": sorted(with_updated_on()),
    }
    STATE.mkdir(parents=True, exist_ok=True)
    path = STATE / f"{label}.json"
    path.write_text(json.dumps(data, indent=1), encoding="utf-8")
    print(f"snapshot '{label}': {len(data['counts'])} tables, "
          f"{len(data['updatable'])} with updated_on ({time.time()-started:.1f}s)")
    print(f"  → {path.relative_to(ROOT)}")
    return path


def static_footprint(job: str) -> tuple[list[str], list[str]]:
    path = FLOW / "platform_api_map.jsonl"
    if not path.is_file():
        return [], []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.startswith("#"):
            row = json.loads(line)
            if row["api"] == job and row["repo"] == "trustt-platform-accounting":
                return row["tables_written"], row["tables_read"]
    return [], []


def run_cases(cases: list[str]) -> list[dict]:
    out = []
    for case in cases:
        started = time.time()
        proc = subprocess.run(["bash", str(ROOT / "scripts/bin/ntest.sh"), "run", case],
                              cwd=str(ROOT), capture_output=True, text=True, timeout=1800)
        text = proc.stdout + proc.stderr
        completed = "COMPLETED" in text
        passed = "✓ PASS" in text or "[PASS]" in text
        job = ""
        m = re.search(r">>> (\w+) COMPLETED", text)
        if m:
            job = m.group(1)
        out.append({"case": case, "job": job, "completed": completed, "passed": passed,
                    "seconds": round(time.time() - started, 1)})
        print(f"  {case:38} {'COMPLETED' if completed else 'did not complete':17} "
              f"{'pass' if passed else 'FAIL':5} {out[-1]['seconds']}s", flush=True)
    return out


def diff(before: dict, after: dict, jobs: list[str]) -> dict:
    inserted = {t: after["counts"][t] - before["counts"][t]
                for t in after["counts"]
                if t in before["counts"] and after["counts"][t] != before["counts"][t]}
    updatable = set(before["updatable"])
    updated = touched_since(updatable, before["db_now"]) if before.get("db_now") else {}
    observed = sorted(set(inserted) | set(updated))

    claimed: set[str] = set()
    for job in jobs:
        claimed |= set(static_footprint(job)[0])

    blind = [t for t in observed if t not in updatable and t not in inserted]
    return {
        "jobs": jobs,
        "inserted": dict(sorted(inserted.items(), key=lambda kv: -abs(kv[1]))),
        "updated": updated,
        "observed": observed,
        "claimed_by_static_map": sorted(claimed),
        "observed_not_claimed": sorted(set(observed) - claimed),
        "claimed_not_observed": sorted(claimed - set(observed)),
        "update_blind_tables": sorted(t for t in observed if t not in updatable),
        "note": ("Tables without an updated_on column cannot show an UPDATE here. Absence "
                 "from this report is not proof they were untouched."),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--snapshot", metavar="LABEL")
    ap.add_argument("--run", nargs="+", metavar="CASE")
    ap.add_argument("--diff", action="store_true")
    ap.add_argument("--jobs", nargs="*", default=[],
                    help="job apiNames to compare the observed footprint against")
    args = ap.parse_args()

    if args.snapshot:
        snapshot(args.snapshot)
        return 0

    if args.run:
        snapshot("before")
        print(f"\nrunning {len(args.run)} case(s) for real:")
        results = run_cases(args.run)
        snapshot("after")
        jobs = args.jobs or [r["job"] for r in results if r["job"]]
        before = json.loads((STATE / "before.json").read_text(encoding="utf-8"))
        after = json.loads((STATE / "after.json").read_text(encoding="utf-8"))
        report = diff(before, after, jobs)
        report["cases"] = results
        (STATE / "report.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
        show(report)
        return 0 if all(r["completed"] for r in results) else 1

    if args.diff:
        try:
            before = json.loads((STATE / "before.json").read_text(encoding="utf-8"))
            after = json.loads((STATE / "after.json").read_text(encoding="utf-8"))
        except OSError:
            print("no snapshots — run --snapshot before / --snapshot after", file=sys.stderr)
            return 2
        show(diff(before, after, args.jobs))
        return 0

    ap.print_help()
    return 0


def show(report: dict) -> None:
    print("\nobserved footprint")
    for table, n in report["inserted"].items():
        print(f"  {table:44} {n:+6d} rows")
    for table, n in report["updated"].items():
        if table not in report["inserted"]:
            print(f"  {table:44} {n:6d} updated")
    if report["jobs"]:
        print(f"\nstatic map claimed: {', '.join(report['claimed_by_static_map']) or '—'}")
        missed = report["observed_not_claimed"]
        print(f"observed but NOT in the map ({len(missed)}): {', '.join(missed) or '—'}")
        stale = report["claimed_not_observed"]
        if stale:
            print(f"claimed but not observed: {', '.join(stale)} "
                  "(may be UPDATE-only on a table without updated_on)")
    blind = report["update_blind_tables"]
    if blind:
        print(f"\nno updated_on, so UPDATEs are invisible here: {', '.join(blind[:8])}")
    print(f"  → {(STATE / 'report.json').relative_to(ROOT)}")


if __name__ == "__main__":
    raise SystemExit(main())
