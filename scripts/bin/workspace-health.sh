#!/usr/bin/env bash
# Fast workspace health (~1–3s) — no ntest, no workspace-close, no full KG rebuild.
# Usage: workspace-health.sh [--json]
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
JSON=0
[[ "${1:-}" == "--json" ]] && JSON=1

kg_ok=0
fresh_ok=0
pending=0
backlog_open=0

bash "$ROOT/scripts/bin/kg-quick-check.sh" >/dev/null 2>&1 && kg_ok=1 || true
bash "$ROOT/scripts/bin/kg-ensure-fresh.sh" --quiet 2>/dev/null && fresh_ok=1 || true
[[ -f "$ROOT/.cursor/.pending-ship-work.json" ]] && pending=1
backlog_open=$(python3 "$ROOT/scripts/lib/workspace_backlog.py" open-ids 2>/dev/null | wc -l)

if [[ "$JSON" == 1 ]]; then
  python3 - <<PY
import json
print(json.dumps({
  "kg_quick": $kg_ok,
  "kg_fresh": $fresh_ok,
  "pending_ship": $pending,
  "backlog_open": $backlog_open,
}))
PY
  exit 0
fi

echo "=== workspace health (fast) ==="
[[ "$kg_ok" == 1 ]] && echo "  ✓ kg quick-check" || echo "  ⚠ kg needs sync"
[[ "$fresh_ok" == 1 ]] && echo "  ✓ kg fresh" || echo "  ⚠ kg stale"
[[ "$pending" == 0 ]] && echo "  ✓ no pending ship work" || echo "  ⚠ pending ship work"
echo "  · backlog open: $backlog_open (scripts/workspace-backlog.json)"
echo "=== run: bash scripts/bin/workspace-max-pass.sh to drain safe items + smoke ==="
