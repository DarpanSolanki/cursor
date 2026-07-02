#!/usr/bin/env bash
# DPI extended regression — batch baseline + all consumer flows where DPI is read or posted.
#
# Phase order (do not reorder without updating restore points):
#   1 verify-dpi (EOD baseline)
#   2 read APIs + FC sim
#   2b part-prep read
#   2c part-prep TRIAL write (before repayment clears overdue DPI)
#   3 parent repayment / 3b child repayment
#   4 reversal (optional)
#   5 cross-EOD idempotency
#   6 NPA movement (before waiver/ICF clears billed DPI)
#   7a ICF write / 7b DCF waiver smoke
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT/scripts/lib/novopay-service-lib.sh"
# shellcheck disable=SC1091
source "$ROOT/scripts/dpic/lib/dpi_demo_fixture.sh"
# shellcheck disable=SC1091
source "$ROOT/scripts/dpic/lib/dpi_gl_verify.sh"

NTEST="$ROOT/scripts/bin/ntest.sh"
export COMPILE="${COMPILE:-0}"
export LOAN_ACCOUNT_ID="${LOAN_ACCOUNT_ID:-8060160}"
export ACCOUNT_NUMBER="${ACCOUNT_NUMBER:-6004044425}"
export JOB_TIME="${JOB_TIME:-1782563400000}"
SKIP_VERIFY="${SKIP_VERIFY:-0}"
SKIP_REVERSAL="${SKIP_REVERSAL:-0}"
SKIP_WAIVER="${SKIP_WAIVER:-0}"
SKIP_PREFLIGHT="${SKIP_PREFLIGHT:-0}"
RESTORE_BETWEEN_PHASES="${RESTORE_BETWEEN_PHASES:-1}"

_REGRESSION_START=$SECONDS
_CURRENT_PHASE="init"

fail() {
  echo "FAIL: $*" >&2
  dpi_print_fixture_health "$LOAN_ACCOUNT_ID" >&2 || true
  exit 1
}

_on_fail() {
  local code=$?
  if [[ "$code" -ne 0 ]]; then
    echo ">>> regression failed during phase: $_CURRENT_PHASE (${SECONDS - _REGRESSION_START}s elapsed)" >&2
    dpi_print_fixture_health "$LOAN_ACCOUNT_ID" >&2 || true
  fi
}
trap _on_fail EXIT

run_case() {
  echo ">>> $1"
  "$NTEST" run "$1" || fail "$1"
}

phase() {
  _CURRENT_PHASE="$1"
  echo ""
  echo "=== Phase $_CURRENT_PHASE (${SECONDS - _REGRESSION_START}s) ==="
}

maybe_restore() {
  [[ "$RESTORE_BETWEEN_PHASES" == "1" ]] || return 0
  dpi_restore_api_state
}

echo "=== DPI extended regression (loan=$LOAN_ACCOUNT_ID job_time=$JOB_TIME) ==="

if [[ "$SKIP_PREFLIGHT" != "1" ]]; then
  bash "$ROOT/scripts/dpic/run_dpi_regression_preflight.sh" || fail "regression_preflight"
else
  echo "SKIP_PREFLIGHT=1"
fi

dpi_ensure_accounting
dpi_ensure_masterdata
dpi_export_correlators
dpi_ensure_dpi_write_catalogues

actor_up=0
task_up=0
nps_probe_service actor 2>/dev/null && actor_up=1
if curl -s -m 5 -o /dev/null -w '%{http_code}' -X POST "http://127.0.0.1:8019/task/api/v1/getTaskList" \
  -H 'Content-Type: application/json' \
  -d '{"headers":{"tenant_code":"mfi","user_id":"53","stan":"probe","client_code":"NOVOPAY","channel_code":"WEB","function_code":"DEFAULT","function_sub_code":"DEFAULT","run_mode":"REAL"},"request":{}}' \
  2>/dev/null | grep -q 200; then
  task_up=1
fi

phase "1 — verify-dpi (batch baseline)"
if [[ "$SKIP_VERIFY" != "1" ]]; then
  bash "$ROOT/scripts/bin/agent-ops.sh" verify-dpi || fail "verify-dpi"
else
  echo "SKIP_VERIFY=1 (restore API state only)"
  dpi_restore_api_state
fi

phase "2 — read APIs + foreclosure surfaces"
maybe_restore
run_case dpic.overview_api
run_case dpic.restructuring_bpi_api
run_case dpic.summary_api

if [[ "$actor_up" == "1" ]]; then
  run_case dpic.foreclosure_sim
  run_case dpic.foreclosure_details_flow
else
  echo "SKIP (actor down): dpic.foreclosure_sim, dpic.foreclosure_details_api"
fi

phase "2b — part-prepayment BPI / details"
run_case dpic.part_prepayment_bpi_flow
run_case dpic.part_prepayment_details_flow

phase "2c — part-prepayment TRIAL write"
if [[ "$actor_up" == "1" ]]; then
  bash "$ROOT/scripts/dpic/run_dpi_part_prepayment_write_e2e.sh" || fail "dpi_part_prepayment_write_e2e"
else
  echo "SKIP part-prep write (actor down)"
fi

phase "3 — loanRepayment DPI appropriation"
bash "$ROOT/scripts/dpic/run_dpi_repayment_e2e.sh" || fail "dpi_repayment_e2e"

phase "3b — childLoanRepayment"
bash "$ROOT/scripts/dpic/run_dpi_child_repayment_e2e.sh" || fail "dpi_child_repayment_e2e"

phase "4 — repayment reversal"
if [[ "$SKIP_REVERSAL" != "1" && "$task_up" == "1" && "$actor_up" == "1" ]]; then
  bash "$ROOT/scripts/dpic/run_dpi_repayment_reversal_e2e.sh" || fail "dpi_repayment_reversal_e2e"
else
  echo "SKIP reversal (task=$task_up actor=$actor_up SKIP_REVERSAL=$SKIP_REVERSAL)"
fi

phase "5 — cross-EOD replay guard"
JOB_TIME="$JOB_TIME" LOAN_ACCOUNT_ID="$LOAN_ACCOUNT_ID" \
  bash "$ROOT/scripts/dpic/run_dpi_cross_eod_replay_guard.sh" || fail "cross_eod_replay"

phase "6 — NPA REGULAR_TO_NPA DPI movement"
if [[ "$actor_up" == "1" ]]; then
  maybe_restore
  bash "$ROOT/scripts/dpic/run_dpi_npa_movement_e2e.sh" || fail "dpi_npa_movement_e2e"
else
  echo "SKIP NPA DPI movement (actor down)"
fi

phase "7 — foreclosure write + DCF waiver"
if [[ "$SKIP_WAIVER" != "1" && "$actor_up" == "1" ]]; then
  maybe_restore
  bash "$ROOT/scripts/dpic/run_dpi_foreclosure_write_e2e.sh" || fail "dpi_foreclosure_write_e2e"
  maybe_restore
  run_case foreclosure.dpi_waiver_smoke
else
  echo "SKIP foreclosure write / waiver (actor=$actor_up SKIP_WAIVER=$SKIP_WAIVER)"
fi

trap - EXIT
dpi_print_fixture_health "$LOAN_ACCOUNT_ID"
echo ""
echo "=== DPI extended regression PASS (${SECONDS - _REGRESSION_START}s) ==="
