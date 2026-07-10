#!/usr/bin/env bash
# Local DPI grace E2E: setup grace=3 on demo overdue loan → dpiAccrualCalculation → SQL asserts.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT/scripts/dpic/lib/dpi_fixture_constants.sh"
if [[ "${DPI_USE_CUSTOM_LOAN:-0}" != "1" ]]; then
  dpi_use_grace_chain_loan
fi
: "${GRACE_DAYS:=3}"
: "${FIRST_EMI_DUE_DATE:=2026-05-14}"
: "${PRODUCT_CODE:=7676}"
: "${GO_LIVE_DDMM:=15-04-2025}"
# shellcheck source=lib/dpi_demo_fixture.sh
source "$ROOT/scripts/dpic/lib/dpi_demo_fixture.sh"
if [[ "${DPI_USE_CUSTOM_LOAN:-0}" != "1" ]]; then
  dpi_use_grace_chain_loan
fi
export JOB_TIME="$DPI_GRACE_JOB_TIME"
PG=(psql -h "${YB_HOST:-127.0.0.1}" -p "${YB_PORT:-5433}" -U "${YB_USER:-yugabyte}" -d "${YB_DB:-yugabyte}")
export PGPASSWORD="${PGPASSWORD:-yugabyte}"
NTEST="$ROOT/scripts/bin/ntest.sh"
WAIT_BATCH="$ROOT/scripts/dpic/lib/wait_batch_job.sh"

echo "=== DPI grace E2E ==="
echo "  loan_account_id=$LOAN_ACCOUNT_ID grace=$GRACE_DAYS first_emi_due=$FIRST_EMI_DUE_DATE job_time=$JOB_TIME"

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

echo ">>> dpiAccrualCalculation"
run_started="$(date +%s)"
JOB_TIME="$JOB_TIME" "$NTEST" api accounting dpiAccrualCalculation --batch --job-time "$JOB_TIME" >/dev/null
bash "$WAIT_BATCH" dpiAccrualCalculation "$JOB_TIME" "$run_started"

# columns: inside|first_start|first_end|amount|expected_start|gate_end|grace_ok
verify_out=""
grace_ok=""
for _ in 1 2 3 4 5; do
  verify_out="$("${PG[@]}" -v ON_ERROR_STOP=1 -t -A -F'|' \
    -v loan_account_id="$LOAN_ACCOUNT_ID" \
    -v grace_days="$GRACE_DAYS" \
    -v first_emi_due_date="$FIRST_EMI_DUE_DATE" \
    -f "$ROOT/scripts/dpic/sql/helpers/verify_grace_dpi_e2e.sql" | grep -E '^[0-9]' | tail -1)"
  IFS='|' read -r inside first_start first_end first_amount expected_start gate_end grace_ok <<<"$verify_out"
  if [[ "$grace_ok" == "t" ]]; then
    break
  fi
  sleep 1
done

fail() { echo "FAIL: $*" >&2; exit 1; }
[[ "$grace_ok" == "t" ]] || fail "grace_ok=$grace_ok inside=$inside first=[$first_start..$first_end] amount=$first_amount expected_start=$expected_start gate=$gate_end verify='$verify_out'"

echo "PASS: gate_end=$gate_end first=[$first_start..$first_end] amount=$first_amount start=due_date"

echo ""
echo "=== grace E2E complete ==="
"${PG[@]}" -v ON_ERROR_STOP=1 -c "
SELECT start_date::date, end_date::date, total_accrued_amount, base_amount
FROM mfi_accounting.dpi_accrual_details
WHERE loan_account_id = $LOAN_ACCOUNT_ID AND is_deleted = false
ORDER BY end_date ASC
LIMIT 8;
"