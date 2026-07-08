#!/usr/bin/env bash
# UD §5.4: go-live excludes pre-go-live EMI from base; maturity < go-live skips calc;
# accrual booking on EMI due dates (interest-accrual posting pattern).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT/scripts/dpic/lib/dpi_demo_fixture.sh"

LOAN_ACCOUNT_ID="${LOAN_ACCOUNT_ID:-8060160}"
GRACE_DAYS="${GRACE_DAYS:-3}"
JOB_TIME="${JOB_TIME:-1782563400000}"
NTEST="$ROOT/scripts/bin/ntest.sh"
WAIT_BATCH="$ROOT/scripts/dpic/lib/wait_batch_job.sh"

fail() { echo "FAIL: $*" >&2; exit 1; }

dpi_ensure_accounting
dpi_ensure_masterdata

read -r emi1 emi2 product_code maturity_orig <<<"$(
  dpi_pg -t -A -F' ' -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" <<'SQL'
SELECT lid1.installment_date::date,
       lid2.installment_date::date,
       p.code,
       la.maturity_date::date
FROM mfi_accounting.loan_account la
JOIN mfi_accounting.loan_product lp ON lp.id = la.loan_product_id
JOIN mfi_accounting.product p ON p.id = lp.product_id
JOIN mfi_accounting.loan_installment_details lid1
  ON lid1.loan_account_id = la.account_id AND lid1.is_deleted = false
JOIN mfi_accounting.loan_installment_details lid2
  ON lid2.loan_account_id = la.account_id AND lid2.is_deleted = false
 AND lid2.installment_date > lid1.installment_date
WHERE la.account_id = :loan_account_id::bigint
ORDER BY lid1.installment_date, lid2.installment_date
LIMIT 1;
SQL
)"

[[ -n "$emi1" && -n "$emi2" ]] || fail "need 2 installments on loan $LOAN_ACCOUNT_ID"

GO_LIVE_VALUE="$(GO_LIVE_EMI1="$emi1" GO_LIVE_EMI2="$emi2" python3 - <<'PY'
import os
from datetime import date, datetime, timedelta
e1 = date.fromisoformat(os.environ["GO_LIVE_EMI1"])
e2 = date.fromisoformat(os.environ["GO_LIVE_EMI2"])
mid = e1 + (e2 - e1) // 2
print(mid.strftime("%d-%m-%Y"))
print(mid.isoformat())
PY
)"
GO_LIVE_ISO="$(echo "$GO_LIVE_VALUE" | tail -1)"
GO_LIVE_DDMM="$(echo "$GO_LIVE_VALUE" | head -1)"

echo "=== DPI go-live UD E2E loan=$LOAN_ACCOUNT_ID go_live=$GO_LIVE_ISO product=$product_code ==="

dpi_pg -v ON_ERROR_STOP=1 -v go_live_value="$GO_LIVE_DDMM" -v go_live_sub_type="$product_code" \
  -f "$ROOT/scripts/dpic/sql/helpers/upsert_dpi_go_live.sql" >/dev/null

COMPILE=1 bash "$ROOT/scripts/bin/novopay-service.sh" ensure accounting --compile

dpi_pg -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" -v grace_days="$GRACE_DAYS" \
  -f "$ROOT/scripts/dpic/sql/helpers/setup_grace_dpi_e2e.sql" >/dev/null
dpi_pg -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" \
  -f "$ROOT/scripts/dpic/sql/helpers/setup_multi_emi_dpi_e2e.sql" >/dev/null
dpi_pg -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" \
  -f "$ROOT/scripts/dpic/sql/helpers/quarantine_dpd_portfolio.sql" >/dev/null
dpi_pg -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" -v business_date_ms="$JOB_TIME" \
  -f "$ROOT/scripts/dpic/sql/helpers/sync_demo_past_due.sql" >/dev/null

dpi_pg -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" \
  -f "$ROOT/scripts/dpic/sql/helpers/purge_dpi_accruals_for_loan.sql" >/dev/null

purge_batch() {
  dpi_pg -v ON_ERROR_STOP=1 -v job_name="$1" -v job_time="$2" \
    -f "$ROOT/scripts/dpic/sql/helpers/purge_batch_job_execution.sql" >/dev/null
}

AS_ON="$(python3 - "$JOB_TIME" <<'PY'
import sys
from datetime import datetime, timezone, timedelta
ms = int(sys.argv[1])
ist = timezone(timedelta(hours=5, minutes=30))
print(datetime.fromtimestamp(ms / 1000, ist).strftime("%Y-%m-%d"))
PY
)"

