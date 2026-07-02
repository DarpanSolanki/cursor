#!/usr/bin/env bash
# Two billing cycles on one loan — QA-shaped date jumps from real schedule (not single-hop billing).
# Asserts: 2+ loan_due_details DPI rows, 2+ billing GL txns, full schema contract.
#
# Modes (DUAL_BILLING_MODE):
#   fixture — demo LAN 8060160 + setup_simple_two_month_overdue (regression)
#   fresh     — keep disburse schedule; setup_natural_overdue_for_dpi only
#   auto      — fresh when LOAN_ACCOUNT_ID != 8060160 (default)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT/scripts/dpic/lib/dpi_demo_fixture.sh"
# shellcheck disable=SC1091
source "$ROOT/scripts/dpic/lib/dpi_fixture_pin.sh"

LOAN_ACCOUNT_ID="${LOAN_ACCOUNT_ID:-8060160}"
DUAL_BILLING_MODE="${DUAL_BILLING_MODE:-auto}"
GRACE_DAYS="${GRACE_DAYS:-3}"
GO_LIVE_DDMM="${GO_LIVE_DDMM:-}"
GO_LIVE_ISO="${GO_LIVE_ISO:-}"
NTEST="$ROOT/scripts/bin/ntest.sh"
WAIT_BATCH="$ROOT/scripts/dpic/lib/wait_batch_job.sh"
QA_VERIFY="$ROOT/scripts/dpic/lib/run_dpi_qa_verify.sh"

fail() { echo "FAIL: $*" >&2; exit 1; }

resolve_mode() {
  case "$DUAL_BILLING_MODE" in
    fixture) echo fixture ;;
    fresh) echo fresh ;;
    auto)
      if dpi_is_fixture_loan; then echo fixture; else echo fresh; fi
      ;;
    *) fail "unknown DUAL_BILLING_MODE=$DUAL_BILLING_MODE (fixture|fresh|auto)" ;;
  esac
}

resolve_go_live() {
  read -r first_emi disb_date <<<"$(
    dpi_pg -t -A -F' ' -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" <<'SQL'
SELECT
  (SELECT lid.installment_date::date::text
   FROM mfi_accounting.loan_installment_details lid
   WHERE lid.loan_account_id = :loan_account_id::bigint AND lid.is_deleted = false
   ORDER BY lid.serial_number LIMIT 1),
  (SELECT la.expected_disbursement_date::date::text
   FROM mfi_accounting.loan_account la
   WHERE la.account_id = :loan_account_id::bigint);
SQL
  )"
  [[ -n "${first_emi:-}" ]] || fail "no installments for loan $LOAN_ACCOUNT_ID"
  if [[ -z "${GO_LIVE_ISO:-}" ]]; then
    GO_LIVE_ISO="$(python3 - "$first_emi" "$disb_date" <<'PY'
import sys
from datetime import datetime, timedelta
first = datetime.strptime(sys.argv[1], "%Y-%m-%d").date()
disb = sys.argv[2]
if disb and disb != "":
    d = datetime.strptime(disb, "%Y-%m-%d").date()
    go = min(d, first - timedelta(days=14))
else:
    go = first - timedelta(days=30)
print(go.isoformat())
PY
)"
  fi
  if [[ -z "${GO_LIVE_DDMM:-}" ]]; then
    GO_LIVE_DDMM="$(python3 - "$GO_LIVE_ISO" <<'PY'
import sys
from datetime import datetime
print(datetime.strptime(sys.argv[1], "%Y-%m-%d").strftime("%d-%m-%Y"))
PY
)"
  fi
  export GO_LIVE_ISO GO_LIVE_DDMM
}

run_milestones_through() {
  local end_date="$1"
  export ROOT NTEST LOAN_ACCOUNT_ID GO_LIVE_ISO END_DATE="$end_date"
  chmod +x "$ROOT/scripts/dpic/lib/dpi_run_milestone_eod.sh"
  bash "$ROOT/scripts/dpic/lib/dpi_run_milestone_eod.sh" milestones "$GO_LIVE_ISO" "$end_date"
}

dpi_due_count() {
  dpi_pg -t -A -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" <<'SQL'
SELECT COUNT(*) FROM mfi_accounting.loan_due_details
WHERE loan_account_id = :loan_account_id::bigint AND component_type = 'DPI' AND is_deleted = false;
SQL
}

billing_txn_count() {
  dpi_pg -t -A -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" <<'SQL'
SELECT COUNT(DISTINCT da.billing_transaction_ref_number)
FROM mfi_accounting.dpi_accrual_details da
WHERE da.loan_account_id = :loan_account_id::bigint AND da.is_deleted = false
  AND da.billing_posting_date IS NOT NULL
  AND da.billing_transaction_ref_number IS NOT NULL;
SQL
}

verify_billing_events() {
  read -r dup mismatch bill_days due_days <<<"$(
    dpi_pg -t -A -F' ' -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" \
      -f "$ROOT/scripts/dpic/sql/helpers/verify_dpi_billing_events.sql" | head -1
  )"
  [[ "${dup:-1}" == "0" ]] || fail "duplicate billing GL refs on same day: dup_ref_days=$dup"
  [[ "${mismatch:-1}" == "0" ]] || fail "billed vs due mismatch days=$mismatch"
  [[ "${bill_days:-0}" -ge 2 ]] || fail "expected >=2 billing event days, got $bill_days"
  [[ "${due_days:-0}" -ge 2 ]] || fail "expected >=2 DPI due days, got $due_days"
}

