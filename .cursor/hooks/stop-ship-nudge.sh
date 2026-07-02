#!/usr/bin/env bash
# stop — nudge only when this session touched ship paths; never auto-run money-tier close.
set -euo pipefail
ROOT="${CURSOR_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
PENDING="$ROOT/.cursor/.pending-ship-work.json"
FLAG="$ROOT/.cursor/.pending-ship-nudge"
GATE="$ROOT/scripts/lib/ship_push_gate.py"
SESSION="$ROOT/scripts/lib/session_ship.py"

if [[ ! -f "$PENDING" && ! -f "$FLAG" ]]; then
  echo '{}'
  exit 0
fi

rm -f "$FLAG"

if [[ -f "$PENDING" ]] && python3 "$GATE" --satisfied 2>/dev/null; then
  python3 "$SESSION" --clear 2>/dev/null || true
  echo '{}'
  exit 0
fi

CLOSE_MODE="$(python3 "$SESSION" --mode 2>/dev/null || echo none)"
CLOSE_REASON="$(python3 "$SESSION" --reason 2>/dev/null || echo unknown)"

# Stale pending from another session or analysis-only tab — stay silent (no blocking nudge).
if [[ "$CLOSE_MODE" == "none" ]]; then
  echo '{}'
  exit 0
fi

# Optional lightweight close on stop — workspace tier only; money/service needs explicit end or mark-verified.
if [[ "${WORKSPACE_AUTOPILOT_NO_AUTO_CLOSE:-0}" != "1" && "$CLOSE_MODE" == "workspace" ]]; then
  LOG="$ROOT/scripts/scratch/logs/autopilot-stop-close.log"
  mkdir -p "$(dirname "$LOG")"
  if timeout 90 bash "$ROOT/scripts/bin/workspace-autopilot.sh" end --quiet >>"$LOG" 2>&1; then
    if python3 "$GATE" --satisfied 2>/dev/null; then
      echo '{}'
      exit 0
    fi
  fi
fi

python3 - <<'PY' "$ROOT" "$PENDING" "$CLOSE_MODE" "$CLOSE_REASON"
import json, sys
from pathlib import Path

root, pending_p, mode, reason = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3], sys.argv[4]
apis, files, tier = [], [], "workspace"
if pending_p.is_file():
    try:
        d = json.loads(pending_p.read_text(encoding="utf-8"))
        apis = d.get("apis") or []
        files = d.get("files") or []
        tier = d.get("tier") or "workspace"
    except Exception:
        pass

api_hint = ", ".join(apis) if apis else "(build/validate per tier)"
msg = (
    f"Ship work pending (tier={tier}, mode={mode}) — close when you ship, not on every stop.\n"
    f"  Agent: `bash scripts/bin/workspace-autopilot.sh end` or `--force-close` after tests PASS\n"
    f"  ({reason})\n"
    f"  apis: {api_hint}\n"
    "Files: " + (", ".join(files[:5]) + ("…" if len(files) > 5 else "") if files else "(see pending-ship-work.json)")
)
print(json.dumps({"followup_message": msg}))
PY
exit 0
