#!/usr/bin/env bash
# Guard: dpiBilling cross-EOD replay must not hit 134497 (numeric client_ref fix 346d9efe6).
# Run EOD twice on same job_time WITHOUT clearing transaction_master — second run must PASS.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
export LOAN_ACCOUNT_ID="${LOAN_ACCOUNT_ID:-8060160}"
export JOB_TIME="${JOB_TIME:-1781699400000}"
export RESET_DPI_BOOKING="${RESET_DPI_BOOKING:-1}"
export QUARANTINE_PORTFOLIO="${QUARANTINE_PORTFOLIO:-1}"
export SYNC_PAST_DUE="${SYNC_PAST_DUE:-1}"
PG=(psql -h "${YB_HOST:-127.0.0.1}" -p "${YB_PORT:-5433}" -U "${YB_USER:-yugabyte}" -d "${YB_DB:-yugabyte}")
export PGPASSWORD="${PGPASSWORD:-yugabyte}"
LOG_DIR="$ROOT/scripts/scratch/logs"
mkdir -p "$LOG_DIR"
ACCT_LOG="${ACCOUNTING_LOG:-$ROOT/novopay-platform-accounting-v2/logs/accounting.log}"

fail() { echo "FAIL: $*" >&2; exit 1; }

bash "$ROOT/scripts/bin/novopay-service.sh" ensure accounting ${COMPILE:+--compile}
bash "$ROOT/scripts/bin/agent-ops.sh" before-test dpiBilling accounting

echo "=== DPI cross-EOD replay guard (loan=$LOAN_ACCOUNT_ID job_time=$JOB_TIME) ==="

echo ">>> Pass 1 — full EOD (reset DPI txns allowed)"
bash "$ROOT/scripts/dpic/run_eod_dpi_only.sh"
bash "$ROOT/scripts/dpic/run_dpi_post_eod_verify.sh"

# Purge batch execution only — keep transaction_master (cross-EOD collision surface)
for j in dpiAccrualCalculation dpiAccrualBooking dpiBilling; do
  "${PG[@]}" -v ON_ERROR_STOP=1 -v job_name="$j" -v job_time="$JOB_TIME" \
    -f "$ROOT/scripts/dpic/sql/helpers/purge_batch_job_execution.sql" >/dev/null
done

echo ">>> Pass 2 — replay same job_time WITHOUT reset_dpi_booking (must not 134497)"
export RESET_DPI_BOOKING=0
RUN2_LOG="$LOG_DIR/dpi_cross_eod_replay_pass2.log"
bash "$ROOT/scripts/dpic/run_eod_dpi_only.sh" 2>&1 | tee "$RUN2_LOG"

if grep -qE '134497|ClientReferenceNumberDedup' "$RUN2_LOG" 2>/dev/null; then
  fail "134497 in batch output — client_ref guard broken"
fi
if [[ -f "$ACCT_LOG" ]] && tail -n 400 "$ACCT_LOG" | grep -qE '134497.*dpiBilling|dpiBilling.*134497'; then
  fail "134497 in accounting.log after replay"
fi

# No new legacy alphabetic-only billing refs on this replay pass
LEGACY_CNT="$("${PG[@]}" -t -A -c \
  "SELECT COUNT(*) FROM mfi_accounting.transaction_master
   WHERE client_reference_number LIKE '${LOAN_ACCOUNT_ID}_DPI_BILL_%'
     AND created_on > NOW() - INTERVAL '15 minutes';" 2>/dev/null || echo 0)"
if [[ "${LEGACY_CNT:-0}" -gt 0 ]]; then
  fail "new legacy _DPI_BILL_ client_ref rows after replay (expected numeric millis form)"
fi

bash "$ROOT/scripts/dpic/run_dpi_post_eod_verify.sh"
echo "=== DPI cross-EOD replay guard PASS ==="
