#!/usr/bin/env bash
# loanRepayment E2E — appropriates billed DPI (BILLED_DPI_INT_AMT / PAID_BILLED_DPI_INT_AMT legs).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT/scripts/dpic/lib/dpi_demo_fixture.sh"

NTEST="$ROOT/scripts/bin/ntest.sh"
COMPILE="${COMPILE:-0}"

fail() { echo "FAIL: $*" >&2; exit 1; }

echo "=== DPI loanRepayment E2E (loan=$LOAN_ACCOUNT_ID LAN=$ACCOUNT_NUMBER) ==="
dpi_ensure_accounting
dpi_export_correlators
dpi_restore_api_state

REPAY_MS="$(dpi_job_time_repay_ms)"
ANCHOR_DATE="$(dpi_job_time_anchor_date)"

AMOUNT="$(dpi_pg -t -A -v ON_ERROR_STOP=1 \
  -v loan_account_id="$LOAN_ACCOUNT_ID" -v anchor_date="$ANCHOR_DATE" <<'SQL'
SELECT COALESCE(SUM(due_amount - paid_amount - COALESCE(waived_amount, 0)), 0)::numeric(20, 0)
FROM mfi_accounting.loan_due_details
WHERE loan_account_id = :loan_account_id::bigint
  AND is_deleted = false
  AND due_date::date <= :'anchor_date'::date
  AND (due_amount - paid_amount - COALESCE(waived_amount, 0)) > 0;
SQL
)"
[[ -n "$AMOUNT" && "$AMOUNT" != "0" ]] || fail "no overdue amount through $ANCHOR_DATE"

DPI_BEFORE="$(dpi_pg -t -A -v ON_ERROR_STOP=1 -c \
  "SELECT COALESCE(sum(due_amount-paid_amount-COALESCE(waived_amount,0)),0)
   FROM mfi_accounting.loan_due_details
   WHERE loan_account_id=$LOAN_ACCOUNT_ID AND component_type='DPI' AND is_deleted=false")"
[[ "${DPI_BEFORE:-0}" != "0" && "${DPI_BEFORE}" != "0.000000" ]] || fail "no outstanding DPI before repayment (run restore_dpi_api_state first)"

CRN="DPIREPAY$(date +%s)"
echo ">>> loanRepayment amount=$AMOUNT repay_ms=$REPAY_MS crn=$CRN"

# shellcheck disable=SC1091
source "$ROOT/scripts/dpic/demo/lib/common.sh"
demo_call_loan_repayment "$AMOUNT" "$CRN" "$REPAY_MS" "$ACCOUNT_NUMBER"

read -r dpi_open max_paid dpi_out <<<"$(
  dpi_pg -v ON_ERROR_STOP=1 -t -A -F' ' \
    -v loan_account_id="$LOAN_ACCOUNT_ID" \
    -f "$ROOT/scripts/dpic/sql/helpers/verify_dpi_repayment.sql" | tail -1
)"

echo ">>> post-repayment: dpi_due_open=$dpi_open max_dpi_paid=$max_paid dpi_outstanding=$dpi_out"
[[ "${dpi_open:-1}" == "0" ]] || fail "DPI dues still open after repayment"
python3 - "$max_paid" <<'PY'
import sys
if float(sys.argv[1] or 0) <= 0:
    raise SystemExit("FAIL: payment row dpi_amount not > 0")
print(f"OK: payment dpi_amount={sys.argv[1]}")
PY

echo ">>> API: dpi_overdue should be 0"
demo_assert_api_field_eq getLoanAccountOverviewDetails \
  account_overview_list[0].amount_details.dpi_overdue_amount 0
demo_assert_api_field_gt getLoanAccountOverviewDetails \
  account_overview_list[0].amount_details.dpi_paid_amount 0

demo_save_state_kv LAST_REPAYMENT_CRN "$CRN" 2>/dev/null || true
demo_save_state_kv LAST_REPAYMENT_AMOUNT "$AMOUNT" 2>/dev/null || true
export LAST_REPAYMENT_CRN="$CRN" LAST_REPAYMENT_AMOUNT="$AMOUNT"

echo "=== DPI loanRepayment E2E PASS ==="
