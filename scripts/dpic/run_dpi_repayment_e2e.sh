#!/usr/bin/env bash
# loanRepayment E2E — billed DPI appropriation. Fail-fast: preflight first; cap DPI_E2E_TIMEOUT_S.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT/scripts/dpic/lib/dpi_demo_fixture.sh"
# shellcheck disable=SC1091
source "$ROOT/scripts/dpic/lib/dpic_harness_lib.sh"

fail() { echo "FAIL: $*" >&2; exit 1; }

echo "=== DPI loanRepayment E2E (loan=$LOAN_ACCOUNT_ID LAN=$ACCOUNT_NUMBER) ==="
dpi_ensure_accounting
dpi_export_correlators
dpi_restore_api_state

# shellcheck disable=SC1091
source "$ROOT/scripts/dpic/demo/lib/common.sh"
dpic_harness_preflight || fail "harness preflight"
dpic_repayment_timestamps

AMOUNT="$(dpic_compute_safe_repay_amount "$LOAN_ACCOUNT_ID" "$REPAY_DATE")"
[[ -n "$AMOUNT" && "$AMOUNT" != "0" ]] || fail "no safe repay amount through $REPAY_DATE"

DPI_BEFORE="$(dpi_pg -t -A -v ON_ERROR_STOP=1 -c \
  "SELECT COALESCE(sum(due_amount-paid_amount-COALESCE(waived_amount,0)),0)
   FROM mfi_accounting.loan_due_details
   WHERE loan_account_id=$LOAN_ACCOUNT_ID AND component_type='DPI' AND is_deleted=false")"
[[ "${DPI_BEFORE:-0}" != "0" && "${DPI_BEFORE}" != "0.000000" ]] || fail "no outstanding DPI (run restore_dpi_api_state)"

CRN="DPIREPAY$(date +%s)"
echo ">>> loanRepayment amount=$AMOUNT cap=${DPI_REPAY_CAP:-2000} repay_ms=$REPAY_MS"

demo_call_loan_repayment "$AMOUNT" "$CRN" "$REPAY_MS" "$ACCOUNT_NUMBER"

read -r dpi_open max_paid _ <<<"$(dpi_pg -v ON_ERROR_STOP=1 -t -A -F' ' \
  -v loan_account_id="$LOAN_ACCOUNT_ID" \
  -f "$ROOT/scripts/dpic/sql/helpers/verify_dpi_repayment.sql" | tail -1)"

dpic_assert_lapd_dpi_paid_gt "$LOAN_ACCOUNT_ID" 0
echo "=== DPI loanRepayment E2E PASS (dpi_open=$dpi_open lapd_dpi=$max_paid) ==="
