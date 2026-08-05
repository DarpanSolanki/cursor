#!/usr/bin/env python3
"""Fail on references to repo directories that no longer exist, in positions that execute.

The repos were renamed `novopay-* -> trustt-*` on 2026-07-15. Roughly 28k mentions of the old
names survive, and almost all are legitimate history — changelog entries, KG snapshots, past-tense
narrative. Rewriting those would falsify the record.

What matters is the small set that a shell or an agent will actually run: `git -C <dead>`,
`cd <dead>`, a path assignment, or a `$ROOT/<dead>` interpolation. Those fail silently — `git -C`
on a missing directory prints nothing and returns non-zero, which reads as "the fix is absent"
rather than "you looked in the wrong place". That is what this gate catches.

    python3 scripts/lib/dead_repo_ref_gate.py check [--json]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

SCAN_DIRS = ("scripts", ".cursor/rules", ".cursor/skills", ".cursor/hooks", "cursor-bundle/memory")
SKIP_PARTS = {".git", "__pycache__", "node_modules", "scratch", "snapshot"}
SKIP_SUFFIX = {".jsonl", ".log", ".db", ".png", ".jpg", ".pdf"}

REPO_NAME = r"novopay-platform-[a-z0-9][a-z0-9-]*"
RUNNABLE = (
    re.compile(rf"git\s+-C\s+\"?\$?[\w{{}}/.-]*?({REPO_NAME})"),
    re.compile(rf"\bcd\s+\"?\$?[\w{{}}/.-]*?({REPO_NAME})"),
    re.compile(rf"\$\{{?ROOT\}}?/({REPO_NAME})"),
    re.compile(rf"^\s*\w+=\"?[^\"]*?/({REPO_NAME})", re.M),
)


def live_repos() -> set[str]:
    return {d.name for d in ROOT.iterdir() if d.is_dir() and (d / ".git").is_dir()}


def _files() -> list[Path]:
    out: list[Path] = []
    for rel in SCAN_DIRS:
        base = ROOT / rel
        if not base.is_dir():
            continue
        for p in base.rglob("*"):
            if not p.is_file() or p.suffix in SKIP_SUFFIX:
                continue
            if SKIP_PARTS & set(p.relative_to(ROOT).parts):
                continue
            out.append(p)
    return out


FALLBACK_WINDOW = 3


def _has_live_counterpart(lines: list[str], idx: int, dead: str) -> bool:
    """A dead name paired with its live counterpart nearby is a compat fallback, not a break.

    `for cand in "$ROOT/trustt-x" "$ROOT/novopay-x"` and the `if [[ ! -d ]]` retry both try the
    live path first. Flagging those would leave the gate permanently red on correct code, which is
    how a gate gets ignored.
    """
    live_name = dead.replace("novopay-platform-", "trustt-platform-")
    candidates = {live_name}
    if live_name.endswith("-v2"):
        candidates.add(live_name[: -len("-v2")])
    lo = max(0, idx - FALLBACK_WINDOW)
    hi = min(len(lines), idx + FALLBACK_WINDOW + 1)
    window = "\n".join(lines[lo:hi])
    return any(c in window for c in candidates)


def scan() -> list[dict]:
    live = live_repos()
    findings: list[dict] = []
    for p in _files():
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if "novopay-platform-" not in text:
            continue
        lines = text.splitlines()
        for lineno, line in enumerate(lines, 1):
            if "novopay-platform-" not in line:
                continue
            for pat in RUNNABLE:
                for m in pat.finditer(line):
                    name = m.group(1)
                    if name in live:
                        continue
                    if (ROOT / name).is_dir():
                        continue
                    if _has_live_counterpart(lines, lineno - 1, name):
                        continue
                    findings.append({
                        "file": str(p.relative_to(ROOT)),
                        "line": lineno,
                        "repo": name,
                        "suggest": name.replace("novopay-platform-", "trustt-platform-").replace(
                            "trustt-platform-accounting-v2", "trustt-platform-accounting"
                        ),
                        "text": line.strip()[:140],
                    })
                    break
    seen, uniq = set(), []
    for f in findings:
        k = (f["file"], f["line"], f["repo"])
        if k not in seen:
            seen.add(k)
            uniq.append(f)
    return uniq


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", nargs="?", default="check", choices=["check"])
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    findings = scan()
    if args.json:
        print(json.dumps({"findings": findings, "count": len(findings)}, indent=2))
        return 1 if findings else 0
    if not findings:
        print("dead-repo-ref gate: OK — no runnable reference to a missing repo directory")
        return 0
    print(f"dead-repo-ref gate: FAIL — {len(findings)} runnable reference(s) to missing repo dirs")
    for f in findings:
        print(f"  {f['file']}:{f['line']}  {f['repo']} -> {f['suggest']}")
        print(f"      {f['text']}")
    print("\nHistory and prose are not scanned — only positions a shell or agent will execute.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
