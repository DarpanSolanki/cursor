#!/usr/bin/env bash
# DPI integration smoke — loan transactions that read/consume DPI (not batch-only).
# Requires accounting :8002; foreclosure sim also needs actor :8003.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
NTEST="$ROOT/scripts/bin/ntest.sh"
export LOAN_ACCOUNT_ID="${LOAN_ACCOUNT_ID:-8060160}"
export JOB_TIME="${JOB_TIME:-1781699400000}"
export COMPILE="${COMPILE:-0}"

fail() { echo "FAIL: $*" >&2; exit 1; }

echo "=== DPI integration smoke (loan=$LOAN_ACCOUNT_ID) ==="
bash "$ROOT/scripts/bin/novopay-service.sh" ensure accounting ${COMPILE:+--compile}

run_case() {
  local id="$1"
  echo ">>> $id"
  "$NTEST" run "$id" || fail "$id"
}

# Restore EOD state on demo LAN before API reads
bash "$ROOT/scripts/dpic/run_eod_dpi_only.sh" 2>&1 | grep -E 'COMPLETED|FAIL|Error' || true

run_case dpic.overview_api
run_case dpic.restructuring_bpi_api
run_case dpic.summary_api

if curl -s -m 3 -o /dev/null -w '%{http_code}' http://localhost:8003/actuator/health 2>/dev/null | grep -q 200; then
  run_case dpic.foreclosure_sim
  run_case foreclosure.dpi_waiver_smoke
else
  echo "SKIP: actor :8003 down — dpic.foreclosure_sim + foreclosure.dpi_waiver_smoke"
fi

run_case dpic.cross_eod_replay_134497

echo ""
echo "=== DPI integration smoke PASS ==="
