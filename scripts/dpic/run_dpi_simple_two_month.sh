#!/usr/bin/env bash
# Purge all local DPI data + backup tables, set one LAN with 2 overdue EMIs, run DPI jobs daily.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT/scripts/dpic/lib/dpi_demo_fixture.sh"

LOAN_ACCOUNT_ID="${LOAN_ACCOUNT_ID:-8060160}"
ACCOUNT_NUMBER="${ACCOUNT_NUMBER:-6004044425}"
GO_LIVE_DDMM="${GO_LIVE_DDMM:-15-03-2026}"
GO_LIVE_ISO="${GO_LIVE_ISO:-2026-03-15}"
END_DATE="${END_DATE:-2026-06-02}"
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

echo "=== Step 1: remove 20k synthetic perf loans (if any) ==="
if dpi_pg -t -A -c "SELECT to_regclass('mfi_accounting._dpi_synthetic_loan_map')" | grep -q _dpi_synthetic; then
  cnt="$(dpi_pg -t -A -c "SELECT COUNT(*) FROM mfi_accounting._dpi_synthetic_loan_map" 2>/dev/null || echo 0)"
  if [[ "${cnt:-0}" -gt 0 ]]; then
    dpi_pg -v ON_ERROR_STOP=1 -f "$ROOT/scripts/dpic/sql/helpers/restore_dpi_synthetic_10k_portfolio.sql"
  fi
fi

echo "=== Step 2: purge ALL DPI accruals / dues / GL txns ==="
dpi_pg -v ON_ERROR_STOP=1 -f "$ROOT/scripts/dpic/sql/helpers/purge_local_dpi_all.sql"

echo "=== Step 3: drop agent backup tables ==="
dpi_pg -v ON_ERROR_STOP=1 -f "$ROOT/scripts/dpic/sql/helpers/drop_local_dpi_backup_tables.sql"

echo "=== Step 4: simple 2-EMI overdue fixture LAN=$ACCOUNT_NUMBER id=$LOAN_ACCOUNT_ID ==="
dpi_pg -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" -v grace_days="$GRACE_DAYS" \
  -f "$ROOT/scripts/dpic/sql/helpers/setup_simple_two_month_overdue.sql"

read -r product_code <<<"$(
  dpi_pg -t -A -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" <<'SQL'
SELECT COALESCE(p.code, 'JLGDL')
FROM mfi_accounting.loan_account la
JOIN mfi_accounting.loan_product lp ON lp.id = la.loan_product_id
LEFT JOIN mfi_accounting.product p ON p.id = lp.product_id AND p.is_deleted = false
WHERE la.account_id = :loan_account_id::bigint;
SQL
)"

dpi_pg -v ON_ERROR_STOP=1 -v go_live_value="$GO_LIVE_DDMM" -v go_live_sub_type="$product_code" \
  -f "$ROOT/scripts/dpic/sql/helpers/upsert_dpi_go_live.sql" >/dev/null
dpi_evict_go_live_cache "$product_code"
dpi_restart_masterdata
dpi_ensure_accounting ${COMPILE:+--compile}

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

echo "=== Step 5: daily DPI calc + booking $GO_LIVE_ISO .. $END_DATE ==="
while IFS= read -r day; do
  [[ -n "$day" ]] || continue
  ms="$(date_to_ms "$day")"
  dpi_pg -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" -v business_date_ms="$ms" \
    -f "$ROOT/scripts/dpic/sql/helpers/sync_demo_past_due.sql" >/dev/null
  echo "    EOD $day"
  call_batch dpiAccrualCalculation "$ms"
  call_batch dpiAccrualBooking "$ms"
done <<<"$CALENDAR_DAYS"

FINAL_MS="$(date_to_ms "$END_DATE")"
echo "=== Step 6: billing on $END_DATE ==="
call_batch dpiBilling "$FINAL_MS"

echo ""
echo "=== VERIFY LAN $ACCOUNT_NUMBER (loan_account_id=$LOAN_ACCOUNT_ID) ==="
dpi_pg -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" \
  -f "$ROOT/scripts/dpic/sql/helpers/verify_dpi_amount_parity.sql"
dpi_pg -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" -v business_date="$END_DATE" \
  -f "$ROOT/scripts/dpic/sql/helpers/verify_dpi_posting_calendar.sql"
dpi_pg -c "
SELECT end_date::date, total_accrued_amount,
       accrual_posting_date::date AS posted_on,
       billing_posting_date::date AS billed_on
FROM mfi_accounting.dpi_accrual_details
WHERE loan_account_id = $LOAN_ACCOUNT_ID AND is_deleted = false AND total_accrued_amount > 0
ORDER BY end_date;
"
dpi_pg -c "
SELECT due_date::date, due_amount, paid_amount
FROM mfi_accounting.loan_due_details
WHERE loan_account_id = $LOAN_ACCOUNT_ID AND component_type = 'DPI' AND is_deleted = false
ORDER BY due_date;
"

read -r unposted posted closed <<<"$(
  dpi_pg -t -A -F' ' -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" -v business_date="$END_DATE" \
    -f "$ROOT/scripts/dpic/sql/helpers/verify_dpi_posting_calendar.sql" | tail -1
)"
[[ "${unposted:-1}" == "0" ]] || fail "unposted closed slices=$unposted"

echo ""
echo "PASS: simple 2-month overdue DPI on LAN $ACCOUNT_NUMBER through $END_DATE"
