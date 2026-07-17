#!/usr/bin/env bash
# Two overdue EMIs: daily dpiAccrualCalculation + dpiAccrualBooking, then dpiBilling.
# Fixture hides EMI3+ so billing fires when EMI2 is due (no future installment blocking).
#
# Assertions: verify_dpi_posting_calendar + verify_dpi_post_eod + verify_dpi_accrual_slice_integrity
# (slice rules: no orphan segments, posting/billing date ordering). DPI due outstanding is summed
# with due_date <= END_DATE (billing may stamp a future anchor due on the billing run day).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT/scripts/dpic/lib/dpi_fixture_constants.sh"
if [[ "${DPI_USE_CUSTOM_LOAN:-0}" != "1" ]]; then
  dpi_use_grace_chain_loan
fi
# shellcheck disable=SC1091
source "$ROOT/scripts/dpic/lib/dpi_demo_fixture.sh"

GO_LIVE_DDMM="${GO_LIVE_DDMM:-15-04-2025}"
GO_LIVE_ISO="${GO_LIVE_ISO:-2026-05-01}"
END_DATE="${END_DATE:-2026-07-01}"
GRACE_DAYS="${GRACE_DAYS:-3}"
# daily = every calendar day (slow); milestones = EMI due + month-end hops (quick profile default)
DPI_CALENDAR_MODE="${DPI_CALENDAR_MODE:-daily}"
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
  dpi_call_batch "$1" "$2"
}

echo "=== DPI two-EMI full chain LAN=$ACCOUNT_NUMBER id=$LOAN_ACCOUNT_ID ==="
echo "    go_live=$GO_LIVE_ISO end=$END_DATE grace=$GRACE_DAYS"

dpi_isolate_loan_for_case "$LOAN_ACCOUNT_ID"
dpi_pg -v ON_ERROR_STOP=1 -f "$ROOT/scripts/dpic/sql/helpers/purge_local_dpi_all.sql" >/dev/null
dpi_pg -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" \
  -f "$ROOT/scripts/dpic/sql/helpers/hard_purge_dpi_accruals_for_loan.sql" >/dev/null

dpi_pg -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" -v grace_days="$GRACE_DAYS" \
  -f "$ROOT/scripts/dpic/sql/helpers/setup_two_emi_dpi_full_chain.sql"

read -r product_code <<<"$(
  dpi_pg -t -A -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" <<'SQL'
SELECT COALESCE(p.code, '7676')
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

if [[ "$DPI_CALENDAR_MODE" == "milestones" || "$DPI_CALENDAR_MODE" == "single" ]]; then
  echo ">>> milestone calc + booking mode=$DPI_CALENDAR_MODE ($GO_LIVE_ISO .. $END_DATE)"
  export ROOT LOAN_ACCOUNT_ID GO_LIVE_ISO END_DATE NTEST WAIT_BATCH
  chmod +x "$ROOT/scripts/dpic/lib/dpi_run_milestone_eod.sh"
  bash "$ROOT/scripts/dpic/lib/dpi_run_milestone_eod.sh" "$DPI_CALENDAR_MODE" "$GO_LIVE_ISO" "$END_DATE"
else
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

  echo ">>> daily calc + booking $GO_LIVE_ISO .. $END_DATE"
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
  echo ">>> billing on $END_DATE"
  call_batch dpiBilling "$FINAL_MS"
fi

echo ""
echo "=== accrual slices (posting + billing dates) ==="
dpi_pg -c "
SELECT lid.serial_number, da.start_date::date, da.end_date::date, da.total_accrued_amount,
       da.accrual_posting_date::date AS posted, da.billing_posting_date::date AS billed
FROM mfi_accounting.dpi_accrual_details da
JOIN mfi_accounting.loan_installment_details lid ON lid.id = da.installment_id
WHERE da.loan_account_id = $LOAN_ACCOUNT_ID AND da.is_deleted = false AND da.total_accrued_amount > 0
ORDER BY da.end_date, lid.serial_number;
"

