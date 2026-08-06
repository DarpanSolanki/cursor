#!/usr/bin/env bash
# TDPQA-237: DPI accrual must use the ROI in force on each accrual day, not the post-restructure
# rate for the whole backfilled window. Seals at rescheduling_effective_date like interest accrual.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT/scripts/dpic/lib/dpi_demo_fixture.sh"

LOAN_ACCOUNT_ID="${LOAN_ACCOUNT_ID:-8060160}"
GRACE_DAYS="${GRACE_DAYS:-3}"
JOB_TIME="${JOB_TIME:-1782563400000}"
GO_LIVE_DDMM="${GO_LIVE_DDMM:-15-04-2026}"
ROI_CHANGE_DATE="${ROI_CHANGE_DATE:-2026-05-20}"
OLD_ROI="${OLD_ROI:-16}"
NEW_ROI="${NEW_ROI:-20}"
NTEST="$ROOT/scripts/bin/ntest.sh"
WAIT_BATCH="$ROOT/scripts/dpic/lib/wait_batch_job.sh"

fail() { echo "FAIL: $*" >&2; exit 1; }

dpi_ensure_accounting
dpi_ensure_masterdata

evict_aid_cache() {
  redis-cli -n 5 --scan --pattern 'account_interest_details::*' 2>/dev/null \
    | xargs -r redis-cli -n 5 del >/dev/null
}

# 8060160 is the shared DPI fixture loan — leaving the seeded ROI change behind makes every
# sibling case accrue at a rate this scenario invented (it did, on first run).
ORIGINAL_ROI="$(dpi_pg -t -A -v ON_ERROR_STOP=1 -c \
  "SELECT effective_rate FROM mfi_accounting.account_interest_details WHERE account_id = $LOAN_ACCOUNT_ID;" | tr -d '[:space:]')"

teardown() {
  dpi_pg -v ON_ERROR_STOP=1 -c "
DELETE FROM mfi_accounting.loan_account_restructuring_details
WHERE loan_account_id = $LOAN_ACCOUNT_ID AND created_by = 'DPI_ROI_E2E';
UPDATE mfi_accounting.account_interest_details
SET effective_rate = ${ORIGINAL_ROI:-$OLD_ROI}
WHERE account_id = $LOAN_ACCOUNT_ID;" >/dev/null 2>&1 || true
  evict_aid_cache
}
trap teardown EXIT

product_code="$(dpi_pg -t -A -v ON_ERROR_STOP=1 -c "
SELECT p.code FROM mfi_accounting.loan_account la
JOIN mfi_accounting.loan_product lp ON lp.id = la.loan_product_id
JOIN mfi_accounting.product p ON p.id = lp.product_id
WHERE la.account_id = $LOAN_ACCOUNT_ID;")"
[[ -n "$product_code" ]] || fail "no product code for loan $LOAN_ACCOUNT_ID"

echo "=== DPI ROI-change E2E loan=$LOAN_ACCOUNT_ID change=$ROI_CHANGE_DATE ${OLD_ROI}%->${NEW_ROI}% ==="

dpi_pg -v ON_ERROR_STOP=1 -v go_live_value="$GO_LIVE_DDMM" -v go_live_sub_type="$product_code" \
  -f "$ROOT/scripts/dpic/sql/helpers/upsert_dpi_go_live.sql" >/dev/null

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

dpi_pg -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" \
  -v roi_change_date="$ROI_CHANGE_DATE" -v old_roi="$OLD_ROI" -v new_roi="$NEW_ROI" \
  -f "$ROOT/scripts/dpic/sql/helpers/setup_roi_change_restructure.sql" >/dev/null

# account_interest_details is @Cacheable in Redis DB 5; the real restructure flow evicts via
# save(), a SQL-seeded rate does not. Without this the job still reads the pre-change rate.
evict_aid_cache

COMPILE=1 bash "$ROOT/scripts/bin/novopay-service.sh" ensure accounting --compile

echo ">>> dpiAccrualCalculation"
dpi_prep_before_batch
dpi_purge_batch dpiAccrualCalculation "$JOB_TIME"
before="$(dpi_pg -t -A -c "
SELECT COALESCE(MAX(bje.job_execution_id), 0)
FROM mfi_batch.batch_job_execution bje
JOIN mfi_batch.batch_job_instance bji ON bji.job_instance_id = bje.job_instance_id
WHERE bji.job_name = 'dpiAccrualCalculation'")"
JOB_TIME="$JOB_TIME" "$NTEST" api accounting dpiAccrualCalculation --batch --job-time "$JOB_TIME" >/dev/null
BATCH_WAIT_ARG3=before bash "$WAIT_BATCH" dpiAccrualCalculation "$JOB_TIME" "$before"

echo ">>> accrual rows"
dpi_pg -v ON_ERROR_STOP=1 -c "
SELECT start_date::date, end_date::date, dpi_annual_rate, base_amount, total_accrued_amount
FROM mfi_accounting.dpi_accrual_details
WHERE loan_account_id = $LOAN_ACCOUNT_ID AND is_deleted = false
ORDER BY start_date;"

ROWS="FROM mfi_accounting.dpi_accrual_details WHERE loan_account_id = $LOAN_ACCOUNT_ID AND is_deleted = false"

dpi_assert_sql_gt "SELECT COUNT(*) $ROWS AND end_date <= '$ROI_CHANGE_DATE'::date;" 0 \
  "pre-change rows exist"
dpi_assert_sql_gt "SELECT COUNT(*) $ROWS AND start_date >= '$ROI_CHANGE_DATE'::date;" 0 \
  "post-change rows exist"
dpi_assert_sql_eq "SELECT COUNT(*) $ROWS AND end_date <= '$ROI_CHANGE_DATE'::date AND dpi_annual_rate <> $OLD_ROI;" 0 \
  "every pre-change row stamped ${OLD_ROI}%"
dpi_assert_sql_eq "SELECT COUNT(*) $ROWS AND start_date >= '$ROI_CHANGE_DATE'::date AND dpi_annual_rate <> $NEW_ROI;" 0 \
  "every post-change row stamped ${NEW_ROI}%"
dpi_assert_sql_eq "SELECT COUNT(*) $ROWS AND start_date < '$ROI_CHANGE_DATE'::date AND end_date > '$ROI_CHANGE_DATE'::date;" 0 \
  "no row straddles the ROI change date"

echo "PASS: DPI ROI-change E2E"
