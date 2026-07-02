#!/usr/bin/env bash
# sessionStart / workspaceOpen — cache-first KG sync for multi-repo branch-sets.
set -euo pipefail
ROOT="${CURSOR_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
cd "$ROOT"
PENDING=".cursor/.pending-kg-rebuild"
mkdir -p .cursor scripts/scratch/logs

MODE="--fast"
[[ "${1:-}" == "sessionStart" ]] && MODE=""

if [[ -x "$ROOT/scripts/bin/kg-session-sync.sh" ]]; then
  timeout 540 bash "$ROOT/scripts/bin/kg-session-sync.sh" $MODE --quiet \
    >>"$ROOT/scripts/scratch/logs/kg-session-sync.log" 2>&1 || true
fi

bash "$ROOT/.cursor/hooks/kg-write-state.sh"

if [[ "${1:-}" == "workspaceOpen" ]]; then
  exit 0
fi

python3 - <<'PY'
import json, os, pathlib
root = pathlib.Path(os.environ.get("CURSOR_PROJECT_DIR", "."))
state = root / ".cursor/workspace-kg-state.md"
branch = root / ".cursor/.kg-branch-set.json"
fresh = (state.read_text(encoding="utf-8") if state.is_file() else "")[:1200]
pending = (root / ".cursor/.pending-kg-rebuild").is_file()
stale = "Action required (stale knowledge)" in fresh or "KG STALE" in fresh
bs = ""
if branch.is_file():
    try:
        import json as j
        b = j.loads(branch.read_text(encoding="utf-8"))
        repos = b.get("repos", {})
        mix = ", ".join(f"{r.split('-')[-1][:8]}:{v.get('branch','?')[:20]}" for r, v in list(repos.items())[:4])
        bs = f"\nBranch-set key `{b.get('key','?')[:12]}…` ({len(repos)} repos; WIP={b.get('wip_repos',0)}). Mix: {mix}…"
    except Exception:
        pass
extra = ""
if pending:
    extra = "\n\n⚠ Pending KG enrich after commit — changelog-add.sh when fix is stable."
if stale:
    extra += "\n\n🛑 KG STALE — `scripts/bin/kg-ensure-fresh.sh` before money-path analysis."
ctx = f"""## KG session watermark (multi-branch cache)
Read `.cursor/workspace-kg-state.md` · branch-set `.cursor/.kg-branch-set.json`
{bs}

{fresh[:700]}{extra}

Cache: each unique repo branch-mix → LRU snapshot (~1s restore). Self-learning: changelog → kg-session-sync.
"""
print(json.dumps({
    "additional_context": ctx,
    "env": {
        "SLIPROD_WORKSPACE": str(root),
        "SLIPROD_KG_STATE": ".cursor/workspace-kg-state.md",
        "KG_ENSURE_FRESH": "scripts/bin/kg-ensure-fresh.sh",
        "KG_CACHE_MAX": os.environ.get("KG_CACHE_MAX", "48"),
    },
}))
PY
