#!/usr/bin/env bash
# Seed N DPI-eligible loans and run dpiAccrualCalculation only (no booking/billing).
# Local perf scenarios: chunk50, chunk100, chunk200, chunk500.
#
# Usage:
#   ./scripts/dpic/run_dpi_batch_perf.sh              # default 50 loans
#   ./scripts/dpic/run_dpi_batch_perf.sh 100
#   SCENARIO=chunk200 ./scripts/dpic/run_dpi_batch_perf.sh
#   RESTORE=1 ./scripts/dpic/run_dpi_batch_perf.sh    # restore only
#
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PG=(psql -h "${YB_HOST:-127.0.0.1}" -p "${YB_PORT:-5433}" -U "${YB_USER:-yugabyte}" -d "${YB_DB:-yugabyte}")
export PGPASSWORD="${PGPASSWORD:-yugabyte}"
NTEST="$ROOT/scripts/bin/ntest.sh"
WAIT_BATCH="$ROOT/scripts/dpic/lib/wait_batch_job.sh"
JOB_TIME="${JOB_TIME:-1781699400000}"
PRODUCT_SCHEME_ID="${PRODUCT_SCHEME_ID:-48}"
PAST_DUE_DAYS="${PAST_DUE_DAYS:-45}"
CLEAR_ACCRUALS="${CLEAR_ACCRUALS:-1}"
COMPILE="${COMPILE:-0}"

case "${SCENARIO:-}" in
  chunk50)  TARGET_COUNT=50 ;;
  chunk100) TARGET_COUNT=100 ;;
  chunk200) TARGET_COUNT=200 ;;
  chunk500) TARGET_COUNT=500 ;;
  *)        TARGET_COUNT="${1:-50}" ;;
esac

if [[ "${RESTORE:-0}" == "1" ]]; then
  echo ">>> Restore DPI perf portfolio"
  "${PG[@]}" -v ON_ERROR_STOP=1 -f "$ROOT/scripts/dpic/sql/helpers/restore_dpi_batch_perf_portfolio.sql"
  exit 0
fi

echo "=== DPI accrual calc perf — target_count=${TARGET_COUNT} scheme=${PRODUCT_SCHEME_ID} job_time=${JOB_TIME} ==="

bash "$ROOT/scripts/bin/novopay-service.sh" ensure accounting ${COMPILE:+--compile}

echo ">>> Seed perf portfolio (target_count=${TARGET_COUNT})"
"${PG[@]}" -v ON_ERROR_STOP=1 \
  -v product_scheme_id="$PRODUCT_SCHEME_ID" \
  -v target_count="$TARGET_COUNT" \
  -v past_due_days="$PAST_DUE_DAYS" \
  -v clear_accruals="$CLEAR_ACCRUALS" \
  -f "$ROOT/scripts/dpic/sql/helpers/seed_dpi_batch_perf_portfolio.sql"

run_started="$(date +%s)"
"${PG[@]}" -v ON_ERROR_STOP=1 -v job_name=dpiAccrualCalculation -v job_time="$JOB_TIME" \
  -f "$ROOT/scripts/dpic/sql/helpers/purge_batch_job_execution.sql" >/dev/null

echo ">>> Run dpiAccrualCalculation"
JOB_TIME="$JOB_TIME" "$NTEST" api accounting dpiAccrualCalculation --batch --job-time "$JOB_TIME" >/dev/null
bash "$WAIT_BATCH" dpiAccrualCalculation "$JOB_TIME" "$run_started"

echo ">>> Step metrics"
"${PG[@]}" -v ON_ERROR_STOP=1 \
  -v job_name=dpiAccrualCalculation \
  -v job_time="$JOB_TIME" \
  -v run_started="$run_started" \
  -f "$ROOT/scripts/dpic/sql/helpers/batch_step_metrics.sql"

echo ""
echo "Restore when done: RESTORE=1 $0"
echo "Other scenarios: SCENARIO=chunk100|chunk200|chunk500 $0"
