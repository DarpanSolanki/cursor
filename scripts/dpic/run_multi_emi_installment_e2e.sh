#!/usr/bin/env bash
# Multi-EMI overdue: dpi_accrual_details must stamp latest overdue INT installment when a newer EMI is overdue.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT/scripts/dpic/lib/dpi_fixture_constants.sh"
if [[ "${DPI_USE_CUSTOM_LOAN:-0}" != "1" ]]; then
  dpi_use_grace_chain_loan
fi
: "${GRACE_DAYS:=3}"
: "${PRODUCT_CODE:=7676}"
: "${GO_LIVE_DDMM:=15-04-2025}"
# shellcheck source=lib/dpi_demo_fixture.sh
source "$ROOT/scripts/dpic/lib/dpi_demo_fixture.sh"
if [[ "${DPI_USE_CUSTOM_LOAN:-0}" != "1" ]]; then
  dpi_use_grace_chain_loan
fi
export JOB_TIME="$DPI_MULTI_EMI_JOB_TIME"
PG=(psql -h "${YB_HOST:-127.0.0.1}" -p "${YB_PORT:-5433}" -U "${YB_USER:-yugabyte}" -d "${YB_DB:-yugabyte}")
export PGPASSWORD="${PGPASSWORD:-yugabyte}"

echo "=== DPI multi-EMI installment_id E2E ==="
echo "  loan_account_id=$LOAN_ACCOUNT_ID grace=$GRACE_DAYS job_time=$JOB_TIME"

dpi_prep_before_batch

dpi_set_go_live_and_refresh "$GO_LIVE_DDMM" "$PRODUCT_CODE"

"${PG[@]}" -v ON_ERROR_STOP=1 \
  -v loan_account_id="$LOAN_ACCOUNT_ID" \
  -v grace_days="$GRACE_DAYS" \
  -f "$ROOT/scripts/dpic/sql/helpers/setup_grace_dpi_e2e.sql"

"${PG[@]}" -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" \
  -f "$ROOT/scripts/dpic/sql/helpers/quarantine_dpd_portfolio.sql" >/dev/null

"${PG[@]}" -v ON_ERROR_STOP=1 \
  -v loan_account_id="$LOAN_ACCOUNT_ID" \
  -v business_date_ms="$JOB_TIME" \
  -f "$ROOT/scripts/dpic/sql/helpers/sync_demo_past_due.sql" >/dev/null

echo ">>> dpiAccrualCalculation (multi-EMI window)"
dpi_call_batch dpiAccrualCalculation "$JOB_TIME"

fail() { echo "FAIL: $*" >&2; exit 1; }

verify_out=""
emi1_id="" emi2_id="" rows_on_emi1=0 rows_on_emi2=0 latest_inst_id=""
for _ in 1 2 3 4 5 6 8 10; do
  verify_out="$("${PG[@]}" -v ON_ERROR_STOP=1 -t -A -F'|' \
    -v loan_account_id="$LOAN_ACCOUNT_ID" \
    -f "$ROOT/scripts/dpic/sql/helpers/verify_multi_emi_installment_dpi_e2e.sql" | grep -E '^[0-9]' | tail -1)"
  IFS='|' read -r emi1_id emi2_id rows_on_emi1 rows_on_emi2 latest_inst_id <<<"$verify_out"
  if [[ -n "$emi1_id" && -n "$emi2_id" && "${rows_on_emi1:-0}" -gt 0 && "${rows_on_emi2:-0}" -gt 0 && "$latest_inst_id" == "$emi2_id" ]]; then
    break
  fi
  sleep 1
done

[[ -n "$emi1_id" && -n "$emi2_id" ]] || fail "need 2 overdue unpaid INT installments (emi1=$emi1_id emi2=$emi2_id verify='$verify_out')"
[[ "$emi1_id" != "$emi2_id" ]] || fail "EMI1 and EMI2 installment_id must differ"
[[ "${rows_on_emi1:-0}" -gt 0 ]] || fail "no accrual rows on EMI1 (earliest overdue period)"
[[ "${rows_on_emi2:-0}" -gt 0 ]] || fail "no accrual rows on EMI2 — latest overdue INT anchor not stamping newer EMI"
[[ "$latest_inst_id" == "$emi2_id" ]] || fail "latest row installment_id=$latest_inst_id expected EMI2=$emi2_id"

echo "PASS: emi1_rows=$rows_on_emi1 emi2_rows=$rows_on_emi2 latest_installment_id=$latest_inst_id"

echo ""
echo "=== multi-EMI installment E2E — accrual rows ==="
"${PG[@]}" -v ON_ERROR_STOP=1 -c "
SELECT da.installment_id, lid.installment_date::date, da.start_date::date, da.end_date::date,
       da.total_accrued_amount, da.base_amount
FROM mfi_accounting.dpi_accrual_details da
JOIN mfi_accounting.loan_installment_details lid ON lid.id = da.installment_id
WHERE da.loan_account_id = $LOAN_ACCOUNT_ID AND da.is_deleted = false
ORDER BY da.end_date ASC;
"
