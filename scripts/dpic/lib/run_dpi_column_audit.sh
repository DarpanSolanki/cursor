#!/usr/bin/env bash
# Column audit gate: slice integrity + booking/billing + QA slice table.
# Usage: run_dpi_column_audit.sh <loan_account_id> <business_date YYYY-MM-DD>
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
HELPERS="$ROOT/scripts/dpic/sql/helpers"
LOAN_ID="${1:?loan_account_id}"
BIZ_DATE="${2:?business_date YYYY-MM-DD}"

# shellcheck disable=SC1091
source "$ROOT/scripts/dpic/lib/dpi_demo_fixture.sh"

fail() { echo "COLUMN_AUDIT_FAIL: $*" >&2; exit 1; }

echo "=== DPI column audit loan=$LOAN_ID business_date=$BIZ_DATE ==="

slice_out="$(dpi_pg -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ID" -v business_date="$BIZ_DATE" \
  -f "$HELPERS/verify_dpi_accrual_slice_integrity.sql" 2>&1)"
slice_viol="$(echo "$slice_out" | awk -F'|' '/^[[:space:]]*[0-9]+[[:space:]]*\|/ {gsub(/ /,"",$1); print $1; exit}')"
slice_rules="$(echo "$slice_out" | awk -F'|' '/^[[:space:]]*[0-9]+[[:space:]]*\|/ {gsub(/^[[:space:]]+|[[:space:]]+$/,"",$2); print $2; exit}')"
[[ -n "${slice_viol:-}" ]] || fail "could not parse slice violation_count"
[[ "${slice_viol}" == "0" ]] || fail "slice violations=$slice_viol rules=${slice_rules:-?}"

book_line="$(dpi_pg -t -A -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ID" -v business_date="$BIZ_DATE" \
  -f "$HELPERS/verify_dpi_booking_billing_audit.sql" 2>/dev/null | head -1)"
book_viol="${book_line%%|*}"
book_rules="${book_line#*|}"
[[ "${book_viol:-1}" == "0" ]] || fail "booking/billing violations=$book_viol rules=${book_rules:-?}"

echo "$slice_out" | sed -n '/=== slice timeline ===/,$p'

echo ""
echo "=== booking/billing audit (biz=$BIZ_DATE) ==="
dpi_pg -v loan_account_id="$LOAN_ID" -v business_date="$BIZ_DATE" -c "
SELECT id,
       start_date::date AS start_d,
       end_date::date AS end_d,
       total_accrued_amount AS amt,
       accrual_posting_date::date AS apd,
       billing_posting_date::date AS bpd,
       CASE
         WHEN end_date::date <= DATE '$BIZ_DATE' AND accrual_posting_date IS NULL
              AND (
                EXTRACT(DAY FROM end_date) = EXTRACT(DAY FROM (date_trunc('month', end_date) + interval '1 month - 1 day'))
                OR EXISTS (
                  SELECT 1 FROM mfi_accounting.loan_due_details d
                  WHERE d.loan_account_id = $LOAN_ID AND d.is_deleted = false
                    AND d.component_type IN ('INT','PRIN') AND d.due_date::date = end_date::date
                )
              ) THEN 'FAIL sealed_unposted'
         WHEN end_date::date <= DATE '$BIZ_DATE' AND accrual_posting_date IS NOT NULL
              AND billing_posting_date IS NULL
              AND (
                EXISTS (
                  SELECT 1 FROM mfi_accounting.loan_due_details d
                  WHERE d.loan_account_id = $LOAN_ID AND d.is_deleted = false
                    AND d.component_type IN ('INT','PRIN') AND d.due_date::date = end_date::date
                )
                OR EXISTS (
                  SELECT 1 FROM mfi_accounting.loan_due_details d
                  WHERE d.loan_account_id = $LOAN_ID AND d.is_deleted = false
                    AND d.component_type IN ('INT','PRIN')
                    AND d.due_date::date > end_date::date
                    AND d.due_date::date <= DATE '$BIZ_DATE'
                )
              ) THEN 'FAIL sealed_unbilled'
         ELSE 'OK'
       END AS gate
FROM mfi_accounting.dpi_accrual_details
WHERE loan_account_id = $LOAN_ID AND is_deleted = false AND total_accrued_amount > 0
ORDER BY end_date, id;

SELECT 'posted_slices' AS check_name, COUNT(*)::text AS actual
FROM mfi_accounting.dpi_accrual_details
WHERE loan_account_id = $LOAN_ID AND is_deleted = false AND accrual_posting_date IS NOT NULL
UNION ALL
SELECT 'dpi_due_rows', COUNT(*)::text
FROM mfi_accounting.loan_due_details
WHERE loan_account_id = $LOAN_ID AND component_type = 'DPI' AND is_deleted = false;
"

echo ""
echo "PASS: column audit loan=$LOAN_ID slice=0 booking=0"
