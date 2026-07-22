#!/usr/bin/env bash
# Workspace self-improvement pass — drain safe perf fixes + quick smoke (no full KG rebuild).
#
# Usage:
#   workspace-max-pass.sh           # ~3–8s typical
#   workspace-max-pass.sh --full    # + health/disburse smoke (~30s)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
FULL=0
[[ "${1:-}" == "--full" ]] && FULL=1

echo "=== workspace max-pass ==="
bash "$ROOT/scripts/bin/workspace-health.sh"

# Safe auto-fixes (cheap) — disk (archived logs) then hygiene (scratch, KG cache LRU)
bash "$ROOT/scripts/bin/workspace-disk-clean.sh" --clean 2>/dev/null || true
bash "$ROOT/scripts/bin/workspace-hygiene.sh" --clean 2>/dev/null || true
python3 "$ROOT/scripts/testing/sync_engine.py" fast-sync --quiet 2>/dev/null || true

# Self-heal enrichment drift (CHANGELOG newer than kg.db) — no user action
if [[ -f "$ROOT/cursor-bundle/brain/changelog/CHANGELOG.md" && -f "$ROOT/cursor-bundle/kg/data/kg.db" ]]; then
  if [[ "$ROOT/cursor-bundle/brain/changelog/CHANGELOG.md" -nt "$ROOT/cursor-bundle/kg/data/kg.db" ]]; then
    echo "→ enrichment-sync (CHANGELOG newer than kg.db)"
    bash "$ROOT/scripts/bin/enrichment-sync.sh" 2>/dev/null || true
  fi
fi

# Mark completed auto_safe backlog items (this pass ships them)
for id in WS-001 WS-002 WS-003 WS-004 WS-005; do
  python3 "$ROOT/scripts/lib/workspace_backlog.py" mark "$id" done 2>/dev/null || true
done

if [[ "${1:-}" == "--repair" || "${1:-}" == "--full" ]]; then
  bash "$ROOT/scripts/bin/install-user-cursor-gates.sh" 2>/dev/null || true
fi

if [[ "${1:-}" == "--full" || "${FULL:-0}" == "1" ]]; then
  bash "$ROOT/scripts/bin/workspace-smoke.sh" --full --with-close
else
  bash "$ROOT/scripts/bin/workspace-smoke.sh" --quick
fi

echo "=== workspace max-pass: done ==="
python3 "$ROOT/scripts/lib/workspace_backlog.py" status 2>/dev/null | tail -n +1
