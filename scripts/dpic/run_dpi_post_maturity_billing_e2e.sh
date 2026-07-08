#!/usr/bin/env bash
# Post-maturity DPI billing: last EMI = maturity = go-live; bill on next monthly anchor.
# Reproduces EOD order calc → booking → billing on anchor day (same-day accrual end race).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT/scripts/dpic/lib/dpi_demo_fixture.sh"

export LOAN_ACCOUNT_ID="${LOAN_ACCOUNT_ID:-8060160}"
export ACCOUNT_NUMBER="${ACCOUNT_NUMBER:-6004044425}"
export MATURITY_ISO="${MATURITY_ISO:-2026-05-02}"
export BILLING_ANCHOR_ISO="${BILLING_ANCHOR_ISO:-2026-06-02}"
export GRACE_DAYS="${GRACE_DAYS:-3}"
export QUARANTINE_PORTFOLIO="${QUARANTINE_PORTFOLIO:-1}"
export SYNC_PAST_DUE="${SYNC_PAST_DUE:-1}"

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

echo "=== DPI post-maturity billing E2E loan=$LOAN_ACCOUNT_ID lan=$ACCOUNT_NUM maturity=$MATURITY_ISO anchor=$BILLING_ANCHOR_ISO ==="

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

ACCRUAL_END_ISO="$(python3 - "$BILLING_ANCHOR_ISO" <<'PY'
import sys
from datetime import datetime, timedelta
anchor = datetime.strptime(sys.argv[1], "%Y-%m-%d").date()
first_of_month = anchor.replace(day=1)
print((first_of_month - timedelta(days=1)).isoformat())
PY
)"

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
    -v end_date="$ACCRUAL_END_ISO" \
    -f "$ROOT/scripts/dpic/sql/helpers/list_dpi_posting_days.sql"
  echo "$ACCRUAL_END_ISO"
)

echo ">>> accrual milestones $MATURITY_ISO .. $ACCRUAL_END_ISO (calc+booking only)"
for day in $(printf '%s\n' "${ACCRUAL_DAYS[@]}" | sort -u); do
  [[ -n "$day" ]] || continue
  run_calc_book_at "$day"
done

ANCHOR_MS="$(date_to_ms "$BILLING_ANCHOR_ISO")"
dpi_pg -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" -v business_date_ms="$ANCHOR_MS" \
  -f "$ROOT/scripts/dpic/sql/helpers/sync_demo_past_due.sql" >/dev/null

echo ">>> anchor day EOD (calc + booking + billing on $BILLING_ANCHOR_ISO)"
call_batch dpiAccrualCalculation "$ANCHOR_MS"
call_batch dpiAccrualBooking "$ANCHOR_MS"
call_batch dpiBilling "$ANCHOR_MS"

read -r next_emi posted billed unbilled billed_amt due_rows due_day due_amt \
  no_next has_due due_anchor all_billed amounts_ok <<<"$(
  dpi_pg -t -A -F' ' -v ON_ERROR_STOP=1 \
    -v loan_account_id="$LOAN_ACCOUNT_ID" \
    -v billing_anchor_date="'$BILLING_ANCHOR_ISO'" \
    -f "$ROOT/scripts/dpic/sql/helpers/verify_dpi_post_maturity_billing.sql" | tail -1
)"

echo "  next_emi=$next_emi posted=$posted billed=$billed unbilled_posted=$unbilled billed_amt=$billed_amt"
echo "  dpi_due_rows=$due_rows due_day=$due_day due_amt=$due_amt"

[[ "${no_next:-f}" == "t" ]] || fail "expected no EMI after maturity"
[[ "${has_due:-f}" == "t" ]] || fail "no DPI loan_due_details row"
[[ "${due_anchor:-f}" == "t" ]] || fail "DPI due_date $due_day != anchor $BILLING_ANCHOR_ISO"
[[ "${all_billed:-f}" == "t" ]] || fail "accrual posted but not billed (unbilled_posted=$unbilled)"
[[ "${amounts_ok:-f}" == "t" ]] || fail "billed amounts zero"

EVIDENCE="$ROOT/scripts/dpic/last_post_maturity_billing.env"
cat >"$EVIDENCE" <<EOF
# Post-maturity DPI billing E2E — source scripts/dpic/run_dpi_post_maturity_billing_e2e.sh
LOAN_ACCOUNT_ID=$LOAN_ACCOUNT_ID
ACCOUNT_NUMBER=$ACCOUNT_NUM
MATURITY_ISO=$MATURITY_ISO
BILLING_ANCHOR_ISO=$BILLING_ANCHOR_ISO
BILLED_AMOUNT=$billed_amt
DPI_DUE_AMOUNT=$due_amt
CERTIFIED_AT=$(date -Iseconds)
FIX_COMMIT=ee9838d6a
EOF

echo "PASS: post-maturity DPI billing lan=$ACCOUNT_NUM loan=$LOAN_ACCOUNT_ID anchor=$BILLING_ANCHOR_ISO"
echo "Evidence: $EVIDENCE"
