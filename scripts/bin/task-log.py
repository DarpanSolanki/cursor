#!/usr/bin/env python3
"""Record what the investigation actually did — including what was wrong.

Everything here measures the harness: gates wired, coverage, KG freshness. Nothing
measures the *work*. On TDPQA-72 three hypotheses were disproven before the right one,
and that knowledge died with the session: the next agent on the next ticket starts from
the same three.

A disproven hypothesis is expensive evidence. It should be cheaper the second time.

    task-log.py hypothesis --api loanPrepayment --text "sweep excludes victim by id" \\
                --verdict disproven --evidence "UpdateChildLoanAccountStatusProcessor:63"
    task-log.py hypothesis --api loanPrepayment --text "FINAL stamps hardcoded ACTIVE" \\
                --verdict confirmed --evidence "loans_orc.xml:2087"
    task-log.py rule-skipped --rule 30-kg-discipline --why "grepped before kg_error"
    task-log.py close --api loanPrepayment --minutes 240 --ticket TDPQA-72
    task-log.py report [--api X] [--since 2026-07-01]

Written to `cursor-bundle/flow-test/task_telemetry.jsonl`. `kg why <api>` surfaces the
disproven hypotheses automatically, so the cost is paid once.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parents[2]
LOG = ROOT / "cursor-bundle" / "flow-test" / "task_telemetry.jsonl"

VERDICTS = ("confirmed", "disproven", "inconclusive")


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _branch() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"],
                              cwd=str(ROOT / "trustt-platform-accounting"),
                              capture_output=True, text=True, timeout=15).stdout.strip()
    except Exception:
        return ""


def append(record: dict) -> None:
    record.setdefault("ts", _now())
    record.setdefault("branch", _branch())
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, separators=(",", ":")) + "\n")


def rows(since: str = "") -> list[dict]:
    if not LOG.is_file():
        return []
    out = []
    for line in LOG.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if since and str(rec.get("ts", "")) < since:
            continue
        out.append(rec)
    return out


def dead_ends_for(api: str, limit: int = 4) -> list[dict]:
    """Hypotheses already disproven for this API — the expensive part, reusable."""
    api_l = (api or "").lower()
    got = [r for r in rows()
           if r.get("type") == "hypothesis"
           and r.get("verdict") == "disproven"
           and (r.get("api") or "").lower() == api_l]
    return got[-limit:]


def cmd_hypothesis(a) -> int:
    if a.verdict not in VERDICTS:
        print(f"verdict must be one of {VERDICTS}", file=sys.stderr)
        return 2
    append({"type": "hypothesis", "api": a.api, "text": a.text,
            "verdict": a.verdict, "evidence": a.evidence or "", "ticket": a.ticket or ""})
    print(f"logged {a.verdict}: {a.text[:80]}")
    return 0


def cmd_rule_skipped(a) -> int:
    append({"type": "rule_skipped", "rule": a.rule, "why": a.why or "", "ticket": a.ticket or ""})
    print(f"logged rule skipped: {a.rule}")
    return 0


def cmd_close(a) -> int:
    append({"type": "task_closed", "api": a.api or "", "ticket": a.ticket or "",
            "minutes": a.minutes, "outcome": a.outcome or ""})
    print(f"logged close: {a.ticket or a.api} ({a.minutes} min)")
    return 0


def cmd_report(a) -> int:
    data = rows(a.since or "")
    if a.api:
        data = [r for r in data if (r.get("api") or "").lower() == a.api.lower()]
    if not data:
        print("no telemetry yet — task-log.py hypothesis/close as you work")
        return 0

    hyps = [r for r in data if r.get("type") == "hypothesis"]
    closed = [r for r in data if r.get("type") == "task_closed"]
    skipped = [r for r in data if r.get("type") == "rule_skipped"]

    print(f"task telemetry — {len(data)} record(s)"
          + (f" for {a.api}" if a.api else "") + (f" since {a.since}" if a.since else ""))

    if hyps:
        verdicts = Counter(r.get("verdict") for r in hyps)
        wrong = verdicts.get("disproven", 0)
        total = sum(verdicts.values())
        print(f"\n  hypotheses: {total}  "
              + " ".join(f"{k}={v}" for k, v in verdicts.most_common()))
        if total:
            print(f"  first-hypothesis accuracy: {100*(total-wrong)//total}%")
        for r in hyps[-6:]:
            mark = {"confirmed": "✓", "disproven": "✗", "inconclusive": "?"}.get(r.get("verdict"), "-")
            print(f"    {mark} [{r.get('api','?')}] {str(r.get('text'))[:74]}")

    if closed:
        mins = [int(r.get("minutes") or 0) for r in closed if r.get("minutes")]
        if mins:
            print(f"\n  tasks closed: {len(closed)}  median {sorted(mins)[len(mins)//2]} min"
                  f"  worst {max(mins)} min")

    if skipped:
        print(f"\n  rules skipped: {len(skipped)}")
        for rule, n in Counter(r.get("rule") for r in skipped).most_common(5):
            print(f"    {n}× {rule}")
        print("  a rule skipped repeatedly is a gate that has not been written yet")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    h = sub.add_parser("hypothesis")
    h.add_argument("--api", required=True)
    h.add_argument("--text", required=True)
    h.add_argument("--verdict", required=True, choices=VERDICTS)
    h.add_argument("--evidence")
    h.add_argument("--ticket")
    h.set_defaults(fn=cmd_hypothesis)

    r = sub.add_parser("rule-skipped")
    r.add_argument("--rule", required=True)
    r.add_argument("--why")
    r.add_argument("--ticket")
    r.set_defaults(fn=cmd_rule_skipped)

    c = sub.add_parser("close")
    c.add_argument("--api")
    c.add_argument("--ticket")
    c.add_argument("--minutes", type=int, required=True)
    c.add_argument("--outcome")
    c.set_defaults(fn=cmd_close)

    p = sub.add_parser("report")
    p.add_argument("--api")
    p.add_argument("--since")
    p.set_defaults(fn=cmd_report)

    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
