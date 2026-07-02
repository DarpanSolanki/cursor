#!/usr/bin/env bash
# afterShellExecution — auto ship tests after commit when pending money/service work exists.
set -euo pipefail
ROOT="${CURSOR_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
INPUT=$(cat)
CMD=$(echo "$INPUT" | python3 -c "import json,sys; print(json.load(sys.stdin).get('command',''))" 2>/dev/null || true)

[[ "$CMD" =~ git[[:space:]]+commit ]] || { echo '{}'; exit 0; }

PENDING="$ROOT/.cursor/.pending-ship-work.json"
[[ -f "$PENDING" ]] || { echo '{}'; exit 0; }

TIER=$(python3 -c "import json; print(json.load(open('$PENDING')).get('tier','workspace'))" 2>/dev/null || echo workspace)
[[ "$TIER" == "workspace" ]] && { echo '{}'; exit 0; }

LOG="$ROOT/scripts/scratch/logs/post-commit-ship-test.log"
mkdir -p "$(dirname "$LOG")"
(
  echo "=== $(date -u +%Y-%m-%dT%H:%M:%SZ) post-commit ship-test-auto tier=$TIER ==="
  bash "$ROOT/scripts/bin/ship-test-auto.sh"
) >>"$LOG" 2>&1 &

python3 - <<'PY'
import json
print(json.dumps({"additional_context": "Post-commit: ship-test-auto queued (impact+deep). Log: scripts/scratch/logs/post-commit-ship-test.log"}))
PY
