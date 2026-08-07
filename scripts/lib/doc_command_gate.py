#!/usr/bin/env python3
"""Every script path a rule, skill or doc tells an agent to run must exist.

An instruction that names a file which is not there costs a full detour: the agent runs it,
gets `No such file or directory`, and starts guessing. `.cursorrules` and the rules are loaded
into *every* session, so a stale path there is paid over and over.

Real case: the rules say `ntest run <case>` and several docs wrote `scripts/bin/ntest`,
but the file is `scripts/bin/ntest.sh`.

  doc_command_gate.py            report, exit 1 on any dead reference
  doc_command_gate.py --json
  doc_command_gate.py --fix      rewrite refs whose only problem is a missing .sh/.py suffix

Scans .cursor/**.md, .cursorrules, AGENTS.md, docs/**.md, cursor-bundle/**/*.md.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]

DOC_GLOBS = [
    ".cursorrules", "AGENTS.md",
    ".cursor/**/*.md",
    "cursor-bundle/**/*.md",
    "docs/**/*.md",
    "system_brain/**/*.md",
]

# A changelog entry describes what was true when it was written; a scratch path in it is
# history, not a broken instruction. Same for dated brain worklogs. These are reported
# but never fail the gate — only surfaces an agent is told to *act on* block.
HISTORICAL = (
    ".cursor/changelog.md",
    "cursor-bundle/brain/workspace/",
    "cursor-bundle/brain/CHANGELOG",
    "system_brain/rules/rule_inventory.md",
)


def is_historical(doc: str) -> bool:
    return any(doc.startswith(h) or doc == h for h in HISTORICAL)

# scripts/<something> with an extension, or a bare scripts/bin/<name>
_REF = re.compile(r"(?<![\w/.-])(scripts/[A-Za-z0-9_./-]+?)(?=[\s`'\"),;:]|$)")

_SKIP_SUFFIXES = (".md", ".json", ".jsonl", ".sql", ".log", ".txt", ".csv", ".yml", ".yaml")


def iter_docs():
    seen = set()
    for pattern in DOC_GLOBS:
        for path in ROOT.glob(pattern):
            if path.is_file() and path not in seen:
                seen.add(path)
                yield path


def candidate_fix(ref: str) -> str | None:
    if "." in pathlib.Path(ref).name:
        return None
    for suffix in (".sh", ".py"):
        if (ROOT / (ref + suffix)).exists():
            return ref + suffix
    return None


def scan() -> list[dict]:
    bad = []
    for doc in iter_docs():
        try:
            text = doc.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for num, line in enumerate(text.splitlines(), 1):
            for ref in _REF.findall(line):
                ref = ref.rstrip(".,")
                if ref.endswith("/") or "*" in ref or "<" in ref:
                    continue
                target = ROOT / ref
                if target.exists():
                    continue
                # a directory reference written without the trailing slash
                if target.is_dir():
                    continue
                if any(ref.endswith(s) for s in _SKIP_SUFFIXES):
                    # data/doc paths are allowed to be generated at runtime
                    if not (ROOT / ref).parent.exists():
                        continue
                bad.append({
                    "doc": str(doc.relative_to(ROOT)),
                    "line": num,
                    "ref": ref,
                    "fix": candidate_fix(ref),
                })
    return bad


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--fix", action="store_true")
    args = ap.parse_args()

    bad = scan()

    if args.fix:
        fixable = [b for b in bad if b["fix"]]
        by_doc: dict[str, list[dict]] = {}
        for b in fixable:
            by_doc.setdefault(b["doc"], []).append(b)
        for doc, items in by_doc.items():
            path = ROOT / doc
            text = path.read_text(encoding="utf-8")
            for b in items:
                text = re.sub(rf"(?<![\w/.-]){re.escape(b['ref'])}(?![\w.-])", b["fix"], text)
            path.write_text(text, encoding="utf-8")
        print(f"fixed {len(fixable)} reference(s) in {len(by_doc)} file(s)")
        bad = scan()

    if args.json:
        print(json.dumps(bad, indent=1))
        return 1 if bad else 0

    live = [b for b in bad if not is_historical(b["doc"])]
    hist = [b for b in bad if is_historical(b["doc"])]

    if not live:
        print(f"doc command gate: OK — every actionable script path exists"
              + (f" ({len(hist)} historical ref(s) ignored)" if hist else ""))
        return 0

    print(f"doc command gate: {len(live)} dead script reference(s) on instruction surfaces")
    for b in live:
        hint = f"   -> {b['fix']}" if b["fix"] else ""
        print(f"  {b['doc']}:{b['line']}  {b['ref']}{hint}")
    if hist:
        print(f"\n  ({len(hist)} more in changelog/worklogs — history, not instructions)")
    if any(b["fix"] for b in live):
        print("\n  Suffix-only misses are auto-fixable: doc_command_gate.py --fix")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
