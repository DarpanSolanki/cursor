#!/usr/bin/env bash
# Step 7 — Direct loanRepayment on demo day: appropriation + billed DPI settlement.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/lib/common.sh"
demo_load_state
demo_resolve_loan

REPAY_MS="${REPAY_MS:-$DEMO_ANCHOR_MS}"
REPAY_DATE="${REPAY_DATE:-$DEMO_ANCHOR_DATE}"
export ACCOUNT_NUMBER="$LAN"

demo_banner "STEP 7 — loanRepayment (demo day $REPAY_DATE)"
demo_talking_points \
  "Direct accounting loanRepayment (CASH, WITHOUT_MAKER_CHECKER) — not collections." \
  "Only dues with due_date <= repayment_time are appropriated; future EMI stays unsettled." \
  "BILLED_DPI_INT_AMT GL leg must post (MFI orchestration parity with loans_orc)." \
  "Headers need operation_mode=SELF for direct API (same as production LOS)."

demo_require_service

AMOUNT="$(demo_compute_overdue_repayment_amount "$REPAY_DATE")"
if [[ -z "$AMOUNT" || "$AMOUNT" == "0" ]]; then
  echo "FAIL: no overdue amount to repay for loan_account_id=$LOAN_ACCOUNT_ID as of $REPAY_DATE" >&2
  exit 1
fi

echo ">>> Overdue total (through $REPAY_DATE): ₹$AMOUNT"
demo_show_dpi_status

CRN="DEMOREPAY$(date +%s)"
echo ">>> loanRepayment amount=$AMOUNT client_reference_number=$CRN"
demo_call_loan_repayment "$AMOUNT" "$CRN" "$REPAY_MS" "$LAN"

FAIL=0
echo ""
echo ">>> DB assertions"
demo_assert_sql_eq \
  "SELECT count(*)::text FROM mfi_accounting.loan_due_details WHERE loan_account_id=$LOAN_ACCOUNT_ID AND component_type='DPI' AND is_deleted=false AND (due_amount-paid_amount-COALESCE(waived_amount,0))>0" \
  "0" "DPI dues fully settled" || FAIL=1

demo_assert_sql_gt \
  "SELECT COALESCE(max(dpi_amount),0)::text FROM mfi_accounting.loan_account_payments_details WHERE loan_account_id=$LOAN_ACCOUNT_ID" \
  "0" "payment row has dpi_amount > 0" || FAIL=1

export JOB_TIME="$REPAY_MS"
demo_sync_registry_correlators
echo ""
echo ">>> API assertions"
demo_assert_api_field_eq getLoanAccountOverviewDetails \
  account_overview_list[0].amount_details.dpi_overdue_amount 0 || FAIL=1
demo_assert_api_field_gt getLoanAccountOverviewDetails \
  account_overview_list[0].amount_details.dpi_paid_amount 0 || FAIL=1

demo_save_state_kv LAST_REPAYMENT_CRN "$CRN"
demo_save_state_kv LAST_REPAYMENT_AMOUNT "$AMOUNT"

[[ "$FAIL" == "0" ]] || exit 1
echo "=== Step 7 loanRepayment: PASS ==="
demo_pause
