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

# Safe auto-fixes (cheap)
bash "$ROOT/scripts/bin/workspace-hygiene.sh" --clean 2>/dev/null || true
python3 "$ROOT/scripts/testing/sync_engine.py" fast-sync --quiet 2>/dev/null || true

# Mark completed auto_safe backlog items (this pass ships them)
for id in WS-001 WS-002 WS-003 WS-004 WS-005; do
  python3 "$ROOT/scripts/lib/workspace_backlog.py" mark "$id" done 2>/dev/null || true
done

if [[ "$FULL" == 1 ]]; then
  bash "$ROOT/scripts/bin/workspace-smoke.sh" --full --with-close
else
  bash "$ROOT/scripts/bin/workspace-smoke.sh" --quick
fi

echo "=== workspace max-pass: done ==="
python3 "$ROOT/scripts/lib/workspace_backlog.py" status 2>/dev/null | tail -n +1
