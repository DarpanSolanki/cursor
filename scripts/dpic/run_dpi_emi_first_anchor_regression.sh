#!/usr/bin/env bash
# Regression: EMI due on 1st — month-end (Jun-30) accrual must not drop (anchor segStart fix a8f822cf0).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT/scripts/dpic/lib/dpi_demo_fixture.sh"

LOAN_ACCOUNT_ID="${LOAN_ACCOUNT_ID:-8060160}"
GO_LIVE_DDMM="${GO_LIVE_DDMM:-15-04-2026}"
GO_LIVE_ISO="${GO_LIVE_ISO:-2026-04-15}"
END_DATE="${END_DATE:-2026-07-01}"
GRACE_DAYS="${GRACE_DAYS:-3}"
NTEST="$ROOT/scripts/bin/ntest.sh"
WAIT_BATCH="$ROOT/scripts/dpic/lib/wait_batch_job.sh"

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
  purge_batch "$api" "$job_time"
  local rs
  rs="$(date +%s)"
  JOB_TIME="$job_time" "$NTEST" api accounting "$api" --batch --job-time "$job_time" >/dev/null
  bash "$WAIT_BATCH" "$api" "$job_time" "$rs"
}

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

echo "=== DPI EMI-1st month-end anchor regression loan=$LOAN_ACCOUNT_ID end=$END_DATE ==="

dpi_pg -v ON_ERROR_STOP=1 -v go_live_value="$GO_LIVE_DDMM" -v go_live_sub_type="$product_code" \
  -f "$ROOT/scripts/dpic/sql/helpers/upsert_dpi_go_live.sql" >/dev/null
dpi_evict_go_live_cache "$product_code"
dpi_restart_masterdata
bash "$ROOT/scripts/bin/novopay-service.sh" ensure accounting ${COMPILE:+--compile}

dpi_pg -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" -v grace_days="$GRACE_DAYS" \
  -f "$ROOT/scripts/dpic/sql/helpers/setup_grace_dpi_e2e.sql" >/dev/null
dpi_pg -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" \
  -f "$ROOT/scripts/dpic/sql/helpers/setup_multi_emi_dpi_e2e.sql" >/dev/null
dpi_pg -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" \
  -f "$ROOT/scripts/dpic/sql/helpers/setup_emi_first_of_month_fixture.sql" >/dev/null
dpi_pg -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" \
  -f "$ROOT/scripts/dpic/sql/helpers/quarantine_dpd_portfolio.sql" >/dev/null
dpi_pg -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" \
  -f "$ROOT/scripts/dpic/sql/helpers/purge_dpi_accruals_for_loan.sql" >/dev/null
dpi_pg -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" \
  -f "$ROOT/scripts/dpic/sql/helpers/reset_dpi_booking_replay.sql" >/dev/null

CALENDAR_DAYS="$(
  python3 - "$GO_LIVE_ISO" "$END_DATE" <<'PY'
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

while IFS= read -r day; do
  [[ -n "$day" ]] || continue
  ms="$(date_to_ms "$day")"
  dpi_pg -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" -v business_date_ms="$ms" \
    -f "$ROOT/scripts/dpic/sql/helpers/sync_demo_past_due.sql" >/dev/null
  call_batch dpiAccrualCalculation "$ms"
  call_batch dpiAccrualBooking "$ms"
done <<<"$CALENDAR_DAYS"

read -r slice_count month_accrued <<<"$(
  dpi_pg -t -A -F' ' -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" \
    -f "$ROOT/scripts/dpic/sql/helpers/verify_dpi_emi_first_month_end_accrual.sql" | tail -1
)"
[[ "${slice_count:-0}" -gt 0 ]] || fail "no dpi_accrual_details slice ending 2026-06-30"
[[ "$(python3 -c "print(float('${month_accrued:-0}')>0)")" == "True" ]] || fail "Jun-30 month-end accrued=0 (anchor flip bug)"

FINAL_MS="$(date_to_ms "$END_DATE")"
call_batch dpiBilling "$FINAL_MS"

read -r unposted posted closed <<<"$(
  dpi_pg -t -A -F' ' -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" -v business_date="$END_DATE" \
    -f "$ROOT/scripts/dpic/sql/helpers/verify_dpi_posting_calendar.sql" | tail -1
)"
[[ "${unposted:-1}" == "0" ]] || fail "posting gaps unposted=$unposted"

read -r total_acc posted_acc billed_acc gl_posted dpi_due posted_gl billed_due posted_covers <<<"$(
  dpi_pg -t -A -F' ' -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" \
    -f "$ROOT/scripts/dpic/sql/helpers/verify_dpi_amount_parity.sql" | tail -1
)"
[[ "${posted_gl:-f}" == "t" ]] || fail "posted accrued != GL"
[[ "${billed_due:-f}" == "t" ]] || fail "billed accrued != DPI due"

echo "PASS: EMI-1st month-end anchor regression (Jun-30 accrued=$month_accrued posted=$posted_acc due=$dpi_due)"
