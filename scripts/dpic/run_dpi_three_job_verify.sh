#!/usr/bin/env bash
# QA paste-ready: fixture reset → setup SQL → ntest batch APIs (calc/booking loop + billing).
# All accrual/booking/billing writes via batch jobs only — no dpi_accrual_details INSERTs.
# SEED_CALC_WINDOW stays 0 (see run_eod_dpi_only.sh); setup SQL is go-live / quarantine / grace only.
#
# Usage:
#   bash scripts/dpic/run_dpi_three_job_verify.sh
#   VERIFY_MODE=single_eod bash scripts/dpic/run_dpi_three_job_verify.sh   # one EOD chain (fast)
#   VERIFY_MODE=daily_loop END_DATE=2026-04-20 bash scripts/dpic/run_dpi_three_job_verify.sh
#   SKIP_RESET=1 bash scripts/dpic/run_dpi_three_job_verify.sh             # when reset already ran
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT/scripts/dpic/lib/dpi_fixture_pin.sh"
dpi_use_fixture_loan

# shellcheck disable=SC1091
source "$ROOT/scripts/dpic/lib/dpi_demo_fixture.sh"

GO_LIVE_DDMM="${GO_LIVE_DDMM:-15-04-2026}"
GO_LIVE_ISO="${GO_LIVE_ISO:-2026-04-15}"
LOOP_START="${LOOP_START:-2026-05-14}"
END_DATE="${END_DATE:-2026-05-20}"
VERIFY_MODE="${VERIFY_MODE:-single_eod}"
GRACE_DAYS="${GRACE_DAYS:-3}"
SKIP_RESET="${SKIP_RESET:-0}"
SEED_CALC_WINDOW="${SEED_CALC_WINDOW:-0}"
# dpi_demo_fixture defaults JOB_TIME to Jun-27 fixture — wrong for May grace single_eod.
# Use THREE_JOB_TIME to override; else grace job_time for single_eod.
if [[ "${VERIFY_MODE}" == "single_eod" ]]; then
  JOB_TIME="${THREE_JOB_TIME:-$DPI_GRACE_JOB_TIME}"
else
  JOB_TIME="${JOB_TIME:-$DPI_GRACE_JOB_TIME}"
fi

export BATCH_POLL_TIMEOUT_S="${BATCH_POLL_TIMEOUT_S:-120}"

NTEST="$ROOT/scripts/bin/ntest.sh"
WAIT_BATCH="$ROOT/scripts/dpic/lib/wait_batch_job.sh"

fail() { echo "FAIL: $*" >&2; exit 1; }

qa_fire_batch() {
  local api="$1" job_time="$2" purge="${3:-1}"
  local rs
  [[ "$purge" == "1" ]] && dpi_purge_batch "$api" "$job_time"
  rs="$(date +%s)"
  echo ""
  echo "# --- QA copy-paste (${api}) ---"
  echo "JOB_TIME=$job_time bash scripts/bin/ntest.sh api accounting $api --batch --job-time $job_time"
  echo "bash scripts/dpic/lib/wait_batch_job.sh $api $job_time $rs"
  echo "# ---"
  JOB_TIME="$job_time" "$NTEST" api accounting "$api" --batch --job-time "$job_time" >/dev/null
  bash "$WAIT_BATCH" "$api" "$job_time" "$rs"
  dpi_print_batch_execution "$api" "$job_time" "$rs"
}

dpi_print_batch_execution() {
  local api="$1" job_time="$2" run_started="$3"
  dpi_pg -c "
SELECT bje.job_execution_id, bji.job_name, bje.status, bje.create_time
FROM mfi_batch.batch_job_execution bje
JOIN mfi_batch.batch_job_instance bji ON bji.job_instance_id = bje.job_instance_id
JOIN mfi_batch.batch_job_execution_params p ON p.job_execution_id = bje.job_execution_id
WHERE bji.job_name = '$api'
  AND p.parameter_name IN ('job_time', 'time')
  AND p.parameter_value LIKE '%' || '$job_time' || '%'
  AND EXTRACT(EPOCH FROM bje.create_time)::bigint >= $run_started
ORDER BY bje.job_execution_id DESC
LIMIT 1;
"
}

echo "=== DPI three-job verify (QA batch API path) ==="
echo "    loan=$LOAN_ACCOUNT_ID LAN=$ACCOUNT_NUMBER mode=$VERIFY_MODE"
echo "    go_live=$GO_LIVE_ISO end=$END_DATE job_time_default=$JOB_TIME SEED_CALC_WINDOW=$SEED_CALC_WINDOW"

[[ "$SEED_CALC_WINDOW" == "0" ]] || fail "SEED_CALC_WINDOW=1 is a documented bypass — not allowed in this harness"

bash "$ROOT/scripts/bin/agent-ops.sh" before-test dpiAccrualCalculation accounting
dpi_ensure_accounting ${COMPILE:+--compile}
dpi_ensure_masterdata

if [[ "$SKIP_RESET" != "1" ]]; then
  echo ">>> fixture reset (reset_dpi_fixtures.sh — all canonical LANs)"
  bash "$ROOT/scripts/dpic/reset_dpi_fixtures.sh"
else
  echo ">>> SKIP_RESET=1 — per-loan DPI wipe + booking replay reset only"
  dpi_pg -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" \
    -f "$ROOT/scripts/dpic/sql/helpers/purge_dpi_accruals_for_loan.sql" >/dev/null
  dpi_pg -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" \
    -f "$ROOT/scripts/dpic/sql/helpers/reset_dpi_booking_replay.sql" >/dev/null
