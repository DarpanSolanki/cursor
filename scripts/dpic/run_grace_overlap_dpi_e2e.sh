#!/usr/bin/env bash
# Multi-EMI grace overlap: DPI accrual continues through EMI2 grace (not killed by latest-EMI grace).
# Product stamps overlap-window slices to EMI2 (latest due ≤ segStart); EMI1 seals at next due.
# Causes FAIL on the old "latest-EMI grace kill-switch" bug (zero accrual in grace window).
#
# Suite hygiene (critical):
#   - Isolates shared grace-chain LAN before run (hard purge + restore EMI schedule).
#   - Purges Spring Batch executions per job_time (no COMPLETED residue / 0s no-ops).
#   - Column audit asserts THIS case's outcomes only:
#       * overlap ownership (primary)
#       * sealed_unposted / sealed_unbilled for EMI1 seals that are billing-eligible on proof_date
#       * open EMI2-grace window (end on non-due / non-month-end) may stay unposted/unbilled — OK
#   - When RUN_COLUMN_AUDIT=1, hides EMI3+ so next-EMI billing calendar matches product intent
#     for EMI1 seals on proof_date (same as two_emi). Overlap ownership does not need EMI3.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT/scripts/dpic/lib/dpi_fixture_constants.sh"
if [[ "${DPI_USE_CUSTOM_LOAN:-0}" != "1" ]]; then
  dpi_use_grace_chain_loan
fi
: "${GRACE_DAYS:=3}"
: "${PRODUCT_CODE:=7676}"
: "${GO_LIVE_DDMM:=15-04-2025}"
: "${GO_LIVE_ISO:=2026-05-01}"
# shellcheck source=lib/dpi_demo_fixture.sh
source "$ROOT/scripts/dpic/lib/dpi_demo_fixture.sh"
if [[ "${DPI_USE_CUSTOM_LOAN:-0}" != "1" ]]; then
  dpi_use_grace_chain_loan
fi
export JOB_TIME="$DPI_GRACE_OVERLAP_JOB_TIME"
PROOF_DATE="${PROOF_DATE:-2026-06-17}"
RUN_AUDIT="${RUN_COLUMN_AUDIT:-1}"
# ownership = overlap SQL only; full = overlap + book/bill + column audit (default)
AUDIT_SCOPE="${DPI_OVERLAP_AUDIT_SCOPE:-full}"

echo "=== DPI grace overlap E2E (accrual continues in EMI2 grace; owned by EMI2) ==="
echo "  loan_account_id=$LOAN_ACCOUNT_ID grace=$GRACE_DAYS job_time=$JOB_TIME proof_date=$PROOF_DATE audit=$AUDIT_SCOPE"

bash "$ROOT/scripts/bin/novopay-service.sh" ensure accounting ${COMPILE:+--compile}

dpi_set_go_live_and_refresh "$GO_LIVE_DDMM" "$PRODUCT_CODE"

# Isolate shared LAN — prior two_emi/grace/booking_anchor must not leave sealed residue.
dpi_isolate_loan_for_case "$LOAN_ACCOUNT_ID"

dpi_pg -v ON_ERROR_STOP=1 \
  -v loan_account_id="$LOAN_ACCOUNT_ID" \
  -v grace_days="$GRACE_DAYS" \
  -f "$ROOT/scripts/dpic/sql/helpers/setup_grace_dpi_e2e.sql"

# Fair billing window for column audit: hide EMI3+ so EMI1 seals are billable once EMI2 due ≤ biz.
# Overlap ownership assert only needs EMI1+EMI2 live; EMI3 would block EMI2-anchored billing only.
if [[ "$RUN_AUDIT" == "1" && "$AUDIT_SCOPE" == "full" ]]; then
  echo "  dpi: hide EMI3+ for billing-eligible column audit on proof_date=$PROOF_DATE"
  dpi_pg -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" -v grace_days="$GRACE_DAYS" <<'SQL'
UPDATE mfi_accounting.loan_due_details ldd
SET is_deleted = true, updated_on = NOW(), updated_by = 'DPI_OVERLAP_HIDE_EMI3'
FROM mfi_accounting.loan_installment_details lid
WHERE lid.loan_account_id = :loan_account_id::bigint
  AND lid.serial_number >= 3
  AND ldd.loan_installment_details_id = lid.id
  AND ldd.is_deleted = false;

UPDATE mfi_accounting.loan_installment_details
SET is_deleted = true, updated_on = NOW(), updated_by = 'DPI_OVERLAP_HIDE_EMI3'
WHERE loan_account_id = :loan_account_id::bigint
  AND serial_number >= 3
  AND is_deleted = false;
SQL
fi

dpi_pg -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" \
  -f "$ROOT/scripts/dpic/sql/helpers/quarantine_dpd_portfolio.sql" >/dev/null

