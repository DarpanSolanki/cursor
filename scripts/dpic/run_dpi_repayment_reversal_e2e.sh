#!/usr/bin/env bash
# loanRepayment → loanAccountTransactionReversal — DPI dues restored after reversal.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT/scripts/dpic/lib/dpi_demo_fixture.sh"
# shellcheck disable=SC1091
source "$ROOT/scripts/dpic/demo/lib/common.sh"

export STATE_FILE="${STATE_FILE:-$ROOT/scripts/scratch/dpic_repay_rev_state.env}"
export LOAN_ACCOUNT_ID ACCOUNT_NUMBER

fail() { echo "FAIL: $*" >&2; exit 1; }

echo "=== DPI repayment + reversal E2E (loan=$LOAN_ACCOUNT_ID) ==="
dpi_ensure_accounting
demo_require_reversal_services
demo_ensure_task_reversal_prereqs

# Fresh repay leg (skip if last repayment already has dpi and not reversed)
if ! demo_load_last_repayment_for_reversal 2>/dev/null; then
  bash "$ROOT/scripts/dpic/run_dpi_repayment_e2e.sh"
fi
export LOAN_ACCOUNT_ID="${LOAN_ACCOUNT_ID:-8060160}"
demo_load_last_repayment_for_reversal

REV_MS="$(demo_platform_reversal_date_ms)"
STAN_BASE="DPIREV$(date +%s)"
echo ">>> reversing ref=$REV_TXN_REF dpi=$REV_DPI"

demo_call_loan_transaction_reversal DEFAULT "${STAN_BASE}I" "$REV_MS"
demo_call_loan_transaction_reversal APPROVE "${STAN_BASE}A" "$REV_MS"

FAIL=0
demo_assert_sql_eq \
  "SELECT COALESCE(tm.reversed,false)::text FROM mfi_accounting.transaction_master tm WHERE tm.reference_number='${REV_TXN_REF}'" \
  "true" "transaction_master.reversed=true" || FAIL=1

if [[ "${REV_DPI:-0}" != "0" && "${REV_DPI}" != "0.000000" ]]; then
  demo_assert_sql_gt \
    "SELECT count(*)::text FROM mfi_accounting.loan_due_details WHERE loan_account_id=$LOAN_ACCOUNT_ID AND component_type='DPI' AND is_deleted=false AND (due_amount-paid_amount-COALESCE(waived_amount,0))>0" \
    "0" "DPI dues outstanding after reversal" || FAIL=1
  demo_assert_sql_gt \
    "SELECT COALESCE(dpi_amount,0)::text FROM mfi_accounting.transaction_reversal_details WHERE loan_account_id=$LOAN_ACCOUNT_ID AND transaction_ref_no='${REV_TXN_REF}' AND is_deleted=false ORDER BY id DESC LIMIT 1" \
    "0" "transaction_reversal_details.dpi_amount > 0" || FAIL=1
fi

[[ "$FAIL" == "0" ]] || exit 1
echo "=== DPI repayment + reversal E2E PASS ==="
