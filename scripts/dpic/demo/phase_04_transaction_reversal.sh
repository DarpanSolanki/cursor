#!/usr/bin/env bash
# Phase 4 — loanAccountTransactionReversal: INITIATE (DEFAULT) then APPROVE.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/lib/common.sh"
demo_load_state
demo_resolve_loan
export ACCOUNT_NUMBER="$LAN"

demo_banner "PHASE 4 — loan transaction reversal (INITIATE → APPROVE)"
demo_talking_points \
  "Individual LAN reversal via loanAccountTransactionReversal (not childLoanTransactionReversal)." \
  "Step 1: function_code=DEFAULT creates PENDING transaction_reversal_details + task." \
  "Step 2: function_code=APPROVE executes reversal (dues + GL); headers need operation_mode=SELF." \
  "Requires task :8019 (mfi_integration_v3.3.1.1) + actor :8003; user_id=${DEMO_REVERSAL_USER_ID:-53}."

demo_require_reversal_services
demo_ensure_task_reversal_prereqs
demo_load_last_repayment_for_reversal

REV_MS="$(demo_platform_reversal_date_ms)"
STAN_BASE="DEMOREV$(date +%s)"

echo ">>> Repayment to reverse: ref=$REV_TXN_REF crn=$REV_CRN amount=$REV_AMOUNT (dpi=$REV_DPI)"
echo ">>> transaction_reversal_date (platform today 18:00 IST): $REV_MS"
echo ""

echo ">>> Step 1 — INITIATE (function_code=DEFAULT, expect 30375)"
demo_call_loan_transaction_reversal DEFAULT "${STAN_BASE}I" "$REV_MS"

echo ""
echo ">>> Step 2 — APPROVE (function_code=APPROVE, expect 30376)"
demo_call_loan_transaction_reversal APPROVE "${STAN_BASE}A" "$REV_MS"

FAIL=0
echo ""
echo ">>> DB assertions"
demo_assert_sql_eq \
  "SELECT COALESCE(tm.reversed,false)::text FROM mfi_accounting.transaction_master tm WHERE tm.reference_number='${REV_TXN_REF}'" \
  "true" "transaction_master.reversed=true" || FAIL=1

demo_assert_sql_eq \
  "SELECT count(*)::text FROM mfi_accounting.transaction_reversal_details WHERE loan_account_id=$LOAN_ACCOUNT_ID AND task_status='APPROVED' AND is_deleted=false" \
  "1" "one APPROVED transaction_reversal_details row" || FAIL=1

if [[ "${REV_DPI:-0}" != "0" && "${REV_DPI}" != "0.000000" ]]; then
  demo_assert_sql_gt \
    "SELECT count(*)::text FROM mfi_accounting.loan_due_details WHERE loan_account_id=$LOAN_ACCOUNT_ID AND component_type='DPI' AND is_deleted=false AND (due_amount-paid_amount-COALESCE(waived_amount,0))>0" \
    "0" "DPI dues outstanding after reversal" || FAIL=1
  demo_assert_api_field_gt getLoanAccountOverviewDetails \
    account_overview_list[0].amount_details.dpi_overdue_amount 0 || FAIL=1
fi

[[ "$FAIL" == "0" ]] || exit 1
echo "=== Phase 4 transaction reversal: PASS ==="
demo_pause
