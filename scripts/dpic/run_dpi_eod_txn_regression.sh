#!/usr/bin/env bash
# DPI EOD txn regression — all batch GL catalogues (regular + NPA), platform month-end job_time,
# 2nd-of-month EMI (QA1 SDCP-10497 class), and transaction_partition_details on billing.
#
# Catches: month-end booking skipped when job_time=Jul-1 IST but slice ends Jun-30;
#          billing_posting_date without transaction_master / wrong catalogue / missing partitions.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT/scripts/dpic/lib/dpi_demo_fixture.sh"

LOAN_ACCOUNT_ID="${LOAN_ACCOUNT_ID:-8060160}"
GO_LIVE_DDMM="${GO_LIVE_DDMM:-01-04-2026}"
GO_LIVE_ISO="${GO_LIVE_ISO:-2026-04-01}"
CALC_END_DATE="${CALC_END_DATE:-2026-07-01}"
SLICE_END_MONTH="${SLICE_END_MONTH:-2026-06-30}"
# Platform EOD: Jun-30 business close → job_time Jul-1 00:00 IST (not May-31 midnight replay).
MONTH_END_JOB_TIME="${MONTH_END_JOB_TIME:-1782844200000}"
NEXT_EMI_JOB_TIME="${NEXT_EMI_JOB_TIME:-1782930600000}"
NTEST="$ROOT/scripts/bin/ntest.sh"
WAIT_BATCH="$ROOT/scripts/dpic/lib/wait_batch_job.sh"
VERIFY_TXN="$ROOT/scripts/dpic/lib/verify_dpi_eod_txn_chain.sh"

fail() { echo "FAIL: $*" >&2; exit 1; }

date_to_ms() {
  python3 - "$1" <<'PY'
import sys
from datetime import datetime, timezone, timedelta
d = datetime.strptime(sys.argv[1], "%Y-%m-%d")
ist = timezone(timedelta(hours=5, minutes=30))
print(int(d.replace(tzinfo=ist).timestamp() * 1000))
PY
}

purge_batch() {
  dpi_pg -v ON_ERROR_STOP=1 -v job_name="$1" -v job_time="$2" \
    -f "$ROOT/scripts/dpic/sql/helpers/purge_batch_job_execution.sql" >/dev/null
}

call_batch() {
  local api="$1" job_time="$2"
  local before
  purge_batch "$api" "$job_time"
  before="$(dpi_pg -t -A -c "
SELECT COALESCE(MAX(bje.job_execution_id), 0)
FROM mfi_batch.batch_job_execution bje
JOIN mfi_batch.batch_job_instance bji ON bji.job_instance_id = bje.job_instance_id
WHERE bji.job_name = '$api'")"
  JOB_TIME="$job_time" "$NTEST" api accounting "$api" --batch --job-time "$job_time" >/dev/null
  BATCH_WAIT_ARG3=before bash "$WAIT_BATCH" "$api" "$job_time" "$before"
}

prepare_base() {
  local fixture_sql="$1"
  dpi_ensure_accounting
  dpi_ensure_masterdata

  read -r product_code <<<"$(
    dpi_pg -t -A -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" <<'SQL'
SELECT COALESCE(p.code, 'JLGDL')
FROM mfi_accounting.loan_account la
JOIN mfi_accounting.loan_product lp ON lp.id = la.loan_product_id
LEFT JOIN mfi_accounting.product p ON p.id = lp.product_id AND p.is_deleted = false
WHERE la.account_id = :loan_account_id::bigint;
SQL
  )"

  dpi_pg -v ON_ERROR_STOP=1 \
    -v go_live_value="$GO_LIVE_DDMM" \
    -v go_live_sub_type="$product_code" \
    -f "$ROOT/scripts/dpic/sql/helpers/upsert_dpi_go_live.sql" >/dev/null
  dpi_evict_go_live_cache "$product_code"
  dpi_restart_masterdata
  bash "$ROOT/scripts/bin/novopay-service.sh" ensure accounting ${COMPILE:+--compile}

  dpi_pg -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" -v grace_days="${GRACE_DAYS:-3}" \
    -f "$ROOT/scripts/dpic/sql/helpers/setup_grace_dpi_e2e.sql" >/dev/null
  dpi_pg -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" \
    -f "$ROOT/scripts/dpic/sql/helpers/setup_multi_emi_dpi_e2e.sql" >/dev/null
  dpi_pg -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" \
    -f "$ROOT/scripts/dpic/sql/helpers/quarantine_dpd_portfolio.sql" >/dev/null
  dpi_pg -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" \
    -f "$fixture_sql" >/dev/null

  local calc_ms
  calc_ms="$(date_to_ms "$CALC_END_DATE")"
  dpi_pg -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" -v business_date_ms="$calc_ms" \
    -f "$ROOT/scripts/dpic/sql/helpers/sync_demo_past_due.sql" >/dev/null
  dpi_pg -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" \
    -f "$ROOT/scripts/dpic/sql/helpers/purge_dpi_accruals_for_loan.sql" >/dev/null
  dpi_pg -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" \
    -f "$ROOT/scripts/dpic/sql/helpers/reset_dpi_booking_replay.sql" >/dev/null

  echo ">>> dpiAccrualCalculation through $CALC_END_DATE"
  call_batch dpiAccrualCalculation "$calc_ms"
}

run_phase() {
  local label="$1" fixture_sql="$2" accrual_cat="$3" billing_cat="$4"

  echo ""
  echo "=== Phase: $label (accrual_cat=$accrual_cat billing_cat=$billing_cat) ==="
  prepare_base "$fixture_sql"

  echo ">>> dpiAccrualBooking ONLY month-end job_time=$MONTH_END_JOB_TIME (Jun-30 close / Jul-1 IST)"
  call_batch dpiAccrualBooking "$MONTH_END_JOB_TIME"
  bash "$VERIFY_TXN" "$LOAN_ACCOUNT_ID" "$SLICE_END_MONTH" "2026-07-01"

  echo ">>> dpiAccrualBooking next-EMI job_time=$NEXT_EMI_JOB_TIME (Jul-2 for 2nd-of-month EMI)"
  call_batch dpiAccrualBooking "$NEXT_EMI_JOB_TIME"

  echo ">>> dpiBilling next-EMI job_time=$NEXT_EMI_JOB_TIME"
  call_batch dpiBilling "$NEXT_EMI_JOB_TIME"
  bash "$VERIFY_TXN" "$LOAN_ACCOUNT_ID" "" "2026-07-02"

  read -r booked billed <<<"$(
    dpi_pg -t -A -F' ' -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" \
      -f "$ROOT/scripts/dpic/sql/helpers/verify_dpi_post_eod.sql" | tail -1 | awk '{print $3, $4}'
  )"
  [[ "${booked:-0}" -gt 0 ]] || fail "$label: expected booked_rows > 0"
  [[ "${billed:-0}" -gt 0 ]] || fail "$label: expected billed_rows > 0"

  bash "$ROOT/scripts/dpic/run_dpi_billing_ud_verify.sh" || fail "$label: billing UD verify"
  echo "PASS: $label"
}

echo "=== DPI EOD txn regression loan=$LOAN_ACCOUNT_ID ==="

run_phase "REGULAR" \
  "$ROOT/scripts/dpic/sql/helpers/setup_qa1_month_end_regular_fixture.sql" \
  1327 1330

run_phase "NPA" \
  "$ROOT/scripts/dpic/sql/helpers/setup_qa1_month_end_npa_fixture.sql" \
  1328 1329

echo ""
echo "=== DPI EOD txn regression PASS (regular 1327/1330 + NPA 1328/1329) ==="
