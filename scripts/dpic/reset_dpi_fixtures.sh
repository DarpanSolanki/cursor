#!/usr/bin/env bash
# Reset canonical DPI fixture LANs after global purge — per-loan DPI wipe + booking replay reset.
# Does NOT insert accruals; jobs recreate state. Fixture seed SQL only (installments/grace/go-live).
#
# Usage: bash scripts/dpic/reset_dpi_fixtures.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT/scripts/dpic/lib/dpi_fixture_constants.sh"
# shellcheck disable=SC1091
source "$ROOT/scripts/dpic/lib/dpi_demo_fixture.sh"

reset_one_loan() {
  local loan_id="$1" label="$2"
  echo ">>> reset fixture loan $loan_id ($label)"
  dpi_pg -v ON_ERROR_STOP=1 -v loan_account_id="$loan_id" \
    -f "$ROOT/scripts/dpic/sql/helpers/purge_dpi_accruals_for_loan.sql" >/dev/null
  dpi_pg -v ON_ERROR_STOP=1 -v loan_account_id="$loan_id" \
    -f "$ROOT/scripts/dpic/sql/helpers/reset_dpi_booking_replay.sql" >/dev/null
  dpi_pg -v ON_ERROR_STOP=1 -v loan_account_id="$loan_id" \
    -f "$ROOT/scripts/dpic/sql/helpers/restore_demo_installments_after_post_maturity_e2e.sql" >/dev/null 2>&1 || true
  # Billed DPI dues survive an accrual-only purge, so every billing run adds another row and
  # milestone asserts drift (jump_regression read due=108 against billed=27 on a 4-row pile-up).
  dpi_pg -v ON_ERROR_STOP=1 -c "
UPDATE mfi_accounting.loan_due_details
SET is_deleted = true, updated_on = NOW(), updated_by = 'DPI_FIXTURE_RESET'
WHERE loan_account_id = $loan_id AND component_type = 'DPI' AND is_deleted = false;
" >/dev/null
  dpi_pg -v ON_ERROR_STOP=1 -c "
UPDATE mfi_accounting.loan_account
SET loan_status = 'ACTIVE', is_deleted = false, la_closing_date = NULL,
    updated_on = NOW(), updated_by = 'DPI_FIXTURE_RESET'
WHERE account_id = $loan_id;
"
}

echo "=== reset_dpi_fixtures: canonical LAN hygiene ==="
reset_one_loan "$DPI_FIXTURE_LOAN_ID" "main/$DPI_FIXTURE_LAN"
reset_one_loan "$DPI_GRACE_CHAIN_LOAN_ID" "grace/$DPI_GRACE_CHAIN_LAN"
reset_one_loan "$DPI_SHG_PARENT_LOAN_ID" "shg/$DPI_SHG_PARENT_LAN"

# SHG family children
family_ids="$(dpi_pg -t -A -c "
SELECT account_id FROM mfi_accounting.loan_account
WHERE parent_loan_account_id = $DPI_SHG_PARENT_LOAN_ID AND is_deleted = false
ORDER BY account_id")"
while IFS= read -r aid; do
  [[ -n "$aid" ]] || continue
  reset_one_loan "$aid" "shg-child"
done <<<"$family_ids"

echo ""
echo "=== fixture LAN snapshot ==="
dpi_pg -c "
SELECT la.account_id AS loan_id,
       la.la_account_number AS lan,
       la.loan_status,
       (SELECT MIN(ldd.due_date)::date FROM mfi_accounting.loan_due_details ldd
        WHERE ldd.loan_account_id = la.account_id AND ldd.is_deleted = false
          AND ldd.component_type IN ('PRIN','INT')) AS first_emi_due,
       (SELECT COUNT(*) FROM mfi_accounting.dpi_accrual_details d
        WHERE d.loan_account_id = la.account_id AND d.is_deleted = false) AS dpi_rows
FROM mfi_accounting.loan_account la
WHERE la.account_id IN ($DPI_FIXTURE_LOAN_ID, $DPI_GRACE_CHAIN_LOAN_ID, $DPI_SHG_PARENT_LOAN_ID)
ORDER BY la.account_id;
"

echo "=== reset_dpi_fixtures: done ==="