dpi_pg -v ON_ERROR_STOP=1 \
  -v loan_account_id="$LOAN_ACCOUNT_ID" \
  -v business_date_ms="$JOB_TIME" \
  -f "$ROOT/scripts/dpic/sql/helpers/sync_demo_past_due.sql" >/dev/null

if [[ -f "$ROOT/scripts/dpic/sql/helpers/clear_batch_failure_audit.sql" ]]; then
  JOB_TIME="$JOB_TIME" dpi_pg -v ON_ERROR_STOP=1 \
    -v loan_account_id="$LOAN_ACCOUNT_ID" \
    -f "$ROOT/scripts/dpic/sql/helpers/clear_batch_failure_audit.sql" >/dev/null 2>&1 || true
fi

fail() { echo "FAIL: $*" >&2; exit 1; }

echo ">>> dpiAccrualCalculation (overlap window through EMI2 grace)"
dpi_call_batch dpiAccrualCalculation "$JOB_TIME"

verify_out="$(dpi_pg -v ON_ERROR_STOP=1 -t -A -F'|' \
  -v loan_account_id="$LOAN_ACCOUNT_ID" \
  -v grace_days="$GRACE_DAYS" \
  -f "$ROOT/scripts/dpic/sql/helpers/verify_grace_overlap_dpi_e2e.sql" | grep -E '^[0-9]' | tail -1)"

# Settle DB write(s) — partition COMPLETED can race ahead of JPA flush on cold JVM.
for _ in 1 2 3 4 5; do
  IFS='|' read -r emi1_id emi1_due emi1_od emi2_id emi2_due emi2_od rows_overlap amt_overlap emi1_rows emi2_rows overlap_ok <<<"$verify_out"
  if [[ "$overlap_ok" == "t" ]]; then
    break
  fi
  sleep 1
  verify_out="$(dpi_pg -v ON_ERROR_STOP=1 -t -A -F'|' \
    -v loan_account_id="$LOAN_ACCOUNT_ID" \
    -v grace_days="$GRACE_DAYS" \
    -f "$ROOT/scripts/dpic/sql/helpers/verify_grace_overlap_dpi_e2e.sql" | grep -E '^[0-9]' | tail -1)"
done

IFS='|' read -r emi1_id emi1_due emi1_od emi2_id emi2_due emi2_od rows_overlap amt_overlap emi1_rows emi2_rows overlap_ok <<<"$verify_out"

[[ -n "$emi1_id" && -n "$emi2_id" && "$emi1_id" != "$emi2_id" ]] || fail "need two unpaid INT EMIs (got emi1=$emi1_id emi2=$emi2_id)"
[[ "$overlap_ok" == "t" ]] || fail "overlap_ok=$overlap_ok rows=$rows_overlap amt=$amt_overlap emi1_rows=$emi1_rows emi2_rows=$emi2_rows (expect accrual in ($emi2_due,$emi2_od) owned by EMI2; EMI1 sealed at next due)"

echo "PASS: accrual continues in EMI2 grace ($emi2_due .. $emi2_od); amt=$amt_overlap emi2_rows=$emi2_rows emi1_rows=$emi1_rows (EMI1 sealed)"

echo ""
echo "=== accrual rows around EMI2 due ==="
dpi_pg -v ON_ERROR_STOP=1 -c "
SELECT da.installment_id, lid.installment_date::date, da.start_date::date, da.end_date::date,
       da.total_accrued_amount, da.base_amount,
       da.accrual_posting_date::date AS posted, da.billing_posting_date::date AS billed
FROM mfi_accounting.dpi_accrual_details da
JOIN mfi_accounting.loan_installment_details lid ON lid.id = da.installment_id
WHERE da.loan_account_id = $LOAN_ACCOUNT_ID AND da.is_deleted = false
  AND da.end_date::date >= DATE '2026-06-10'
ORDER BY da.end_date ASC;
"

if [[ "$RUN_AUDIT" == "1" && "$AUDIT_SCOPE" == "full" ]]; then
  echo ">>> dpiAccrualBooking + dpiBilling (case-scoped column audit on $PROOF_DATE)"
  dpi_call_batch dpiAccrualBooking "$JOB_TIME"
  dpi_call_batch dpiBilling "$JOB_TIME"
  bash "$ROOT/scripts/dpic/lib/run_dpi_column_audit.sh" "$LOAN_ACCOUNT_ID" "$PROOF_DATE" \
    || fail "column audit violations after calc+booking+billing (isolated run — treat as real only if EMI1 seals stay posted+unbilled)"
  echo "PASS: column audit 0 violations (loan=$LOAN_ACCOUNT_ID proof_date=$PROOF_DATE)"
elif [[ "$AUDIT_SCOPE" == "ownership" ]]; then
  echo "PASS: ownership-only scope (skipped book/bill column audit)"
fi
