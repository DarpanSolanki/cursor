#!/usr/bin/env bash
# Regenerate scripts/bin/OPS-INDEX.md from script headers + caller scan.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BIN="$ROOT/scripts/bin"
OUT="$BIN/OPS-INDEX.md"
cd "$ROOT"

python3 - "$BIN" "$OUT" <<'PY'
from __future__ import annotations
import re
from pathlib import Path

bin_dir = Path(__file__)  # wrong — use argv
import sys
bin_dir = Path(sys.argv[1])
out = Path(sys.argv[2])
root = bin_dir.parent.parent

scripts = sorted(bin_dir.glob("*.sh"))
# Also include thin wrappers named without .sh? only .sh

# Build reference counts: who mentions basename
all_text_paths = []
for pat in ("scripts/bin/*.sh", "scripts/lib/*.sh", "scripts/lib/*.py",
            "scripts/testing/*.py", ".cursor/hooks/*.sh", "sync_branches_v2.sh"):
    all_text_paths.extend(root.glob(pat))

contents: dict[Path, str] = {}
for p in all_text_paths:
    try:
        contents[p] = p.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        pass

rows = []
for sh in scripts:
    if sh.name == "OPS-INDEX.md":
        continue
    try:
        lines = sh.read_text(encoding="utf-8", errors="ignore").splitlines()
    except Exception:
        lines = []
    purpose = ""
    for ln in lines[1:12]:
        s = ln.strip()
        if s.startswith("#") and not s.startswith("#!"):
            purpose = s.lstrip("# ").strip()
            if purpose:
                break
    if not purpose:
        purpose = "(no header)"
    # called-by
    callers = []
    needle = sh.name
    for p, text in contents.items():
        if p.resolve() == sh.resolve():
            continue
        if needle in text:
            callers.append(str(p.relative_to(root)))
    callers = sorted(set(callers))[:8]
    called = ", ".join(callers) if callers else "—"
    rows.append((sh.name, purpose[:90], called))

lines = [
    "# OPS-INDEX — scripts/bin (auto-generated)",
    "",
    "Regenerate: `bash scripts/bin/build-ops-index.sh` (also via intel-session-sync hook).",
    "",
    "| Name | Purpose | Called-by |",
    "|------|---------|-----------|",
]
for name, purpose, called in rows:
    purpose = purpose.replace("|", "/")
    called = called.replace("|", "/")
    lines.append(f"| `{name}` | {purpose} | {called} |")
lines.append("")
lines.append(f"_Generated {len(rows)} entries._")
lines.append("")
out.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"Wrote {out} ({len(rows)} scripts)")
PY
