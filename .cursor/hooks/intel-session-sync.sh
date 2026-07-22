#!/usr/bin/env bash
# sessionStart — fast super-agent bootstrap (~2–5s); self-learning always on.
set -euo pipefail
ROOT="${CURSOR_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
cd "$ROOT"
mkdir -p scripts/scratch/logs .cursor

LOG="$ROOT/scripts/scratch/logs/intel-session-sync.log"
KG_STATE="$ROOT/.cursor/workspace-kg-state.md"

# Skip redundant kg-ensure when kg-session-watermark just ran (<90s)
SKIP_KG=0
if [[ -f "$KG_STATE" ]]; then
  age=$(( $(date +%s) - $(stat -c %Y "$KG_STATE" 2>/dev/null || echo 0) ))
  [[ "$age" -lt 90 ]] && SKIP_KG=1
fi

# Rebuild gaps digest when SoT is newer (session bootstrap token tax)
GAPS_SRC="$ROOT/.cursor/gaps-and-risks.md"
GAPS_DIGEST="$ROOT/.cursor/gaps-and-risks-digest.md"
if [[ -f "$GAPS_SRC" ]]; then
  if [[ ! -f "$GAPS_DIGEST" || "$GAPS_SRC" -nt "$GAPS_DIGEST" ]]; then
    bash "$ROOT/scripts/bin/build-gaps-digest.sh" >>"$LOG" 2>&1 || true
  fi
fi

# Rebuild architecture digest when SoT is newer
ARCH_SRC="$ROOT/.cursor/architecture.md"
ARCH_DIGEST="$ROOT/.cursor/architecture-digest.md"
if [[ -f "$ARCH_SRC" ]]; then
  if [[ ! -f "$ARCH_DIGEST" || "$ARCH_SRC" -nt "$ARCH_DIGEST" ]]; then
    bash "$ROOT/scripts/bin/build-architecture-digest.sh" >>"$LOG" 2>&1 || true
  fi
fi

# Regenerate OPS-INDEX when any scripts/bin/*.sh is newer than the index
OPS_INDEX="$ROOT/scripts/bin/OPS-INDEX.md"
if [[ -x "$ROOT/scripts/bin/build-ops-index.sh" ]]; then
  newest_bin="$(find "$ROOT/scripts/bin" -maxdepth 1 -name '*.sh' -printf '%T@\n' 2>/dev/null | sort -n | tail -1 || true)"
  index_mtime="$(stat -c %Y "$OPS_INDEX" 2>/dev/null || echo 0)"
  if [[ -n "$newest_bin" ]]; then
    newest_bin="${newest_bin%%.*}"
    if [[ ! -f "$OPS_INDEX" ]] || [[ "${newest_bin:-0}" -gt "$index_mtime" ]]; then
      bash "$ROOT/scripts/bin/build-ops-index.sh" >>"$LOG" 2>&1 || true
    fi
  fi
fi

export SKIP_KG_ENSURE="$SKIP_KG"
RESULT=$(timeout 50 python3 "$ROOT/scripts/testing/sync_engine.py" fast-session --quiet \
  >>"$LOG" 2>&1 && cat "$LOG" | tail -1 || echo '{"ok":false}')

python3 - <<'PY'
import json, os, pathlib, time
root = pathlib.Path(os.environ.get("CURSOR_PROJECT_DIR", "."))
hub = root / ".cursor/workspace-intelligence-state.md"
intel = root / ".cursor/.intel-cache.json"
lines = []
if hub.is_file():
    lines = hub.read_text(encoding="utf-8").splitlines()[:22]
hub_snip = "\n".join(lines) if lines else "(hub not yet written — run: scripts/bin/super-agent.sh session)"
stale = []
fp = root / ".cursor/.intel-fingerprint.json"
if fp.is_file():
    try:
        import json as j
        data = j.loads(fp.read_text(encoding="utf-8"))
        for layer, rec in (data.get("layers") or {}).items():
            built = rec.get("built_at") or 0
            if built and time.time() - built > 86400:
                stale.append(layer)
    except Exception:
        pass
extra = ""
if stale:
    extra = f"\n\nStale layers (>24h): {', '.join(stale)} — `bash scripts/bin/super-agent.sh sync --full` after branch/orch drift."
ctx = f"""## Intelligence hub (auto-sync on session start)
Read `.cursor/workspace-intelligence-state.md` · skill `.cursor/skills/super-agent/SKILL.md`

{hub_snip}
{extra}

Fast path: `super-agent.sh session` (~3s) · `super-agent.sh sync` (~0.05s when fresh) · learning_bus always hot.
"""
print(json.dumps({"additional_context": ctx}))
PY
