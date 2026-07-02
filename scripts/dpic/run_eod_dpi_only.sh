#!/usr/bin/env bash
# Fast local DPI EOD: skip DPD, quarantine portfolio to 1 loan, poll batch completion (~3-5s/job).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
JOB_TIME="${JOB_TIME:-1781267400000}"
LOAN_ACCOUNT_ID="${LOAN_ACCOUNT_ID:-}"
SEED_CALC_WINDOW="${SEED_CALC_WINDOW:-1}"
SYNC_PAST_DUE="${SYNC_PAST_DUE:-1}"
QUARANTINE_PORTFOLIO="${QUARANTINE_PORTFOLIO:-1}"
PG=(psql -h "${YB_HOST:-127.0.0.1}" -p "${YB_PORT:-5433}" -U "${YB_USER:-yugabyte}" -d "${YB_DB:-yugabyte}")
export PGPASSWORD="${PGPASSWORD:-yugabyte}"
NTEST="$ROOT/scripts/bin/ntest.sh"
WAIT_BATCH="$ROOT/scripts/dpic/lib/wait_batch_job.sh"
chmod +x "$WAIT_BATCH" 2>/dev/null || true

call_batch() {
  local api="$1"
  echo "=== ${api} job_time=${JOB_TIME} ==="
  JOB_TIME="$JOB_TIME" "$NTEST" api accounting "$api" --batch --job-time "$JOB_TIME"
  bash "$WAIT_BATCH" "$api" "$JOB_TIME"
}

if [[ -n "$LOAN_ACCOUNT_ID" && "$QUARANTINE_PORTFOLIO" == "1" ]]; then
  echo ">>> Quarantine DPD portfolio (only loan $LOAN_ACCOUNT_ID eligible)"
  "${PG[@]}" -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" \
    -f "$ROOT/scripts/dpic/sql/helpers/quarantine_dpd_portfolio.sql"
fi

if [[ -n "$LOAN_ACCOUNT_ID" && "$SYNC_PAST_DUE" == "1" ]]; then
  echo ">>> Sync past_due_days loan_account_id=$LOAN_ACCOUNT_ID"
  "${PG[@]}" -v ON_ERROR_STOP=1 \
    -v loan_account_id="$LOAN_ACCOUNT_ID" \
    -v business_date_ms="$JOB_TIME" \
    -f "$ROOT/scripts/dpic/sql/helpers/sync_demo_past_due.sql"
fi

if [[ -n "$LOAN_ACCOUNT_ID" && "$SEED_CALC_WINDOW" == "1" ]]; then
  echo ">>> Calc window seed loan_account_id=$LOAN_ACCOUNT_ID"
  "${PG[@]}" -v ON_ERROR_STOP=1 \
    -v loan_account_id="$LOAN_ACCOUNT_ID" \
    -v business_date_ms="$JOB_TIME" \
    -f "$ROOT/scripts/dpic/sql/helpers/seed_calc_window.sql"
fi

call_batch dpiAccrualCalculation
call_batch dpiAccrualBooking
call_batch dpiBilling

echo "Done (${LOAN_ACCOUNT_ID:-all loans})."
