#!/usr/bin/env bash
# Fail if a NEW scripts/bin/*.sh has zero references (pre-U5 orphans grandfathered).
# Run from ship-loop workspace tier.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
INDEX="$ROOT/scripts/bin/OPS-INDEX.md"
[[ -f "$INDEX" ]] || bash "$ROOT/scripts/bin/build-ops-index.sh"

python3 - <<'PY'
from pathlib import Path
import sys
root = Path(".")
bin_dir = root / "scripts/bin"
gf_path = bin_dir / ".ops-bin-grandfather"
grandfather = set()
if gf_path.is_file():
    for ln in gf_path.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if ln and not ln.startswith("#"):
            grandfather.add(ln)

blobs = []
for pat in (
    "scripts/bin/*.sh", "scripts/lib/*", "scripts/testing/**/*.py",
    ".cursor/hooks/*.sh", ".cursor/rules/*.mdc", ".cursor/skills/**/SKILL.md",
    "AGENTS.md", "sync_branches_v2.sh", "scripts/env/*",
):
    for p in root.glob(pat):
        if p.is_file() and p.suffix in {".sh", ".py", ".md", ".mdc", ".json", ".txt"}:
            try:
                blobs.append((p, p.read_text(encoding="utf-8", errors="ignore")))
            except Exception:
                pass

new_orphans = []
legacy = []
for sh in sorted(bin_dir.glob("*.sh")):
    name = sh.name
    hits = 0
    for p, text in blobs:
        if p.resolve() == sh.resolve():
            continue
        if name in text:
            hits += 1
    if hits == 0:
        if name in grandfather:
            legacy.append(name)
        else:
            new_orphans.append(name)

if legacy:
    print(f"OPS bin hygiene: {len(legacy)} grandfathered zero-ref (ok)")
if new_orphans:
    print("OPS bin hygiene FAIL — NEW scripts with zero references:")
    for o in new_orphans:
        print(f"  - scripts/bin/{o}")
    print("Fix: wire into a caller, or delete. Do not extend .ops-bin-grandfather casually.")
    sys.exit(1)
print(f"OPS bin hygiene OK ({sum(1 for _ in bin_dir.glob('*.sh'))} scripts)")
PY
