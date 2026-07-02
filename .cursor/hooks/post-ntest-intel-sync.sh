#!/usr/bin/env bash
# afterShellExecution — intel sync + on ntest PASS queue push (ship-and-continue).
set -euo pipefail
ROOT="${CURSOR_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
INPUT=$(cat)
CMD=$(echo "$INPUT" | python3 -c "import json,sys; print(json.load(sys.stdin).get('command',''))" 2>/dev/null || true)
OUT=$(echo "$INPUT" | python3 -c "import json,sys; print(json.load(sys.stdin).get('output','')[:8000])" 2>/dev/null || true)

if [[ ! "$CMD" =~ (ntest|super-agent|capture-flow|test-learn|agent-ops|sync_engine\.py|gradlew|ship-loop-gate|workspace-close|disburse-quick|dpi-sanity) ]]; then
  echo '{}'
  exit 0
fi

mkdir -p "$ROOT/scripts/scratch/logs"
timeout 30 python3 "$ROOT/scripts/testing/sync_engine.py" fast-sync --quiet \
  >>"$ROOT/scripts/scratch/logs/intel-post-ntest.log" 2>&1 || true

EXTRA=""
# ntest / sanity PASS → mark verified + try push (cooldown inside ship-and-continue)
if [[ "$CMD" =~ ntest|disburse-quick|dpi-sanity|verify-dpi|verify-disburse ]]; then
  if echo "$OUT" | grep -qE '(✓ PASS|PASS \(|\[PASS\]|COMPLETED|disburse-quick: PASS|dpi-sanity: PASS)'; then
  API=$(echo "$CMD" | sed -nE 's/.*(ntest\.sh|ntest)( +auto| +run)? +([^ ]+).*/\3/p' | head -1)
  [[ -z "$API" ]] && API=$(echo "$CMD" | grep -oE 'disburseLoan|loanPrepayment|dpi[A-Za-z]+' | head -1)
  LOG="$ROOT/scripts/scratch/logs/autopilot-post-test.log"
  {
    echo "=== $(date -u +%Y-%m-%dT%H:%M:%SZ) PASS detected api=${API:-?} ==="
    bash "$ROOT/scripts/bin/workspace-autopilot.sh" mark-verified --api "${API:-}" --quiet
    sleep "${SHIP_PUSH_COOLDOWN_SEC:-20}"
    bash "$ROOT/scripts/bin/workspace-autopilot.sh" ship-and-continue --quiet
  } >>"$LOG" 2>&1 &
  EXTRA="Test PASS — push queued (cooldown ${SHIP_PUSH_COOLDOWN_SEC:-20}s). Continue next task; autopilot re-runs on new message."
  fi
fi

python3 - <<PY
import json
print(json.dumps({
    "additional_context": "Post-test intel sync (fast-sync). ${EXTRA} Hub: .cursor/workspace-intelligence-state.md"
}))
PY
