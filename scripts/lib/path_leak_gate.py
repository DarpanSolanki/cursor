#!/usr/bin/env python3
"""Fail when operational scripts still route to Claude/stale roots.

Capacity killer: hardcoded sibling clone, wrong bundle name, legacy home roots,
or absolute workspace paths in runners that already have ROOT.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

SCAN_GLOBS = (
    "scripts/**/*.py",
    "scripts/**/*.sh",
    ".cursor/hooks/**/*.sh",
    "cursor-bundle/kg/**/*.py",
    "cursor-bundle/kg/**/*.sh",
    "cursor-bundle/brain/**/tools/**/*.sh",
    "cursor-bundle/brain/**/tools/**/*.py",
)

ALLOW_PREFIXES = (
    "scripts/cursor-user-gates/",
    "scripts/scratch/",
)

SELF = Path(__file__).resolve()

# Pattern strings are split so this file does not match itself.
_SIBLING = "sliProd" + "Claude"
_WRONG_BUNDLE = "claude" + "-bundle"
_LEGACY = "/home/darpan/" + "darpan"
_WS_ABS = "/home/darpan/Documents/" + "sliProd/"

BANNED = [
    ("sibling_clone", re.compile(re.escape(_SIBLING))),
    ("wrong_bundle", re.compile(re.escape(_WRONG_BUNDLE))),
    ("legacy_home", re.compile(re.escape(_LEGACY) + r"(?!/Documents)")),
    ("hardcoded_ws_abs", re.compile(r'["\']' + re.escape(_WS_ABS))),
    ("dot_claude_live", re.compile(r'["\']\.claude/|/home/[^"\']*/\.claude/')),
]


def _iter_files():
    seen: set[Path] = set()
    for pattern in SCAN_GLOBS:
        for path in ROOT.glob(pattern):
            if not path.is_file() or path.resolve() == SELF:
                continue
            rel = path.relative_to(ROOT).as_posix()
            if any(rel.startswith(p) for p in ALLOW_PREFIXES):
                continue
            if "__pycache__" in path.parts:
                continue
            if path in seen:
                continue
            seen.add(path)
            yield path, rel


def check() -> list[str]:
    bad: list[str] = []
    for path, rel in _iter_files():
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for name, rx in BANNED:
            for m in rx.finditer(text):
                line = text.count("\n", 0, m.start()) + 1
                snippet = text.splitlines()[line - 1].strip()[:100]
                if "CLAUDE_PROJECT_DIR" in snippet and name == "dot_claude_live":
                    continue
                bad.append(f"{rel}:{line}: {name} — {snippet}")
    return bad


def main() -> int:
    bad = check()
    if bad:
        print(f"path-leak: FAIL — {len(bad)} routing hit(s)")
        for line in bad[:50]:
            print(f"  {line}")
        if len(bad) > 50:
            print(f"  … {len(bad) - 50} more")
        return 1
    print("path-leak: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
