#!/usr/bin/env bash
# sessionStart — surface standing user corrections from cursor-bundle/memory.
# Consultation order puts Memory at #1, but nothing loaded it: the KG/intel/autopilot
# hooks all skipped it, so RULE 1/2/3 (no comments, no over-engineering, reuse queries)
# never reached context and were repeatedly broken. This is that missing layer.
set -euo pipefail
ROOT="${CURSOR_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
MEM="$ROOT/cursor-bundle/memory"
[[ -d "$MEM" ]] || exit 0

python3 - "$MEM" <<'PY'
import re, sys
from pathlib import Path

mem = Path(sys.argv[1])
rules = mem / "feedback_keep_code_simple.md"
print("## Standing code rules (cursor-bundle/memory — obey before writing any code)")
if rules.is_file():
    for line in rules.read_text(encoding="utf-8").splitlines():
        m = re.match(r"\*\*(RULE \d+[^*]*)\*\*(.*)", line.strip())
        if m:
            head = m.group(1).strip(" —-")
            rest = re.sub(r"\s+", " ", m.group(2)).strip(" —-")
            first = rest.split(". ")[0][:150] if rest else ""
            print(f"- **{head}** — {first}" if first else f"- **{head}**")
    print(f"  Source: cursor-bundle/memory/feedback_keep_code_simple.md")

index = mem / "MEMORY.md"
if index.is_file():
    n = sum(1 for l in index.read_text(encoding="utf-8").splitlines() if l.startswith("- ["))
    print(f"- {n} indexed memories in cursor-bundle/memory/MEMORY.md — read it before proposing a fix.")
print("- Gates: java-comment-lint (--diff) blocks comment volume on push; "
      "edits made in a git worktree OUTSIDE the workspace root bypass every path-based gate.")
PY
