#!/usr/bin/env bash
# Full local DPI regression — APIs + grace E2E + restore for repeatable API state.
# DEPRECATED — use DPI_REGRESSION_PROFILE=standard scripts/dpic/run_dpi_full_regression.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT/scripts/dpic/lib/dpi_fixture_constants.sh"
export LOAN_ACCOUNT_ID="${LOAN_ACCOUNT_ID:-$DPI_FIXTURE_LOAN_ID}"
export JOB_TIME="${JOB_TIME:-$DPI_GRACE_OVERLAP_JOB_TIME}"
export COMPILE="${COMPILE:-0}"

echo "=== DPI full regression (loan=$LOAN_ACCOUNT_ID) ==="
echo "WARN: run_dpi_regression.sh is deprecated — prefer run_dpi_full_regression.sh"
bash "$ROOT/scripts/dpic/run_restructuring_api_smoke.sh"
echo ""
bash "$ROOT/scripts/bin/ntest.sh" run dpic.foreclosure_sim
echo ""
export GRACE_JOB_TIME="${GRACE_JOB_TIME:-$DPI_GRACE_JOB_TIME}"
JOB_TIME="$GRACE_JOB_TIME" bash "$ROOT/scripts/dpic/run_grace_dpi_e2e.sh"
echo ""
bash "$ROOT/scripts/dpic/restore_dpi_api_state.sh"
echo ""
bash "$ROOT/scripts/bin/ntest.sh" run dpic.eod_dpi
echo ""
echo "=== DPI full regression PASS ==="
