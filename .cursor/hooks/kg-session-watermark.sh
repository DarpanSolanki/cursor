#!/usr/bin/env bash
# INDIRECT (SU-STITCH-005): not listed in hooks.json by filename.
# Wired via: kg-session-start.sh → this script (sessionStart); also enrichment-sync,
# setup-local, smoke-workspace, kg-ensure-fresh callers.
# sessionStart / workspaceOpen — cache-first KG sync for multi-repo branch-sets.
set -euo pipefail
ROOT="${CURSOR_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
cd "$ROOT"
PENDING=".cursor/.pending-kg-rebuild"
mkdir -p .cursor scripts/scratch/logs

MODE="--fast"
# sessionStart: state-only by default (≤3s). Set KG_SESSION_SYNC_ON_START=1 for full sync.
# Money paths still call kg-ensure-fresh / kg-session-sync explicitly.

if [[ "${KG_SESSION_SYNC_ON_START:-0}" == "1" ]]; then
  if [[ -x "$ROOT/scripts/bin/kg-session-sync.sh" ]]; then
    if [[ -x "$ROOT/scripts/bin/with-budget.py" ]]; then
      python3 "$ROOT/scripts/bin/with-budget.py" --budget 12 --label kg-session-sync -- \
        bash "$ROOT/scripts/bin/kg-session-sync.sh" $MODE --quiet \
        >>"$ROOT/scripts/scratch/logs/kg-session-sync.log" 2>&1 || true
    else
      bash "$ROOT/scripts/bin/kg-session-sync.sh" $MODE --quiet \
        >>"$ROOT/scripts/scratch/logs/kg-session-sync.log" 2>&1 || true
    fi
  fi
fi

bash "$ROOT/.cursor/hooks/kg-write-state.sh"

# Impact banner deferred — was dominating sessionStart wall (~impact_tests import+KG).
# Agents run: bash scripts/bin/impact-tests.sh --banner when needed.
export IMPACT_BANNER=""

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
impact = (os.environ.get("IMPACT_BANNER") or "").strip()
if impact:
    # Cap so sessionStart stays usable
    if len(impact) > 3500:
        impact = impact[:3500] + "\n… (truncated; run: bash scripts/bin/impact-tests.sh)"
    extra += "\n\n" + impact
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
