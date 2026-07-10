#!/usr/bin/env bash
# DPD job + DPI EOD batches. Business date via JOB_TIME (default 12-Jun-2026 18:00 IST).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
JOB_TIME="${JOB_TIME:-1781267400000}"
BASE_URL="${ACCOUNTING_BASE_URL:-http://localhost:8002}"
CTX="${ACCOUNTING_CONTEXT_PATH:-/accounting}"
STAN="${STAN:-$(date +%s%3N)}"
LOAN_ACCOUNT_ID="${LOAN_ACCOUNT_ID:-}"
SEED_CALC_WINDOW="${SEED_CALC_WINDOW:-0}"
PG=(psql -h "${YB_HOST:-127.0.0.1}" -p "${YB_PORT:-5433}" -U "${YB_USER:-yugabyte}" -d "${YB_DB:-yugabyte}")
export PGPASSWORD="${PGPASSWORD:-yugabyte}"

call_batch() {
  local api="$1"
  local body
  body=$(cat <<EOF
{
  "headers": {
    "tenant_code": "mfi",
    "client_code": "NOVOPAY",
    "channel_code": "WEB",
    "user_id": "3",
    "stan": "${STAN}_${api}",
    "function_code": "DEFAULT",
    "function_sub_code": "BATCH",
    "run_mode": "REAL"
  },
  "request": {
    "job_time": "${JOB_TIME}",
    "op_code": "START"
  }
}
EOF
)
  echo "=== ${api} job_time=${JOB_TIME} ==="
  curl -sS -X POST "${BASE_URL}${CTX}/api/v1/${api}" \
    -H 'Content-Type: application/json' \
    -d "${body}"
  echo
}

if [[ -n "$LOAN_ACCOUNT_ID" && "$SEED_CALC_WINDOW" == "1" ]]; then
  echo ">>> BYPASS: seed_calc_window.sql (documented workaround — see sql/helpers/seed_calc_window.sql)"
  "${PG[@]}" -v ON_ERROR_STOP=1 \
    -v loan_account_id="$LOAN_ACCOUNT_ID" \
    -v business_date_ms="$JOB_TIME" \
    -f "$ROOT/scripts/dpic/sql/helpers/seed_calc_window.sql"
fi

call_batch loanAccountDpdCalcJob
sleep 2
call_batch dpiAccrualCalculation
sleep 2
call_batch dpiAccrualBooking
sleep 2
call_batch dpiBilling

echo ""
echo "Logs: ${ROOT}/novopay-platform-accounting-v2/logs/mfi/accounting-mfi.log"
