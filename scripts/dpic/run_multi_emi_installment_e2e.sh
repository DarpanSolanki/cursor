#!/usr/bin/env bash
# Multi-EMI overdue: dpi_accrual_details must stamp latest overdue INT installment when a newer EMI is overdue.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
LOAN_ACCOUNT_ID="${LOAN_ACCOUNT_ID:-8060160}"
GRACE_DAYS="${GRACE_DAYS:-3}"
DEMO_LAN="${DEMO_LAN:-6004044425}"
# Past second EMI grace (due 2026-06-18 + grace 3 → accrual anchor switches to EMI2).
JOB_TIME="${JOB_TIME:-1782563400000}"
PG=(psql -h "${YB_HOST:-127.0.0.1}" -p "${YB_PORT:-5433}" -U "${YB_USER:-yugabyte}" -d "${YB_DB:-yugabyte}")
export PGPASSWORD="${PGPASSWORD:-yugabyte}"
NTEST="$ROOT/scripts/bin/ntest.sh"
WAIT_BATCH="$ROOT/scripts/dpic/lib/wait_batch_job.sh"

echo "=== DPI multi-EMI installment_id E2E ==="
echo "  loan_account_id=$LOAN_ACCOUNT_ID grace=$GRACE_DAYS job_time=$JOB_TIME"

bash "$ROOT/scripts/bin/novopay-service.sh" ensure accounting ${COMPILE:+--compile}

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
run_started="$(date +%s)"
JOB_TIME="$JOB_TIME" "$NTEST" api accounting dpiAccrualCalculation --batch --job-time "$JOB_TIME" >/dev/null
bash "$WAIT_BATCH" dpiAccrualCalculation "$JOB_TIME" "$run_started"

verify_out="$("${PG[@]}" -v ON_ERROR_STOP=1 -t -A -F'|' \
  -v loan_account_id="$LOAN_ACCOUNT_ID" \
  -f "$ROOT/scripts/dpic/sql/helpers/verify_multi_emi_installment_dpi_e2e.sql" | tail -1)"

IFS='|' read -r emi1_id emi2_id rows_on_emi1 rows_on_emi2 latest_inst_id <<<"$verify_out"

fail() { echo "FAIL: $*" >&2; exit 1; }

[[ -n "$emi1_id" && -n "$emi2_id" ]] || fail "need 2 overdue unpaid INT installments (emi1=$emi1_id emi2=$emi2_id)"
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
