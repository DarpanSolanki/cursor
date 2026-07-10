#!/usr/bin/env bash
# Fresh LAN DPI grace gate E2E — disburse + setup_grace + daily calc/booking/billing.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT/scripts/dpic/lib/dpi_demo_fixture.sh"

ANCHOR_DATE="${ANCHOR_DATE:-2026-06-15}"
GRACE_DAYS="${GRACE_DAYS:-3}"
export BATCH_POLL_TIMEOUT_S="${BATCH_POLL_TIMEOUT_S:-180}"
TAG="${1:-multi_overdue}"

bash "$ROOT/scripts/bin/novopay-service.sh" ensure accounting ${COMPILE:+--compile}

if [[ "${USE_EXISTING_LOAN:-0}" == "1" && -n "${LOAN_ACCOUNT_ID:-}" ]]; then
  echo ">>> Reusing loan_account_id=$LOAN_ACCOUNT_ID"
else
  # shellcheck disable=SC1091
  source "$ROOT/scripts/dpic/lib/disburse_fresh_dpi_loan.sh" "$TAG"
fi

echo "=== FRESH LAN loan=$LOAN_ACCOUNT_ID lan=$LAN tag=$TAG ==="

dpi_pg -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" -v grace_days="$GRACE_DAYS" \
  -f "$ROOT/scripts/dpic/sql/helpers/setup_grace_dpi_e2e.sql"
dpi_pg -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" \
  -f "$ROOT/scripts/dpic/sql/helpers/setup_multi_emi_dpi_e2e.sql"
dpi_pg -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" \
  -f "$ROOT/scripts/dpic/sql/helpers/quarantine_dpd_portfolio.sql" >/dev/null
dpi_pg -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" \
  -f "$ROOT/scripts/dpic/sql/helpers/purge_dpi_accruals_for_loan.sql" >/dev/null

product_code="$(dpi_pg -t -A -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" <<'SQL'
SELECT COALESCE(p.code, '6367') FROM mfi_accounting.loan_account la
JOIN mfi_accounting.loan_product lp ON lp.id = la.loan_product_id
LEFT JOIN mfi_accounting.product p ON p.id = lp.product_id AND p.is_deleted = false
WHERE la.account_id = :loan_account_id::bigint;
SQL
)"
dpi_set_go_live_and_refresh "15-04-2025" "$product_code"
dpi_ensure_accounting ${COMPILE:+--compile}

eval "$(LOAN_ACCOUNT_ID="$LOAN_ACCOUNT_ID" GRACE_DAYS="$GRACE_DAYS" python3 "$ROOT/scripts/dpic/lib/job_times_from_loan.py")"
echo "SINGLE_OVERDUE_JOB_MS=$SINGLE_OVERDUE_JOB_MS MULTI_OVERDUE_JOB_MS=$MULTI_OVERDUE_JOB_MS"

echo "=== EMI schedule (due / overdue) ==="
dpi_pg -c "
SELECT lid.serial_number, ldd.component_type, ldd.due_date::date, ldd.overdue_date::date,
       (ldd.due_amount-ldd.paid_amount-ldd.waived_amount) AS outstanding
FROM mfi_accounting.loan_installment_details lid
JOIN mfi_accounting.loan_due_details ldd ON ldd.loan_installment_details_id=lid.id AND ldd.is_deleted=false
WHERE lid.loan_account_id=$LOAN_ACCOUNT_ID AND ldd.component_type='INT'
ORDER BY ldd.due_date LIMIT 4;"

END_MS="$MULTI_OVERDUE_JOB_MS"
# Multi-EMI proof needs EMI2 accrual through month-end seal, not only EMI2 overdue day.
if [[ "$TAG" == "multi_overdue" ]]; then
  END_MS="$(python3 - "$MULTI_OVERDUE_JOB_MS" <<'PY'
import sys
from datetime import datetime
from zoneinfo import ZoneInfo
IST = ZoneInfo("Asia/Kolkata")
end = datetime.fromtimestamp(int(sys.argv[1])/1000, IST).date()
month_end = end.replace(day=1)
if month_end.month == 12:
    month_end = month_end.replace(year=month_end.year + 1, month=1, day=1)
else:
    month_end = month_end.replace(month=month_end.month + 1, day=1)
from datetime import timedelta
month_end = month_end - timedelta(days=1)
ms = int(datetime(month_end.year, month_end.month, month_end.day, 18, 0, 0, tzinfo=IST).timestamp() * 1000)
print(ms)
PY
)"
fi
python3 - "$END_MS" <<'PY' | while read -r ms; do
import os, sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
IST = ZoneInfo("Asia/Kolkata")
end = datetime.fromtimestamp(int(sys.argv[1])/1000, IST).date()
start = datetime.strptime("2026-04-15", "%Y-%m-%d").date()
d = start
while d <= end:
    ms = int(datetime(d.year,d.month,d.day,18,0,0,tzinfo=IST).timestamp()*1000)
    print(ms)
    d += timedelta(days=1)
PY
  [[ -n "$ms" ]] || continue
  day="$(python3 - "$ms" <<'P'
import sys
from datetime import datetime
from zoneinfo import ZoneInfo
d=datetime.fromtimestamp(int(sys.argv[1])/1000, ZoneInfo("Asia/Kolkata"))
print(d.strftime("%Y-%m-%d"))
P
)"
  echo ">>> EOD $day"
  dpi_pg -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" -v business_date_ms="$ms" \
    -f "$ROOT/scripts/dpic/sql/helpers/sync_demo_past_due.sql" >/dev/null
  dpi_call_batch dpiAccrualCalculation "$ms"
  dpi_call_batch dpiAccrualBooking "$ms"
done

BIZ="$(python3 - "$END_MS" <<'P'
import sys
from datetime import datetime
from zoneinfo import ZoneInfo
print(datetime.fromtimestamp(int(sys.argv[1])/1000, ZoneInfo("Asia/Kolkata")).strftime("%Y-%m-%d"))
P
)"

echo "=== accrual rows ==="
dpi_pg -c "
SELECT installment_id, start_date::date, end_date::date, total_accrued_amount, accrual_posting_date::date
FROM mfi_accounting.dpi_accrual_details
WHERE loan_account_id=$LOAN_ACCOUNT_ID AND is_deleted=false AND total_accrued_amount>0
ORDER BY end_date;"

echo "=== multi-EMI verify ==="
verify_out="$(dpi_pg -v ON_ERROR_STOP=1 -t -A -F'|' -v loan_account_id="$LOAN_ACCOUNT_ID" \
  -f "$ROOT/scripts/dpic/sql/helpers/verify_multi_emi_installment_dpi_e2e.sql" | tail -1)"
echo "$verify_out"
IFS='|' read -r emi1 emi2 r1 r2 latest <<<"$verify_out"
[[ "${r1:-0}" -gt 0 && "${r2:-0}" -gt 0 ]] || { echo "FAIL multi-EMI rows emi1=$r1 emi2=$r2"; exit 1; }

bash "$ROOT/scripts/dpic/lib/run_dpi_column_audit.sh" "$LOAN_ACCOUNT_ID" "$BIZ"

echo "PASS fresh_dpi_grace_e2e loan=$LOAN_ACCOUNT_ID lan=$LAN biz=$BIZ"
