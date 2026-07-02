#!/usr/bin/env bash
# Local DPI grace E2E: setup grace=3 on demo overdue loan → dpiAccrualCalculation → SQL asserts.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
LOAN_ACCOUNT_ID="${LOAN_ACCOUNT_ID:-8057160}"
GRACE_DAYS="${GRACE_DAYS:-3}"
FIRST_EMI_DUE_DATE="${FIRST_EMI_DUE_DATE:-2026-05-14}"
# First business day after grace gate (due + grace + 1 = 2026-05-18); run through 2026-05-20 EOD.
JOB_TIME="${JOB_TIME:-1779280200000}"
PG=(psql -h "${YB_HOST:-127.0.0.1}" -p "${YB_PORT:-5433}" -U "${YB_USER:-yugabyte}" -d "${YB_DB:-yugabyte}")
export PGPASSWORD="${PGPASSWORD:-yugabyte}"
NTEST="$ROOT/scripts/bin/ntest.sh"
WAIT_BATCH="$ROOT/scripts/dpic/lib/wait_batch_job.sh"

echo "=== DPI grace E2E ==="
echo "  loan_account_id=$LOAN_ACCOUNT_ID grace=$GRACE_DAYS first_emi_due=$FIRST_EMI_DUE_DATE job_time=$JOB_TIME"

code="$(curl -s -m 5 -o /dev/null -w '%{http_code}' -X POST "http://localhost:8002/accounting/api/v1/getLoanAccountBasicDetails" \
  -H 'Content-Type: application/json' \
  -d '{"headers":{"tenant_code":"mfi","user_id":"3","stan":"grace_e2e","client_code":"NOVOPAY","channel_code":"WEB","function_code":"DEFAULT","function_sub_code":"DEFAULT","run_mode":"REAL"},"request":{"account_number":"6004041325"}}' \
  2>/dev/null || echo 000)"
if [[ "$code" != "200" ]]; then
  echo "FAIL: accounting not reachable (HTTP $code)" >&2
  exit 1
fi

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
JOB_TIME="$JOB_TIME" "$NTEST" api accounting dpiAccrualCalculation --batch --job-time "$JOB_TIME" >/dev/null
bash "$WAIT_BATCH" dpiAccrualCalculation "$JOB_TIME"

"${PG[@]}" -v ON_ERROR_STOP=1 \
  -v loan_account_id="$LOAN_ACCOUNT_ID" \
  -v grace_days="$GRACE_DAYS" \
  -v first_emi_due_date="$FIRST_EMI_DUE_DATE" \
  -f "$ROOT/scripts/dpic/sql/helpers/verify_grace_dpi_e2e.sql"

echo ""
echo "=== grace E2E complete ==="
"${PG[@]}" -v ON_ERROR_STOP=1 -c "
SELECT start_date::date, end_date::date, total_accrued_amount, base_amount
FROM mfi_accounting.dpi_accrual_details
WHERE loan_account_id = $LOAN_ACCOUNT_ID AND is_deleted = false
ORDER BY end_date ASC
LIMIT 8;
"