echo ""
echo "=== DPI dues ==="
dpi_pg -c "
SELECT lid.serial_number, ldd.due_date::date, ldd.due_amount, ldd.paid_amount
FROM mfi_accounting.loan_due_details ldd
JOIN mfi_accounting.loan_installment_details lid ON lid.id = ldd.loan_installment_details_id
WHERE ldd.loan_account_id = $LOAN_ACCOUNT_ID AND ldd.component_type = 'DPI' AND ldd.is_deleted = false
ORDER BY ldd.due_date;
"

read -r unposted posted closed <<<"$(
  dpi_pg -t -A -F' ' -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" -v business_date="$END_DATE" \
    -f "$ROOT/scripts/dpic/sql/helpers/verify_dpi_posting_calendar.sql" | tail -1
)"
[[ "${unposted:-1}" -eq 0 ]] || fail "unposted closed slices=$unposted (all closed slices must be posted)"

read -r accrual_rows distinct_inst booked billed _extra <<<"$(
  dpi_pg -t -A -F' ' -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" \
    -f "$ROOT/scripts/dpic/sql/helpers/verify_dpi_post_eod.sql" | tail -1 | awk '{print $1, $2, $3, $4, ""}'
)"
[[ "${accrual_rows:-0}" -ge 2 ]] || fail "expected >=2 accrual rows, got ${accrual_rows:-0}"
[[ "${distinct_inst:-0}" -ge 2 ]] || fail "expected accruals on >=2 EMIs, got distinct_installments=${distinct_inst:-0}"
[[ "${booked:-0}" -gt 0 ]] || fail "expected booked_rows > 0, got ${booked:-0}"
[[ "${billed:-0}" -gt 0 ]] || fail "expected billed_rows > 0, got ${billed:-0}"

read -r slice_violations slice_rules <<<"$(
  dpi_pg -t -A -F' ' -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" -v business_date="$END_DATE" \
    -f "$ROOT/scripts/dpic/sql/helpers/verify_dpi_accrual_slice_integrity.sql" | head -1
)"
[[ "${slice_violations:-0}" -eq 0 ]] || fail "slice integrity violations=$slice_violations rules=${slice_rules:-?}"

echo "=== slice integrity ==="
dpi_pg -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" -v business_date="$END_DATE" \
  -f "$ROOT/scripts/dpic/sql/helpers/verify_dpi_accrual_slice_integrity.sql" | tail -8

read -r billed_amt due_amt <<<"$(
  dpi_pg -t -A -F' ' -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" -v business_date="$END_DATE" <<'SQL'
WITH billed AS (
  SELECT COALESCE(SUM(da.total_accrued_amount), 0) AS amt
  FROM mfi_accounting.dpi_accrual_details da
  WHERE da.loan_account_id = :loan_account_id::bigint
    AND da.is_deleted = false
    AND da.billing_posting_date IS NOT NULL
    AND da.billing_posting_date::date <= :'business_date'::date
),
due AS (
  SELECT COALESCE(SUM(ldd.due_amount - ldd.paid_amount - ldd.waived_amount), 0) AS amt
  FROM mfi_accounting.loan_due_details ldd
  WHERE ldd.loan_account_id = :loan_account_id::bigint
    AND ldd.component_type = 'DPI' AND ldd.is_deleted = false
    AND ldd.due_date::date <= :'business_date'::date
)
SELECT billed.amt::int, due.amt::int FROM billed, due;
SQL
)"
[[ "${billed_amt:-0}" -eq "${due_amt:-0}" ]] || fail "billed accrued ($billed_amt) != DPI due outstanding ($due_amt) as of $END_DATE"
[[ "${billed_amt:-0}" -gt 0 ]] || fail "expected billed DPI > 0 as of $END_DATE"

echo ""
bash "$ROOT/scripts/dpic/lib/run_dpi_column_audit.sh" "$LOAN_ACCOUNT_ID" "$END_DATE" \
  || fail "column audit sealed_unposted/sealed_unbilled after two-EMI chain"

echo ""
echo "PASS: two-EMI DPI full chain on LAN $ACCOUNT_NUMBER through $END_DATE mode=$DPI_CALENDAR_MODE (rows=$accrual_rows EMIs=$distinct_inst booked=$booked billed=$billed billed_due=$billed_amt)"