fi

read -r product_code <<<"$(
  dpi_pg -t -A -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" <<'SQL'
SELECT COALESCE(p.code, 'JLGDL')
FROM mfi_accounting.loan_account la
JOIN mfi_accounting.loan_product lp ON lp.id = la.loan_product_id
LEFT JOIN mfi_accounting.product p ON p.id = lp.product_id AND p.is_deleted = false
WHERE la.account_id = :loan_account_id::bigint;
SQL
)"

dpi_set_go_live_and_refresh "$GO_LIVE_DDMM" "$product_code"
dpi_pg -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" -v grace_days="$GRACE_DAYS" \
  -f "$ROOT/scripts/dpic/sql/helpers/setup_grace_dpi_e2e.sql" >/dev/null
dpi_pg -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" \
  -f "$ROOT/scripts/dpic/sql/helpers/setup_multi_emi_dpi_e2e.sql" >/dev/null
dpi_pg -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" \
  -f "$ROOT/scripts/dpic/sql/helpers/quarantine_dpd_portfolio.sql" >/dev/null

if [[ "$VERIFY_MODE" == "single_eod" ]]; then
  ms="$JOB_TIME"
  dpi_pg -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" -v business_date_ms="$ms" \
    -f "$ROOT/scripts/dpic/sql/helpers/sync_demo_past_due.sql" >/dev/null
  echo ">>> single EOD chain at job_time=$ms"
  qa_fire_batch dpiAccrualCalculation "$ms"
  qa_fire_batch dpiAccrualBooking "$ms"
  qa_fire_batch dpiBilling "$ms"
  proof_date="$(
    python3 - "$ms" <<'PY'
import sys
from datetime import datetime, timezone, timedelta
ist = timezone(timedelta(hours=5, minutes=30))
print(datetime.fromtimestamp(int(sys.argv[1]) / 1000, tz=ist).date())
PY
  )"
else
  CALENDAR_DAYS="$(
    python3 - "$LOOP_START" "$END_DATE" <<'PY'
import sys
from datetime import datetime, timedelta
start = datetime.strptime(sys.argv[1], "%Y-%m-%d").date()
end = datetime.strptime(sys.argv[2], "%Y-%m-%d").date()
d = start
while d <= end:
    print(d.isoformat())
    d += timedelta(days=1)
PY
  )"
  echo ">>> daily dpiAccrualCalculation + dpiAccrualBooking ($LOOP_START .. $END_DATE)"
  while IFS= read -r day; do
    [[ -n "$day" ]] || continue
    ms="$(dpi_date_to_ms "$day")"
    dpi_pg -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" -v business_date_ms="$ms" \
      -f "$ROOT/scripts/dpic/sql/helpers/sync_demo_past_due.sql" >/dev/null
    echo "    EOD $day (job_time=$ms)"
    qa_fire_batch dpiAccrualCalculation "$ms"
    qa_fire_batch dpiAccrualBooking "$ms"
  done <<<"$CALENDAR_DAYS"
  final_ms="$(dpi_date_to_ms "$END_DATE")"
  echo ">>> dpiBilling at END_DATE=$END_DATE job_time=$final_ms"
  qa_fire_batch dpiBilling "$final_ms"
  proof_date="$END_DATE"
fi

read -r accrual_rows posted_rows <<<"$(
  dpi_pg -t -A -F' ' -c "
SELECT COUNT(*) FILTER (WHERE total_accrued_amount > 0),
       COUNT(*) FILTER (WHERE accrual_posting_date IS NOT NULL AND total_accrued_amount > 0)
FROM mfi_accounting.dpi_accrual_details
WHERE loan_account_id = $LOAN_ACCOUNT_ID AND is_deleted = false;
"
)"
[[ "${accrual_rows:-0}" -gt 0 ]] || fail "no accrual rows after batch jobs — calc did not produce output"

echo ""
echo "=== slice integrity (business_date=$proof_date) ==="
read -r slice_viol slice_rules <<<"$(
  dpi_pg -t -A -F' ' -v ON_ERROR_STOP=1 \
    -v loan_account_id="$LOAN_ACCOUNT_ID" \
    -v business_date="$proof_date" \
    -f "$ROOT/scripts/dpic/sql/helpers/verify_dpi_accrual_slice_integrity.sql" 2>/dev/null | head -1
)"
[[ "${slice_viol:-1}" == "0" ]] || fail "slice violations=$slice_viol rules=${slice_rules:-?}"

echo ""
bash "$ROOT/scripts/dpic/lib/run_dpi_column_audit.sh" "$LOAN_ACCOUNT_ID" "$proof_date"

echo ""
echo "=== job-generated DPI state (read-only proof) ==="
dpi_pg -c "
SELECT start_date::date, end_date::date, total_accrued_amount,
       accrual_posting_date::date AS posted
FROM mfi_accounting.dpi_accrual_details
WHERE loan_account_id = $LOAN_ACCOUNT_ID AND is_deleted = false AND total_accrued_amount > 0
ORDER BY end_date
LIMIT 12;
"

echo ""
echo "PASS: three-job verify loan=$LOAN_ACCOUNT_ID accrual_rows=$accrual_rows posted=$posted_rows slice=0 column_audit=0 mode=$VERIFY_MODE"
