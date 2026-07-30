#!/usr/bin/env bash
# Suite-level booking+DPD quarantine: keep all canonical fixture loans, park the rest.
# Usage: bash scripts/dpic/lib/suite_booking_quarantine.sh park|restore
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT/scripts/dpic/lib/dpi_fixture_constants.sh"
PG=(psql -h "${YB_HOST:-127.0.0.1}" -p "${YB_PORT:-5433}" -U "${YB_USER:-yugabyte}" -d "${YB_DB:-yugabyte}")
export PGPASSWORD="${PGPASSWORD:-yugabyte}"

KEEP_IDS="${DPI_FIXTURE_LOAN_ID},${DPI_GRACE_CHAIN_LOAN_ID},${DPI_SHG_PARENT_LOAN_ID},${DPI_CHILD_JLG_LOAN_ID}"
# SHG children also kept via parent_loan_account_id match in SQL below.

cmd="${1:?park|restore}"

case "$cmd" in
  park)
    echo ">>> suite quarantine park (keep fixtures + SHG children): $KEEP_IDS"
    # FIX: ensure DPI batches have force_async=TRUE job params.
    # Some earlier executions showed force_async missing from batch_job_execution_params,
    # which disables internal parallelization and makes the harness wait on long STARTED jobs.
    "${PG[@]}" -v ON_ERROR_STOP=1 -f "$ROOT/scripts/sql/adhoc/upsert_dpi_batch_job_force_parameters_yugabyte.sql" >/dev/null
    # Local harness: force_async upsert sets is_multi_node=TRUE; revert for single-node Spring registration.
    "${PG[@]}" -v ON_ERROR_STOP=1 -f "$ROOT/scripts/dpic/sql/helpers/upsert_dpi_batch_local_single_node.sql" >/dev/null
    rm -f "$ROOT/.cursor/.dpi-local-single-node.stamp"
    "${PG[@]}" -v ON_ERROR_STOP=1 <<SQL
BEGIN;
CREATE TABLE IF NOT EXISTS mfi_accounting._demo_dpd_quarantine_backup (
  account_id BIGINT PRIMARY KEY, past_due_days INT NOT NULL, backed_up_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS mfi_accounting._demo_dpi_booking_quarantine_backup (
  accrual_id BIGINT PRIMARY KEY, loan_account_id BIGINT NOT NULL, backed_up_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO mfi_accounting._demo_dpd_quarantine_backup (account_id, past_due_days)
SELECT la.account_id, la.past_due_days
FROM mfi_accounting.loan_account la
WHERE la.past_due_days > 0 AND la.loan_status = 'ACTIVE'
  AND la.account_id NOT IN ($KEEP_IDS)
  AND COALESCE(la.parent_loan_account_id, -1) NOT IN ($KEEP_IDS)
ON CONFLICT (account_id) DO UPDATE
  SET past_due_days = EXCLUDED.past_due_days, backed_up_at = NOW();

UPDATE mfi_accounting.loan_account la
SET past_due_days = 0, updated_on = NOW(), updated_by = 'SUITE_DPD_QUARANTINE'
WHERE la.past_due_days > 0 AND la.loan_status = 'ACTIVE'
  AND la.account_id NOT IN ($KEEP_IDS)
  AND COALESCE(la.parent_loan_account_id, -1) NOT IN ($KEEP_IDS);

INSERT INTO mfi_accounting._demo_dpi_booking_quarantine_backup (accrual_id, loan_account_id)
SELECT da.id, da.loan_account_id
FROM mfi_accounting.dpi_accrual_details da
JOIN mfi_accounting.loan_account la ON la.account_id = da.loan_account_id
WHERE da.is_deleted = false AND da.accrual_posting_date IS NULL AND da.total_accrued_amount > 0
  AND la.loan_status IN ('ACTIVE','FORECLOSURE_FREEZE')
  AND da.loan_account_id NOT IN ($KEEP_IDS)
  AND COALESCE(la.parent_loan_account_id, -1) NOT IN ($KEEP_IDS)
ON CONFLICT (accrual_id) DO UPDATE
  SET loan_account_id = EXCLUDED.loan_account_id, backed_up_at = NOW();

UPDATE mfi_accounting.dpi_accrual_details da
SET is_deleted = true
FROM mfi_accounting._demo_dpi_booking_quarantine_backup b
WHERE da.id = b.accrual_id AND da.is_deleted = false;

COMMIT;

SELECT 'booking_eligible_loans=' || COUNT(DISTINCT da.loan_account_id)
FROM mfi_accounting.dpi_accrual_details da
JOIN mfi_accounting.loan_account la ON la.account_id = da.loan_account_id
WHERE da.is_deleted = false AND da.accrual_posting_date IS NULL AND da.total_accrued_amount > 0
  AND la.loan_status IN ('ACTIVE','FORECLOSURE_FREEZE');
SQL
    ;;
  restore)
    echo ">>> suite quarantine restore"
    "${PG[@]}" -v ON_ERROR_STOP=1 -f "$ROOT/scripts/dpic/sql/helpers/restore_dpd_portfolio.sql"
    ;;
  *)
    echo "usage: $0 park|restore" >&2
    exit 2
    ;;
esac