MODE="$(resolve_mode)"

read -r product_code lan <<<"$(
  dpi_pg -t -A -F' ' -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" <<'SQL'
SELECT COALESCE(p.code, 'JLGDL'), a.account_number
FROM mfi_accounting.loan_account la
JOIN mfi_accounting.account a ON a.id = la.account_id
JOIN mfi_accounting.loan_product lp ON lp.id = la.loan_product_id
LEFT JOIN mfi_accounting.product p ON p.id = lp.product_id AND p.is_deleted = false
WHERE la.account_id = :loan_account_id::bigint;
SQL
)"

echo "=== DPI dual billing E2E mode=$MODE lan=$lan loan=$LOAN_ACCOUNT_ID ==="
dpi_ensure_accounting
dpi_ensure_masterdata
resolve_go_live

dpi_pg -v ON_ERROR_STOP=1 -v go_live_value="$GO_LIVE_DDMM" -v go_live_sub_type="$product_code" \
  -f "$ROOT/scripts/dpic/sql/helpers/upsert_dpi_go_live.sql" >/dev/null
dpi_evict_go_live_cache "$product_code"
dpi_restart_masterdata

if [[ "$MODE" == "fixture" ]]; then
  dpi_pg -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" -v grace_days="$GRACE_DAYS" \
    -f "$ROOT/scripts/dpic/sql/helpers/setup_grace_dpi_e2e.sql" >/dev/null
  dpi_pg -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" -v grace_days="$GRACE_DAYS" \
    -f "$ROOT/scripts/dpic/sql/helpers/setup_simple_two_month_overdue.sql" >/dev/null
else
  dpi_pg -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" -v grace_days="$GRACE_DAYS" \
    -f "$ROOT/scripts/dpic/sql/helpers/setup_natural_overdue_for_dpi.sql" >/dev/null
fi

dpi_pg -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" \
  -f "$ROOT/scripts/dpic/sql/helpers/reset_dpi_booking_replay.sql" >/dev/null
dpi_pg -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" \
  -f "$ROOT/scripts/dpic/sql/helpers/purge_dpi_accruals_for_loan.sql" >/dev/null
dpi_pg -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" \
  -f "$ROOT/scripts/dpic/sql/helpers/quarantine_dpd_portfolio.sql" >/dev/null

read -r first_bill_date second_bill_date <<<"$(
  dpi_pg -t -A -F' ' -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" <<'SQL'
SELECT
  (SELECT lid.installment_date::date::text
   FROM mfi_accounting.loan_installment_details lid
   WHERE lid.loan_account_id = :loan_account_id::bigint AND lid.is_deleted = false
   ORDER BY lid.serial_number OFFSET 1 LIMIT 1),
  (SELECT lid.installment_date::date::text
   FROM mfi_accounting.loan_installment_details lid
   WHERE lid.loan_account_id = :loan_account_id::bigint AND lid.is_deleted = false
   ORDER BY lid.serial_number OFFSET 2 LIMIT 1);
SQL
)"
[[ -n "${first_bill_date:-}" && -n "${second_bill_date:-}" ]] \
  || fail "need two billing milestone dates from schedule (got first=$first_bill_date second=$second_bill_date)"

echo ">>> go_live=$GO_LIVE_ISO billing targets=[$first_bill_date,$second_bill_date]"
echo ">>> billing cycle 1 — EOD milestones through $first_bill_date (from schedule)"
run_milestones_through "$first_bill_date"
c1="$(dpi_due_count)"
t1="$(billing_txn_count)"
echo "    after cycle 1: dpi_due_rows=$c1 billing_txns=$t1"
[[ "${c1:-0}" -ge 1 ]] || fail "cycle 1: expected >=1 DPI due row, got $c1"
[[ "${t1:-0}" -ge 1 ]] || fail "cycle 1: expected >=1 billing txn, got $t1"
bash "$QA_VERIFY" "$LOAN_ACCOUNT_ID" "$first_bill_date"

echo ">>> billing cycle 2 — EOD milestones through $second_bill_date"
run_milestones_through "$second_bill_date"
c2="$(dpi_due_count)"
t2="$(billing_txn_count)"
echo "    after cycle 2: dpi_due_rows=$c2 billing_txns=$t2"
[[ "${c2:-0}" -ge 2 ]] || fail "cycle 2: expected >=2 DPI due rows (two billing events), got $c2"
[[ "${t2:-0}" -ge 2 ]] || fail "cycle 2: expected >=2 distinct billing txns, got $t2"
bash "$QA_VERIFY" "$LOAN_ACCOUNT_ID" "$second_bill_date"

bash "$ROOT/scripts/dpic/run_dpi_billing_ud_verify.sh" || fail "billing UD after dual cycle"
verify_billing_events

echo "PASS: dual billing mode=$MODE lan=$lan due_rows=$c2 billing_txns=$t2 dates=[$first_bill_date,$second_bill_date]"
