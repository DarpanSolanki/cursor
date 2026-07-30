#!/usr/bin/env bash
# QA business-date JUMP regression (not daily EOD). Confirms calc walks full window in one hop.
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
JUMP_MODE="${JUMP_MODE:-milestones}"   # milestones | single
NTEST="$ROOT/scripts/bin/ntest.sh"
export ROOT NTEST LOAN_ACCOUNT_ID GO_LIVE_ISO END_DATE

fail() { echo "FAIL: $*" >&2; exit 1; }

prepare_fixture() {
  dpi_pg -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" -v grace_days="$GRACE_DAYS" \
    -f "$ROOT/scripts/dpic/sql/helpers/setup_simple_two_month_overdue.sql" >/dev/null
  dpi_pg -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" \
    -f "$ROOT/scripts/dpic/sql/helpers/quarantine_dpd_portfolio.sql" >/dev/null
  dpi_pg -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" \
    -f "$ROOT/scripts/dpic/sql/helpers/purge_dpi_accruals_for_loan.sql" >/dev/null
  dpi_pg -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" \
    -f "$ROOT/scripts/dpic/sql/helpers/reset_dpi_booking_replay.sql" >/dev/null
}

setup_go_live() {
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
  bash "$ROOT/scripts/bin/novopay-service.sh" ensure accounting ${COMPILE:+--compile}
}

assert_parity() {
  local label="$1"
  read -r unposted posted closed <<<"$(
    dpi_pg -t -A -F' ' -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" -v business_date="$END_DATE" \
      -f "$ROOT/scripts/dpic/sql/helpers/verify_dpi_posting_calendar.sql" | tail -1
  )"
  [[ "${unposted:-1}" == "0" ]] || fail "$label: unposted=$unposted posted=$posted closed=$closed"

  read -r total_acc posted_acc billed_acc gl_posted dpi_due posted_gl billed_due posted_covers <<<"$(
    dpi_pg -t -A -F' ' -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" \
      -f "$ROOT/scripts/dpic/sql/helpers/verify_dpi_amount_parity.sql" | tail -1
  )"
  [[ "${posted_gl:-f}" == "t" ]] || fail "$label: posted $posted_acc != GL $gl_posted"
  [[ "${billed_due:-f}" == "t" ]] || fail "$label: billed $billed_acc != due $dpi_due"
  [[ "${posted_covers:-f}" == "t" ]] || fail "$label: posted < billed"
  echo "OK $label: posted=$posted_acc gl=$gl_posted due=$dpi_due slices_closed=$closed"
}

dpi_ensure_accounting
dpi_ensure_masterdata
setup_go_live

echo "=== DPI jump regression LAN=$ACCOUNT_NUMBER mode=$JUMP_MODE ==="
prepare_fixture
chmod +x "$ROOT/scripts/dpic/lib/dpi_run_milestone_eod.sh"
bash "$ROOT/scripts/dpic/lib/dpi_run_milestone_eod.sh" "$JUMP_MODE" "$GO_LIVE_ISO" "$END_DATE"
assert_parity "jump_$JUMP_MODE"

# Cross-check: single jump must match milestone hops (same end state)
if [[ "$JUMP_MODE" == "milestones" ]]; then
  REF_POSTED="$(dpi_pg -t -A -c "SELECT COALESCE(SUM(total_accrued_amount) FILTER (WHERE accrual_posting_date IS NOT NULL),0) FROM mfi_accounting.dpi_accrual_details WHERE loan_account_id=$LOAN_ACCOUNT_ID AND is_deleted=false")"
  REF_DUE="$(dpi_pg -t -A -c "SELECT COALESCE(SUM(due_amount),0) FROM mfi_accounting.loan_due_details WHERE loan_account_id=$LOAN_ACCOUNT_ID AND component_type='DPI' AND is_deleted=false")"
  prepare_fixture
  bash "$ROOT/scripts/dpic/lib/dpi_run_milestone_eod.sh" single "$END_DATE"
  SINGLE_POSTED="$(dpi_pg -t -A -c "SELECT COALESCE(SUM(total_accrued_amount) FILTER (WHERE accrual_posting_date IS NOT NULL),0) FROM mfi_accounting.dpi_accrual_details WHERE loan_account_id=$LOAN_ACCOUNT_ID AND is_deleted=false")"
  SINGLE_DUE="$(dpi_pg -t -A -c "SELECT COALESCE(SUM(due_amount),0) FROM mfi_accounting.loan_due_details WHERE loan_account_id=$LOAN_ACCOUNT_ID AND component_type='DPI' AND is_deleted=false")"
  [[ "$REF_POSTED" == "$SINGLE_POSTED" ]] || fail "single jump posted $SINGLE_POSTED != milestone $REF_POSTED"
  [[ "$REF_DUE" == "$SINGLE_DUE" ]] || fail "single jump due $SINGLE_DUE != milestone $REF_DUE"
  assert_parity "jump_single"
  echo "OK single-jump matches milestone-hops (posted=$SINGLE_POSTED due=$SINGLE_DUE)"
fi

bash "$ROOT/scripts/dpic/lib/dpi_local_db_teardown.sh"
echo "PASS: DPI business-date jump regression ($JUMP_MODE)"
