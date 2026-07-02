#!/usr/bin/env bash
# Post-maturity catch-up: accrual through month-end; billing on a late date (not next anchor).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT/scripts/dpic/lib/dpi_demo_fixture.sh"

export LOAN_ACCOUNT_ID="${LOAN_ACCOUNT_ID:-8060160}"
export ACCOUNT_NUMBER="${ACCOUNT_NUMBER:-6004044425}"
export MATURITY_ISO="${MATURITY_ISO:-2026-05-02}"
export ACCRUAL_THROUGH_ISO="${ACCRUAL_THROUGH_ISO:-2026-06-30}"
export BILLING_RUN_ISO="${BILLING_RUN_ISO:-2026-06-20}"
export EXPECTED_DUE_ANCHOR_ISO="${EXPECTED_DUE_ANCHOR_ISO:-2026-06-02}"
export GRACE_DAYS="${GRACE_DAYS:-3}"
export QUARANTINE_PORTFOLIO="${QUARANTINE_PORTFOLIO:-1}"

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

GO_LIVE_DDMM="$(python3 - "$MATURITY_ISO" <<'PY'
import sys
from datetime import datetime
print(datetime.strptime(sys.argv[1], "%Y-%m-%d").strftime("%d-%m-%Y"))
PY
)"

read -r MATURITY_ORIG PRODUCT_CODE ACCOUNT_NUM <<<"$(
  dpi_pg -t -A -F' ' -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" <<'SQL'
SELECT la.maturity_date::date,
       COALESCE(p.code, 'JLGDL'),
       a.account_number
FROM mfi_accounting.loan_account la
JOIN mfi_accounting.account a ON a.id = la.account_id
JOIN mfi_accounting.loan_product lp ON lp.id = la.loan_product_id
LEFT JOIN mfi_accounting.product p ON p.id = lp.product_id AND p.is_deleted = false
WHERE la.account_id = :loan_account_id::bigint;
SQL
)"

restore_fixture() {
  dpi_pg -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" \
    -f "$ROOT/scripts/dpic/sql/helpers/restore_demo_installments_after_post_maturity_e2e.sql" >/dev/null 2>&1 || true
  dpi_pg -v ON_ERROR_STOP=1 \
    -v loan_account_id="$LOAN_ACCOUNT_ID" \
    -v maturity_date_orig="$MATURITY_ORIG" \
    -f "$ROOT/scripts/dpic/sql/helpers/restore_post_maturity_dpi_e2e.sql" >/dev/null 2>&1 || true
}

trap restore_fixture EXIT

echo "=== DPI post-maturity catch-up E2E loan=$LOAN_ACCOUNT_ID maturity=$MATURITY_ISO billing_run=$BILLING_RUN_ISO ==="

dpi_ensure_accounting --compile
dpi_ensure_masterdata
dpi_set_go_live_and_refresh "$GO_LIVE_DDMM" "7676"

dpi_pg -v ON_ERROR_STOP=1 \
  -v loan_account_id="$LOAN_ACCOUNT_ID" \
  -v "maturity_date=$MATURITY_ISO" \
  -f "$ROOT/scripts/dpic/sql/helpers/setup_post_maturity_dpi_e2e.sql" >/dev/null
dpi_pg -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" -v grace_days="$GRACE_DAYS" \
  -f "$ROOT/scripts/dpic/sql/helpers/setup_grace_dpi_e2e.sql" >/dev/null
dpi_pg -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" \
  -f "$ROOT/scripts/dpic/sql/helpers/quarantine_dpd_portfolio.sql" >/dev/null
dpi_pg -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" \
  -f "$ROOT/scripts/dpic/sql/helpers/purge_dpi_accruals_for_loan.sql" >/dev/null
dpi_pg -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" \
  -f "$ROOT/scripts/dpic/sql/helpers/reset_dpi_booking_replay.sql" >/dev/null

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

run_calc_book_at() {
  local day="$1"
  local ms
  ms="$(date_to_ms "$day")"
  dpi_pg -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" -v business_date_ms="$ms" \
    -f "$ROOT/scripts/dpic/sql/helpers/sync_demo_past_due.sql" >/dev/null
  echo "    calc+book → $day"
  call_batch dpiAccrualCalculation "$ms"
  call_batch dpiAccrualBooking "$ms"
}

mapfile -t ACCRUAL_DAYS < <(
  dpi_pg -t -A -v ON_ERROR_STOP=1 \
    -v loan_account_id="$LOAN_ACCOUNT_ID" \
    -v go_live_date="$MATURITY_ISO" \
    -v end_date="$ACCRUAL_THROUGH_ISO" \
    -f "$ROOT/scripts/dpic/sql/helpers/list_dpi_posting_days.sql"
  echo "$ACCRUAL_THROUGH_ISO"
)

echo ">>> accrual milestones $MATURITY_ISO .. $ACCRUAL_THROUGH_ISO (calc+booking only)"
for day in $(printf '%s\n' "${ACCRUAL_DAYS[@]}" | sort -u); do
  [[ -n "$day" ]] || continue
  run_calc_book_at "$day"
done

BILLING_MS="$(date_to_ms "$BILLING_RUN_ISO")"
dpi_pg -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" -v business_date_ms="$BILLING_MS" \
  -f "$ROOT/scripts/dpic/sql/helpers/sync_demo_past_due.sql" >/dev/null

echo ">>> late billing only on $BILLING_RUN_ISO (before July anchor for June accrual)"
call_batch dpiBilling "$BILLING_MS"

read -r next_emi posted billed unbilled billed_amt unbilled_amt due_rows due_day due_amt \
  no_next has_due due_anchor partial amounts_ok <<<"$(
  dpi_pg -t -A -F' ' -v ON_ERROR_STOP=1 \
    -v loan_account_id="$LOAN_ACCOUNT_ID" \
    -v "expected_due_anchor_date=$EXPECTED_DUE_ANCHOR_ISO" \
    -f "$ROOT/scripts/dpic/sql/helpers/verify_dpi_post_maturity_billing_catchup.sql" | tail -1
)"

echo "  posted=$posted billed=$billed unbilled_posted=$unbilled billed_amt=$billed_amt unbilled_amt=$unbilled_amt"
echo "  dpi_due_rows=$due_rows due_day=$due_day due_amt=$due_amt"

[[ "${no_next:-f}" == "t" ]] || fail "expected no EMI after maturity"
[[ "${has_due:-f}" == "t" ]] || fail "no DPI loan_due_details row on catch-up run"
[[ "${due_anchor:-f}" == "t" ]] || fail "DPI due_date $due_day != expected anchor $EXPECTED_DUE_ANCHOR_ISO"
[[ "${partial:-f}" == "t" ]] || fail "expected partial catch-up (some billed, some unbilled)"
[[ "${amounts_ok:-f}" == "t" ]] || fail "billed amounts zero"

echo "PASS: post-maturity catch-up billing lan=$ACCOUNT_NUM loan=$LOAN_ACCOUNT_ID run=$BILLING_RUN_ISO"
