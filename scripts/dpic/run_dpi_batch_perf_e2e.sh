#!/usr/bin/env bash
# Honest local DPI batch performance: seed portfolio + optional history bloat + full EOD chain.
#
# Local LAN ceiling ~1990 (ACTIVE loans with overdue PRIN/INT). Use MULTI_SCHEME=1 for max pool.
# Table growth: HISTORY_ROWS_PER_LOAN inserts posted accrual rows (simulates years of history).
#
# Usage:
#   ./scripts/dpic/run_dpi_batch_perf_e2e.sh                    # 1500 LANs, calc only
#   FULL_EOD=1 ./scripts/dpic/run_dpi_batch_perf_e2e.sh         # calc + booking + billing
#   SCENARIO=max FULL_EOD=1 HISTORY_ROWS_PER_LOAN=100 ./scripts/dpic/run_dpi_batch_perf_e2e.sh
#   RESTORE=1 ./scripts/dpic/run_dpi_batch_perf_e2e.sh
#
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PG=(psql -h "${YB_HOST:-127.0.0.1}" -p "${YB_PORT:-5433}" -U "${YB_USER:-yugabyte}" -d "${YB_DB:-yugabyte}")
export PGPASSWORD="${PGPASSWORD:-yugabyte}"
NTEST="$ROOT/scripts/bin/ntest.sh"
WAIT_BATCH="$ROOT/scripts/dpic/lib/wait_batch_job.sh"
REPORT="${REPORT:-$ROOT/scripts/scratch/dpi-batch-perf/report-$(date +%Y%m%d-%H%M%S).txt}"
mkdir -p "$(dirname "$REPORT")"

JOB_TIME="${JOB_TIME:-1781699400000}"
PRODUCT_SCHEME_ID="${PRODUCT_SCHEME_ID:-48}"
MULTI_SCHEME="${MULTI_SCHEME:-1}"
PAST_DUE_DAYS="${PAST_DUE_DAYS:-45}"
CLEAR_ACCRUALS="${CLEAR_ACCRUALS:-1}"
HISTORY_ROWS_PER_LOAN="${HISTORY_ROWS_PER_LOAN:-0}"
FULL_EOD="${FULL_EOD:-0}"
COMPILE="${COMPILE:-0}"
BATCH_POLL_TIMEOUT_S="${BATCH_POLL_TIMEOUT_S:-600}"

case "${SCENARIO:-}" in
  chunk50)    TARGET_COUNT=50 ;;
  chunk100)   TARGET_COUNT=100 ;;
  chunk500)   TARGET_COUNT=500 ;;
  chunk1000)  TARGET_COUNT=1000 ;;
  max|chunk1990) TARGET_COUNT=1990 ;;
  *)          TARGET_COUNT="${1:-1500}" ;;
esac

if [[ "${RESTORE:-0}" == "1" ]]; then
  RESTORE=1 "$ROOT/scripts/dpic/run_dpi_batch_perf.sh"
  exit 0
fi

log() { echo "$@" | tee -a "$REPORT"; }

log "=== DPI batch perf E2E ==="
log "report=$REPORT"
log "target_count=$TARGET_COUNT multi_scheme=$MULTI_SCHEME history_rows_per_loan=$HISTORY_ROWS_PER_LOAN full_eod=$FULL_EOD job_time=$JOB_TIME"
log ""

bash "$ROOT/scripts/bin/novopay-service.sh" ensure accounting ${COMPILE:+--compile}

log ">>> Seed portfolio"
"${PG[@]}" -v ON_ERROR_STOP=1 \
  -v product_scheme_id="$PRODUCT_SCHEME_ID" \
  -v multi_scheme="$MULTI_SCHEME" \
  -v target_count="$TARGET_COUNT" \
  -v past_due_days="$PAST_DUE_DAYS" \
  -v clear_accruals="$CLEAR_ACCRUALS" \
  -f "$ROOT/scripts/dpic/sql/helpers/seed_dpi_batch_perf_portfolio.sql" | tee -a "$REPORT"

if [[ "$HISTORY_ROWS_PER_LOAN" -gt 0 ]]; then
  log ">>> Seed accrual history bloat ($HISTORY_ROWS_PER_LOAN rows/loan)"
  "${PG[@]}" -v ON_ERROR_STOP=1 \
    -v history_rows_per_loan="$HISTORY_ROWS_PER_LOAN" \
    -f "$ROOT/scripts/dpic/sql/helpers/seed_dpi_accrual_history_bloat.sql" | tee -a "$REPORT"
fi

log ""
log ">>> DB snapshot before jobs"
"${PG[@]}" -t -A -c "
SELECT 'eligible_loans=' || COUNT(*)
FROM mfi_accounting.loan_account la
JOIN mfi_accounting.product_scheme_frequency_details psfd
  ON psfd.product_scheme_id = la.la_product_scheme_id
 AND psfd.interest_frequency = la.repayment_frequency AND psfd.is_deleted = false
WHERE la.loan_status = 'ACTIVE' AND la.past_due_days > 0 AND psfd.dpi_applicable = 'YES';
SELECT 'accrual_rows_active=' || COUNT(*) FROM mfi_accounting.dpi_accrual_details WHERE is_deleted = false;
SELECT 'unposted_accrual_rows=' || COUNT(*) FROM mfi_accounting.dpi_accrual_details WHERE is_deleted = false AND accrual_posting_date IS NULL;
" | tee -a "$REPORT"

run_job() {
  local api="$1"
  local run_started
  run_started="$(date +%s)"
  "${PG[@]}" -v ON_ERROR_STOP=1 -v job_name="$api" -v job_time="$JOB_TIME" \
    -f "$ROOT/scripts/dpic/sql/helpers/purge_batch_job_execution.sql" >/dev/null
  log ">>> Run $api (started $(date -Iseconds))"
  JOB_TIME="$JOB_TIME" "$NTEST" api accounting "$api" --batch --job-time "$JOB_TIME" >/dev/null
  BATCH_POLL_TIMEOUT_S="$BATCH_POLL_TIMEOUT_S" bash "$WAIT_BATCH" "$api" "$JOB_TIME" "$run_started" | tee -a "$REPORT"
  log ">>> Metrics $api"
  "${PG[@]}" -v ON_ERROR_STOP=1 \
    -v job_name="$api" -v job_time="$JOB_TIME" -v run_started="$run_started" \
    -f "$ROOT/scripts/dpic/sql/helpers/batch_step_metrics.sql" | tee -a "$REPORT"
  log ""
}

run_job dpiAccrualCalculation
if [[ "$FULL_EOD" == "1" ]]; then
  run_job dpiAccrualBooking
  run_job dpiBilling
fi

log "=== Done. Restore: RESTORE=1 $0 ==="
log "Report: $REPORT"