echo ">>> dpiAccrualCalculation (go-live base)"
purge_batch dpiAccrualCalculation "$JOB_TIME"
rs="$(date +%s)"
JOB_TIME="$JOB_TIME" "$NTEST" api accounting dpiAccrualCalculation --batch --job-time "$JOB_TIME" >/dev/null
bash "$WAIT_BATCH" dpiAccrualCalculation "$JOB_TIME" "$rs"

read -r eligible all_od accrual_base accrual_amount verdict <<<"$(
  dpi_pg -t -A -F' ' -v ON_ERROR_STOP=1 \
    -v loan_account_id="$LOAN_ACCOUNT_ID" \
    -v go_live_date="$GO_LIVE_ISO" \
    -v grace_days="$GRACE_DAYS" \
    -v as_on="$AS_ON" \
    -f "$ROOT/scripts/dpic/sql/helpers/verify_go_live_ud_e2e.sql" | tail -1
)"
[[ "$verdict" == "PASS" ]] || fail "go-live base: verdict=$verdict eligible=$eligible all_od=$all_od accrual_base=$accrual_base"
echo "OK go-live base accrual_base=$accrual_base (eligible=$eligible, all_overdue=$all_od)"

echo ">>> maturity < go-live must skip calc"
MAT_BEFORE="$(python3 - "$GO_LIVE_ISO" <<'PY'
import sys
from datetime import date, timedelta
g = date.fromisoformat(sys.argv[1])
print((g - timedelta(days=30)).isoformat())
PY
)"
dpi_pg -v ON_ERROR_STOP=1 -c \
  "UPDATE mfi_accounting.loan_account SET maturity_date = '$MAT_BEFORE'::timestamp, updated_on = NOW(), updated_by = 'DPI_UD_E2E' WHERE account_id = $LOAN_ACCOUNT_ID;"
dpi_pg -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" \
  -f "$ROOT/scripts/dpic/sql/helpers/purge_dpi_accruals_for_loan.sql" >/dev/null
purge_batch dpiAccrualCalculation "$JOB_TIME"
rs="$(date +%s)"
JOB_TIME="$JOB_TIME" "$NTEST" api accounting dpiAccrualCalculation --batch --job-time "$JOB_TIME" >/dev/null
bash "$WAIT_BATCH" dpiAccrualCalculation "$JOB_TIME" "$rs"
n="$(dpi_pg -t -A -c "SELECT COUNT(*) FROM mfi_accounting.dpi_accrual_details WHERE loan_account_id=$LOAN_ACCOUNT_ID AND is_deleted=false AND total_accrued_amount>0;")"
[[ "${n:-0}" == "0" ]] || fail "maturity before go-live: expected 0 accrual rows, got $n"
dpi_pg -v ON_ERROR_STOP=1 -c \
  "UPDATE mfi_accounting.loan_account SET maturity_date = '$maturity_orig'::timestamp, updated_on = NOW(), updated_by = 'DPI_UD_E2E' WHERE account_id = $LOAN_ACCOUNT_ID;"
echo "OK maturity skip"

echo ">>> full EOD + posting calendar"
dpi_pg -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" -v grace_days="$GRACE_DAYS" \
  -f "$ROOT/scripts/dpic/sql/helpers/setup_grace_dpi_e2e.sql" >/dev/null
dpi_pg -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" \
  -f "$ROOT/scripts/dpic/sql/helpers/setup_multi_emi_dpi_e2e.sql" >/dev/null
dpi_pg -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" \
  -f "$ROOT/scripts/dpic/sql/helpers/purge_dpi_accruals_for_loan.sql" >/dev/null
dpi_pg -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" \
  -f "$ROOT/scripts/dpic/sql/helpers/reset_dpi_booking_replay.sql" >/dev/null
LOAN_ACCOUNT_ID="$LOAN_ACCOUNT_ID" JOB_TIME="$JOB_TIME" RESET_DPI_BOOKING=1 \
  bash "$ROOT/scripts/dpic/run_eod_dpi_only.sh"

read -r unposted posted closed <<<"$(
  dpi_pg -t -A -F' ' -v ON_ERROR_STOP=1 \
    -v loan_account_id="$LOAN_ACCOUNT_ID" \
    -v business_date="$AS_ON" \
    -f "$ROOT/scripts/dpic/sql/helpers/verify_dpi_posting_calendar.sql" | tail -1
)"
[[ "${unposted:-1}" == "0" ]] || fail "posting gaps: unposted_on_posting_day=$unposted posted=$posted closed=$closed"
echo "OK posting calendar posted=$posted closed=$closed"

echo "PASS: DPI go-live UD E2E"
