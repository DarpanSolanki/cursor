#!/usr/bin/env bash
# loanRepayment E2E — appropriates billed DPI (BILLED_DPI_INT_AMT / PAID_BILLED_DPI_INT_AMT legs).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT/scripts/dpic/lib/dpi_demo_fixture.sh"
# shellcheck disable=SC1091
source "$ROOT/scripts/dpic/lib/dpic_harness_lib.sh"

NTEST="$ROOT/scripts/bin/ntest.sh"
COMPILE="${COMPILE:-0}"

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
[[ -n "$AMOUNT" && "$AMOUNT" != "0" ]] || fail "no safe repay amount through $REPAY_DATE (harness SQL)"

DPI_BEFORE="$(dpi_pg -t -A -v ON_ERROR_STOP=1 -c \
  "SELECT COALESCE(sum(due_amount-paid_amount-COALESCE(waived_amount,0)),0)
   FROM mfi_accounting.loan_due_details
   WHERE loan_account_id=$LOAN_ACCOUNT_ID AND component_type='DPI' AND is_deleted=false")"
[[ "${DPI_BEFORE:-0}" != "0" && "${DPI_BEFORE}" != "0.000000" ]] || fail "no outstanding DPI before repayment (run restore_dpi_api_state first)"

CRN="DPIREPAY$(date +%s)"
echo ">>> loanRepayment amount=$AMOUNT (cap=${DPI_REPAY_CAP:-2000}) repay_ms=$REPAY_MS crn=$CRN"

demo_call_loan_repayment "$AMOUNT" "$CRN" "$REPAY_MS" "$ACCOUNT_NUMBER"

read -r dpi_open max_paid dpi_out <<<"$(
  dpi_pg -v ON_ERROR_STOP=1 -t -A -F' ' \
    -v loan_account_id="$LOAN_ACCOUNT_ID" \
    -f "$ROOT/scripts/dpic/sql/helpers/verify_dpi_repayment.sql" | tail -1
)"

echo ">>> post-repayment: dpi_due_open=$dpi_open max_dpi_paid=$max_paid dpi_outstanding=$dpi_out"
dpic_assert_lapd_dpi_paid_gt "$LOAN_ACCOUNT_ID" 0

# Full settle when we paid >= open DPI; partial cap may leave DPI open — still valid if lapd dpi > 0
python3 - "$AMOUNT" "$DPI_BEFORE" "$dpi_open" <<'PY'
import sys
amt, dpi_before, dpi_open = (float(x or 0) for x in sys.argv[1:4])
if amt + 0.01 >= dpi_before and dpi_open > 0.01:
    raise SystemExit(f"FAIL: paid {amt} (dpi_before={dpi_before}) but dpi still open={dpi_open}")
print(f"OK: repayment dpi check amt={amt} dpi_open={dpi_open}")
PY

echo ">>> API: dpi_overdue (when key present)"
dpic_assert_overview_dpi_overdue_eq 0 || echo "WARN: overview dpi_overdue not 0 (partial repay cap?)"

demo_save_state_kv LAST_REPAYMENT_CRN "$CRN" 2>/dev/null || true
demo_save_state_kv LAST_REPAYMENT_AMOUNT "$AMOUNT" 2>/dev/null || true
export LAST_REPAYMENT_CRN="$CRN" LAST_REPAYMENT_AMOUNT="$AMOUNT"

echo "=== DPI loanRepayment E2E PASS ==="
