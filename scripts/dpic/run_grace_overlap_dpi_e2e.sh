#!/usr/bin/env bash
# Multi-EMI grace overlap: DPI accrual continues through EMI2 grace (not killed by latest-EMI grace).
# Product stamps overlap-window slices to EMI2 (latest due ≤ segStart); EMI1 seals at next due.
# Causes FAIL on the old "latest-EMI grace kill-switch" bug (zero accrual in grace window).
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
export JOB_TIME="$DPI_GRACE_OVERLAP_JOB_TIME"
PG=(psql -h "${YB_HOST:-127.0.0.1}" -p "${YB_PORT:-5433}" -U "${YB_USER:-yugabyte}" -d "${YB_DB:-yugabyte}")
export PGPASSWORD="${PGPASSWORD:-yugabyte}"
NTEST="$ROOT/scripts/bin/ntest.sh"
WAIT_BATCH="$ROOT/scripts/dpic/lib/wait_batch_job.sh"
RUN_AUDIT="${RUN_COLUMN_AUDIT:-1}"

echo "=== DPI grace overlap E2E (accrual continues in EMI2 grace; owned by EMI2) ==="
echo "  loan_account_id=$LOAN_ACCOUNT_ID grace=$GRACE_DAYS job_time=$JOB_TIME"

bash "$ROOT/scripts/bin/novopay-service.sh" ensure accounting ${COMPILE:+--compile}

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

if [[ -f "$ROOT/scripts/dpic/sql/helpers/clear_batch_failure_audit.sql" ]]; then
  JOB_TIME="$JOB_TIME" "${PG[@]}" -v ON_ERROR_STOP=1 \
    -v loan_account_id="$LOAN_ACCOUNT_ID" \
    -f "$ROOT/scripts/dpic/sql/helpers/clear_batch_failure_audit.sql" >/dev/null 2>&1 || true
fi

fail() { echo "FAIL: $*" >&2; exit 1; }

qa_fire_batch() {
  local api="$1" job_time="$2"
  local rs
  rs="$(date +%s)"
  JOB_TIME="$job_time" "$NTEST" api accounting "$api" --batch --job-time "$job_time" >/dev/null
  bash "$WAIT_BATCH" "$api" "$job_time" "$rs"
}

echo ">>> dpiAccrualCalculation (overlap window through EMI2 grace)"
qa_fire_batch dpiAccrualCalculation "$JOB_TIME"

verify_out="$("${PG[@]}" -v ON_ERROR_STOP=1 -t -A -F'|' \
  -v loan_account_id="$LOAN_ACCOUNT_ID" \
  -v grace_days="$GRACE_DAYS" \
  -f "$ROOT/scripts/dpic/sql/helpers/verify_grace_overlap_dpi_e2e.sql" | grep -E '^[0-9]' | tail -1)"

# Settle DB write(s) — partition COMPLETED can race ahead of JPA flush on cold JVM.
for _ in 1 2 3 4 5; do
  IFS='|' read -r emi1_id emi1_due emi1_od emi2_id emi2_due emi2_od rows_overlap amt_overlap emi1_rows emi2_rows overlap_ok <<<"$verify_out"
  if [[ "$overlap_ok" == "t" ]]; then
    break
  fi
  sleep 1
  verify_out="$("${PG[@]}" -v ON_ERROR_STOP=1 -t -A -F'|' \
    -v loan_account_id="$LOAN_ACCOUNT_ID" \
    -v grace_days="$GRACE_DAYS" \
    -f "$ROOT/scripts/dpic/sql/helpers/verify_grace_overlap_dpi_e2e.sql" | grep -E '^[0-9]' | tail -1)"
done

IFS='|' read -r emi1_id emi1_due emi1_od emi2_id emi2_due emi2_od rows_overlap amt_overlap emi1_rows emi2_rows overlap_ok <<<"$verify_out"

[[ -n "$emi1_id" && -n "$emi2_id" && "$emi1_id" != "$emi2_id" ]] || fail "need two unpaid INT EMIs (got emi1=$emi1_id emi2=$emi2_id)"
[[ "$overlap_ok" == "t" ]] || fail "overlap_ok=$overlap_ok rows=$rows_overlap amt=$amt_overlap emi1_rows=$emi1_rows emi2_rows=$emi2_rows (expect accrual in ($emi2_due,$emi2_od) owned by EMI2; EMI1 sealed at next due)"

echo "PASS: accrual continues in EMI2 grace ($emi2_due .. $emi2_od); amt=$amt_overlap emi2_rows=$emi2_rows emi1_rows=$emi1_rows (EMI1 sealed)"

echo ""
echo "=== accrual rows around EMI2 due ==="
"${PG[@]}" -v ON_ERROR_STOP=1 -c "
SELECT da.installment_id, lid.installment_date::date, da.start_date::date, da.end_date::date,
       da.total_accrued_amount, da.base_amount
FROM mfi_accounting.dpi_accrual_details da
JOIN mfi_accounting.loan_installment_details lid ON lid.id = da.installment_id
WHERE da.loan_account_id = $LOAN_ACCOUNT_ID AND da.is_deleted = false
  AND da.end_date::date >= DATE '2026-06-10'
ORDER BY da.end_date ASC;
"

if [[ "$RUN_AUDIT" == "1" ]]; then
  echo ">>> dpiAccrualBooking + dpiBilling (column audit)"
  qa_fire_batch dpiAccrualBooking "$JOB_TIME"
  qa_fire_batch dpiBilling "$JOB_TIME"
  # Overlap job_time is 2026-06-17 18:00 IST — audit wants YYYY-MM-DD
  proof_date="${PROOF_DATE:-2026-06-17}"
  bash "$ROOT/scripts/dpic/lib/run_dpi_column_audit.sh" "$LOAN_ACCOUNT_ID" "$proof_date" \
    || fail "column audit violations after calc+booking+billing"
  echo "PASS: column audit 0 violations (loan=$LOAN_ACCOUNT_ID)"
fi
