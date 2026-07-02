#!/usr/bin/env bash
# Full local DPI regression — APIs + grace E2E + restore for repeatable API state.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
export LOAN_ACCOUNT_ID="${LOAN_ACCOUNT_ID:-8060160}"
export JOB_TIME="${JOB_TIME:-1781699400000}"
export COMPILE="${COMPILE:-0}"

echo "=== DPI full regression (loan=$LOAN_ACCOUNT_ID) ==="
bash "$ROOT/scripts/dpic/run_restructuring_api_smoke.sh"
echo ""
bash "$ROOT/scripts/bin/ntest.sh" run dpic.foreclosure_sim
echo ""
export GRACE_JOB_TIME="${GRACE_JOB_TIME:-1779712200000}"
JOB_TIME="$GRACE_JOB_TIME" bash "$ROOT/scripts/dpic/run_grace_dpi_e2e.sh"
echo ""
bash "$ROOT/scripts/dpic/restore_dpi_api_state.sh"
echo ""
bash "$ROOT/scripts/bin/ntest.sh" run dpic.eod_dpi
echo ""
echo "=== DPI full regression PASS ==="
