#!/usr/bin/env bash
# Impact-scoped DPI ship gate — modules selected by changed service code (DPI_SHIP_MODULES).
# Default all modules; workspace-close passes a minimal comma list from ship_change_scope.py
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DPIC="$ROOT/scripts/dpic"

fail() { echo "DPI_SHIP_CLOSE_FAIL: $*" >&2; exit 1; }
phase() { echo ""; echo "=== ship_close: $* ==="; }

has_mod() {
  local m="$1"
  [[ ",${DPI_SHIP_MODULES:-posting,eod,cross,billing,grace}," == *",$m,"* ]]
}

# Pin demo fixture — do not inherit LOAN_ACCOUNT_ID from fresh-disburse / last_certified env.
# shellcheck disable=SC1091
source "$DPIC/lib/dpi_fixture_constants.sh"
SHIP_FIXTURE_LOAN_ID="$DPI_FIXTURE_LOAN_ID"
SHIP_FIXTURE_LAN="$DPI_FIXTURE_LAN"
SHIP_MONTH_END_JOB_TIME=1782844200000
SHIP_NEXT_EMI_JOB_TIME=1782930600000

phase "ensure accounting"
bash "$ROOT/scripts/bin/agent-ops.sh" ensure accounting --compile 2>/dev/null || true

if has_mod posting; then
  phase "posting calendar (month-end accrual + EMI billing)"
  LOAN_ACCOUNT_ID="$SHIP_FIXTURE_LOAN_ID" ACCOUNT_NUMBER="$SHIP_FIXTURE_LAN" DEMO_LAN="$SHIP_FIXTURE_LAN" \
    bash "$DPIC/run_dpi_posting_calendar_regression.sh" || fail "posting_calendar"
fi

if has_mod eod; then
  phase "EOD txn chain (month-end job_time)"
  LOAN_ACCOUNT_ID="$SHIP_FIXTURE_LOAN_ID" ACCOUNT_NUMBER="$SHIP_FIXTURE_LAN" \
    MONTH_END_JOB_TIME="$SHIP_MONTH_END_JOB_TIME" NEXT_EMI_JOB_TIME="$SHIP_NEXT_EMI_JOB_TIME" \
    bash "$DPIC/run_dpi_eod_txn_regression.sh" || fail "eod_txn"
fi

if has_mod cross; then
  phase "cross-EOD replay guard (134497)"
  LOAN_ACCOUNT_ID="$SHIP_FIXTURE_LOAN_ID" ACCOUNT_NUMBER="$SHIP_FIXTURE_LAN" \
    bash "$DPIC/run_dpi_cross_eod_replay_guard.sh" || fail "cross_eod"
fi

if has_mod billing; then
  phase "billing UD next-EMI"
  LOAN_ACCOUNT_ID="$SHIP_FIXTURE_LOAN_ID" ACCOUNT_NUMBER="$SHIP_FIXTURE_LAN" \
    bash "$DPIC/run_dpi_billing_ud_e2e.sh" || fail "billing_ud"
  phase "post-maturity billing anchor"
  LOAN_ACCOUNT_ID="$SHIP_FIXTURE_LOAN_ID" ACCOUNT_NUMBER="$SHIP_FIXTURE_LAN" \
    bash "$DPIC/run_dpi_post_maturity_billing_e2e.sh" || fail "post_maturity_billing"
    bash "$DPIC/run_dpi_post_maturity_billing_catchup_e2e.sh" || fail "post_maturity_billing_catchup"
fi

if has_mod grace; then
  phase "grace + overlap E2E (grace-chain LAN $DPI_GRACE_CHAIN_LAN)"
  bash "$DPIC/run_grace_dpi_e2e.sh" || fail "grace_e2e"
  bash "$DPIC/run_grace_overlap_dpi_e2e.sh" || fail "grace_overlap_e2e"
fi

echo "DPI_SHIP_CLOSE_VERIFY PASS (modules=${DPI_SHIP_MODULES:-posting,eod,cross,billing,grace})"
