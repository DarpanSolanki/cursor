#!/usr/bin/env bash
# childLoanRepayment E2E — JLG child loan billed DPI appropriation (see dpi_fixture_constants.sh).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT/scripts/dpic/lib/dpi_demo_fixture.sh"

export LOAN_ACCOUNT_ID="${CHILD_LOAN_ACCOUNT_ID:-$DPI_CHILD_JLG_LOAN_ID}"
export ACCOUNT_NUMBER="${CHILD_ACCOUNT_NUMBER:-$DPI_CHILD_JLG_LAN}"
export DEMO_LAN="$ACCOUNT_NUMBER"

fail() { echo "FAIL: $*" >&2; exit 1; }

echo "=== DPI childLoanRepayment E2E (loan=$LOAN_ACCOUNT_ID LAN=$ACCOUNT_NUMBER) ==="
dpi_ensure_accounting
dpi_export_correlators
dpi_prepare_repay_fixture
dpi_restore_api_state

# shellcheck disable=SC1091
source "$ROOT/scripts/dpic/demo/lib/common.sh"

demo_resolve_repayment_timestamps
ANCHOR_DATE="$REPAY_DATE"

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
[[ -n "$AMOUNT" && "$AMOUNT" != "0" ]] || fail "no overdue amount through $ANCHOR_DATE (run EOD on child loan first)"

DPI_BEFORE="$(dpi_pg -t -A -v ON_ERROR_STOP=1 -c \
  "SELECT COALESCE(sum(due_amount-paid_amount-COALESCE(waived_amount,0)),0)
   FROM mfi_accounting.loan_due_details
   WHERE loan_account_id=$LOAN_ACCOUNT_ID AND component_type='DPI' AND is_deleted=false")"
python3 - "$DPI_BEFORE" <<'PY'
import sys
if float(sys.argv[1] or 0) <= 0:
    raise SystemExit("FAIL: no outstanding DPI on child loan before repayment")
print(f"OK: child DPI open={sys.argv[1]}")
PY

CRN="DPICHREPAY$(date +%s)"
echo ">>> childLoanRepayment amount=$AMOUNT repay_date=$REPAY_DATE crn=$CRN"
demo_call_child_loan_repayment "$AMOUNT" "$CRN" "$REPAY_MS" "$ACCOUNT_NUMBER"

read -r dpi_open max_paid dpi_out <<<"$(
  dpi_pg -v ON_ERROR_STOP=1 -t -A -F' ' \
    -v loan_account_id="$LOAN_ACCOUNT_ID" \
    -f "$ROOT/scripts/dpic/sql/helpers/verify_dpi_repayment.sql" | tail -1
)"

echo ">>> post-repayment: dpi_due_open=$dpi_open max_dpi_paid=$max_paid"
[[ "${dpi_open:-1}" == "0" ]] || fail "child DPI dues still open after repayment"
python3 - "$max_paid" <<'PY'
import sys
if float(sys.argv[1] or 0) <= 0:
    raise SystemExit("FAIL: child payment row dpi_amount not > 0")
print(f"OK: child payment dpi_amount={sys.argv[1]}")
PY

echo "=== DPI childLoanRepayment E2E PASS ==="
